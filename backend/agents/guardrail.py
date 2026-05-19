"""
Guardrail Agent — cross-cutting security checks, NO LLM.

This is intentionally NOT a subclass of BaseAgent.

Role:
    The Guardrail runs BEFORE and AFTER every agent in the pipeline. It is not
    a fraud-detection component — it makes no risk assessments and has no fraud
    verdict fields. Its only job is to flag security and quality issues and
    report them to the orchestrator, which decides what to do.

Severity semantics:
    INFO     — logged, no pipeline impact
    WARNING  — flagged, pipeline continues (orchestrator may add to report)
    CRITICAL — pipeline halts immediately before the next agent runs

Why deterministic (no LLM):
    Security checks cannot be "reasoned about". A guardrail that uses an LLM
    to decide whether an injection attempt is real is itself an attack surface.
    Regex-based PII detection and pattern matching are predictable, auditable,
    and impossible to social-engineer.

Singletons:
    PIIHandler and InjectionDetector are created once at module import and
    reused. This avoids recompiling all regex patterns on every pipeline call.
"""

import re
from datetime import datetime, timezone

from config.constitutional_policies import (
    ACTION_LANGUAGE_ALLOWED_AGENTS,
    CERTAINTY_PHRASES,
    MINIMUM_SCORE_WITH_RULE_VIOLATION,
    SCOPE_CREEP_PHRASES,
)
from models.schemas import GuardrailFlag
from pipeline.state import FraudPipelineState
from security.injection_detector import InjectionDetector
from security.pii_handler import PIIHandler
from utils.logger import FraudPipelineLogger

_pii_handler = PIIHandler()
_detector = InjectionDetector()


class GuardrailAgent:
    """Cross-cutting security checks — no LLM, no BaseAgent."""

    agent_name = "guardrail"

    def __init__(self):
        self.logger = FraudPipelineLogger("guardrail")

    # ------------------------------------------------------------------
    # Pre-agent check
    # ------------------------------------------------------------------

    def pre_agent_check(
        self,
        agent_name: str,
        agent_input: dict,
        state: FraudPipelineState,
    ) -> list[dict]:
        """
        Run before any agent receives its input.
        Returns list of GuardrailFlag dicts (empty = all clear).
        """
        flags: list[GuardrailFlag] = []
        input_text = str(agent_input)
        ts = datetime.now(timezone.utc).isoformat()

        # Check 1 — Injection detection
        injection_result = _detector.check_input(input_text)
        if not injection_result["is_safe"]:
            for raw_flag in injection_result["flags"]:
                severity = raw_flag.get("severity", "WARNING")
                guardrail_severity = "CRITICAL" if severity == "CRITICAL" else "WARNING"
                action = "INPUT_BLOCKED" if guardrail_severity == "CRITICAL" else "INPUT_FLAGGED"
                flags.append(GuardrailFlag(
                    flag_type="INJECTION_ATTEMPT",
                    severity=guardrail_severity,
                    agent_context=agent_name,
                    description=raw_flag.get("description", "Injection pattern detected"),
                    remediation="Reject input and halt pipeline.",
                    timestamp=ts,
                ))
                self.logger.log_guardrail_flag(
                    "INJECTION_ATTEMPT", guardrail_severity, agent_name, action
                )

        # Check 2 — PII in input
        pii_types = _pii_handler.scan_for_pii_in_output(input_text)
        for pii_type in pii_types:
            flags.append(GuardrailFlag(
                flag_type=f"PII_IN_INPUT_{pii_type}",
                severity="WARNING",
                agent_context=agent_name,
                description=f"Unmasked PII detected in agent input: {pii_type}",
                remediation="Ensure PIIHandler.detect_and_tokenize ran before this agent.",
                timestamp=ts,
            ))
            self.logger.log_guardrail_flag(
                f"PII_IN_INPUT_{pii_type}", "WARNING", agent_name, "PII_FLAGGED"
            )

        return [f.model_dump() for f in flags]

    # ------------------------------------------------------------------
    # Post-agent check
    # ------------------------------------------------------------------

    def post_agent_check(
        self,
        agent_name: str,
        agent_output: dict,
        original_state: FraudPipelineState,
    ) -> list[dict]:
        """
        Run after any agent produces output.
        Returns list of GuardrailFlag dicts (empty = all clear).
        """
        flags: list[GuardrailFlag] = []
        output_text = str(agent_output).lower()
        ts = datetime.now(timezone.utc).isoformat()

        # Check 1 — Scope creep (only for agents that must not use action language)
        if agent_name not in ACTION_LANGUAGE_ALLOWED_AGENTS:
            for phrase in SCOPE_CREEP_PHRASES:
                if phrase.lower() in output_text:
                    flags.append(GuardrailFlag(
                        flag_type="SCOPE_CREEP",
                        severity="WARNING",
                        agent_context=agent_name,
                        description=f"Agent used action language outside permitted role: '{phrase}'",
                        remediation="Review agent system prompt and write restrictions.",
                        timestamp=ts,
                    ))
                    self.logger.log_guardrail_flag(
                        "SCOPE_CREEP", "WARNING", agent_name, "OUTPUT_FLAGGED"
                    )
                    break  # one flag per output is enough

        # Check 2 — False certainty
        for phrase in CERTAINTY_PHRASES:
            if phrase.lower() in output_text:
                flags.append(GuardrailFlag(
                    flag_type="FALSE_CERTAINTY",
                    severity="WARNING",
                    agent_context=agent_name,
                    description=f"Agent used overconfident language: '{phrase}'",
                    remediation="LLM outputs in fraud detection must express uncertainty.",
                    timestamp=ts,
                ))
                self.logger.log_guardrail_flag(
                    "FALSE_CERTAINTY", "WARNING", agent_name, "OUTPUT_FLAGGED"
                )
                break

        # Check 3 — PII in output (CRITICAL — must never reach any log or report)
        raw_output_text = str(agent_output)  # unsuppressed case for PII scan
        pii_types = _pii_handler.scan_for_pii_in_output(raw_output_text)
        for pii_type in pii_types:
            flags.append(GuardrailFlag(
                flag_type=f"PII_IN_OUTPUT_{pii_type}",
                severity="CRITICAL",
                agent_context=agent_name,
                description=f"Unmasked PII found in agent output: {pii_type}",
                remediation="Apply PIIHandler.mask_for_output before returning.",
                timestamp=ts,
            ))
            self.logger.log_guardrail_flag(
                f"PII_IN_OUTPUT_{pii_type}", "CRITICAL", agent_name, "OUTPUT_BLOCKED"
            )

        # Check 4 — Ground truth consistency
        original_amount = (
            original_state.get("structured_transaction", {}) or {}
        ).get("amount")
        if original_amount is not None:
            try:
                numbers_in_output = re.findall(r'\b\d+\.?\d*\b', raw_output_text)
                for num_str in numbers_in_output:
                    num = float(num_str)
                    if num > float(original_amount) * 10:
                        flags.append(GuardrailFlag(
                            flag_type="GROUND_TRUTH_INCONSISTENCY",
                            severity="WARNING",
                            agent_context=agent_name,
                            description=(
                                f"Output contains value {num} which is >10x "
                                f"the original transaction amount {original_amount}"
                            ),
                            remediation="Check for hallucinated amounts in agent output.",
                            timestamp=ts,
                        ))
                        self.logger.log_guardrail_flag(
                            "GROUND_TRUTH_INCONSISTENCY", "WARNING", agent_name, "OUTPUT_FLAGGED"
                        )
                        break
            except (ValueError, TypeError):
                pass

        return [f.model_dump() for f in flags]

    # ------------------------------------------------------------------
    # Halt decision
    # ------------------------------------------------------------------

    def should_halt_pipeline(self, flags: list[dict]) -> bool:
        """Return True if any flag is CRITICAL — pipeline must halt immediately."""
        return any(f.get("severity") == "CRITICAL" for f in flags)
