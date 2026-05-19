"""
PII-aware structured logger for the fraud detection pipeline.

Design constraints:
- Log metadata only — never raw transaction data, PII, or LLM output text.
- Log error TYPE only — error messages can contain stack traces with sensitive data.
- JSON-serialized events make log aggregation (CloudWatch, Datadog, etc.) trivial.
- One logger instance per agent so log records carry the originating agent name
  without callers having to include it manually.
"""

import json
import logging
import sys
from datetime import datetime, timezone


class FraudPipelineLogger:

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self._logger = logging.getLogger(f"fraud_pipeline.{agent_name}")

        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)
            self._logger.propagate = False

    # ------------------------------------------------------------------
    # Internal dispatcher
    # ------------------------------------------------------------------

    def _log(self, level: str, event: dict) -> None:
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        event["agent"] = self.agent_name
        serialized = json.dumps(event, default=str)
        log_fn = getattr(self._logger, level.lower(), self._logger.info)
        log_fn(serialized)

    # ------------------------------------------------------------------
    # Public log methods
    # ------------------------------------------------------------------

    def log_agent_start(self, agent_name: str, transaction_ref: str = "") -> None:
        self._log("info", {
            "event": "agent_start",
            "agent": agent_name,
            "transaction_ref": transaction_ref,
        })

    def log_agent_complete(
        self, agent_name: str, duration_ms: float = 0, success: bool = True
    ) -> None:
        self._log("info", {
            "event": "agent_complete",
            "agent": agent_name,
            "duration_ms": duration_ms,
            "success": success,
        })

    def log_agent_error(self, agent_name: str, error_type: str) -> None:
        # Log error TYPE only — never the error message or traceback.
        # Exception messages routinely contain PII, stack frames, or
        # internal logic that must not appear in log aggregators.
        self._log("error", {
            "event": "agent_error",
            "agent": agent_name,
            "error_type": error_type,
        })

    def log_guardrail_flag(
        self, flag_type: str, severity: str, agent: str, action: str
    ) -> None:
        self._log("warning", {
            "event": "guardrail_flag",
            "flag_type": flag_type,
            "severity": severity,
            "agent": agent,
            "action": action,
        })

    def log_risk_verdict(
        self, score: int, level: str, critic_verdict: str = ""
    ) -> None:
        self._log("info", {
            "event": "risk_verdict",
            "score": score,
            "level": level,
            "critic_verdict": critic_verdict,
        })

    def log_pipeline_complete(
        self, duration_ms: float, reliability: str, risk_level: str
    ) -> None:
        self._log("info", {
            "event": "pipeline_complete",
            "duration_ms": duration_ms,
            "reliability": reliability,
            "risk_level": risk_level,
        })
