"""
Rule Enforcement Agent — deterministic compliance checks, NO LLM.

This is intentionally NOT a subclass of BaseAgent.

Why no LLM here:
    Compliance rules exist precisely because they cannot be reasoned around.
    An LLM that concludes "$10,001 is essentially the same as $9,999" is
    producing a compliance violation, however sound the logic appears.
    Deterministic Python code that checks `amount > 10_000` provides an
    absolute guarantee — the same input always produces the same outcome,
    with no variance, no temperature, no hallucination.

    This is the most important design decision in the system. The audit
    trail for a rule violation must be "Python evaluated amount > 10000 and
    got True", not "the LLM assessed the amount as high-value".

run_fallback():
    If the main run() raises (e.g. malformed structured_transaction), the
    pipeline calls run_fallback() instead. It applies only MANDATORY_ESCALATION
    rules (the highest-severity subset) and marks output as DETERMINISTIC_FALLBACK
    so the final report discloses reduced rule coverage to the analyst.
"""

from datetime import datetime, timezone

from config.constitutional_policies import MINIMUM_SCORE_WITH_RULE_VIOLATION
from config.fraud_rules import FRAUD_RULES
from models.schemas import RuleEnforcementOutput, RuleViolation
from pipeline.state import FraudPipelineState
from utils.logger import FraudPipelineLogger


class RuleEnforcementAgent:
    """Deterministic compliance rule checker — no LLM, no BaseAgent."""

    agent_name = "rule_enforcement"
    agent_version = "1.0.0"
    SEVERITY_ORDER = ["NONE", "ADVISORY", "MANDATORY_REVIEW", "MANDATORY_ESCALATION"]

    def __init__(self):
        self.logger = FraudPipelineLogger("rule_enforcement")

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    def run(self, state: FraudPipelineState) -> dict:
        start_time = datetime.now(timezone.utc)
        self.logger.log_agent_start(
            self.agent_name, state.get("transaction_ref", "")
        )

        transaction = state.get("structured_transaction", {})
        violations: list[RuleViolation] = []
        highest_severity = "NONE"

        for rule in FRAUD_RULES:
            try:
                if rule.check_function(transaction):
                    violation = RuleViolation(
                        rule_id=rule.rule_id,
                        rule_name=rule.rule_name,
                        severity=rule.severity,
                        description=rule.description,
                        evidence=(
                            f"{rule.rule_name} triggered: "
                            f"{self._get_triggered_value(rule.rule_id, transaction)}"
                        ),
                        minimum_score_override=(
                            MINIMUM_SCORE_WITH_RULE_VIOLATION
                            if rule.severity in ("MANDATORY_REVIEW", "MANDATORY_ESCALATION")
                            else None
                        ),
                    )
                    violations.append(violation)
                    if (
                        self.SEVERITY_ORDER.index(rule.severity)
                        > self.SEVERITY_ORDER.index(highest_severity)
                    ):
                        highest_severity = rule.severity
            except Exception:
                # Individual rule failure must not crash the whole agent.
                # The logger records only the rule_id — never exception text.
                self.logger.log_agent_error(self.agent_name, f"rule_check_failed_{rule.rule_id}")

        requires_review = highest_severity in ("MANDATORY_REVIEW", "MANDATORY_ESCALATION")

        output = RuleEnforcementOutput(
            violations=violations,
            violations_found=len(violations),
            rules_checked=len(FRAUD_RULES),
            highest_severity=highest_severity,
            requires_human_review=requires_review,
            source="DETERMINISTIC",
        )

        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        self.logger.log_agent_complete(self.agent_name, duration_ms=duration_ms, success=True)

        return {"rule_violations": output.model_dump()}

    # ------------------------------------------------------------------
    # Fallback — critical rules only
    # ------------------------------------------------------------------

    def run_fallback(self, state: FraudPipelineState) -> dict:
        """
        Apply only MANDATORY_ESCALATION rules when main run() fails.

        Always sets requires_human_review=True and marks source as
        DETERMINISTIC_FALLBACK so the analyst knows rule coverage was reduced.
        """
        transaction = state.get("structured_transaction", {})
        violations: list[RuleViolation] = []

        critical_rules = [
            r for r in FRAUD_RULES if r.severity == "MANDATORY_ESCALATION"
        ]
        for rule in critical_rules:
            try:
                if rule.check_function(transaction):
                    violations.append(
                        RuleViolation(
                            rule_id=rule.rule_id,
                            rule_name=rule.rule_name,
                            severity=rule.severity,
                            description=rule.description,
                            evidence=(
                                f"{rule.rule_name} triggered: "
                                f"{self._get_triggered_value(rule.rule_id, transaction)}"
                            ),
                            minimum_score_override=MINIMUM_SCORE_WITH_RULE_VIOLATION,
                        )
                    )
            except Exception:
                pass

        highest = "MANDATORY_ESCALATION" if violations else "NONE"
        output = RuleEnforcementOutput(
            violations=violations,
            violations_found=len(violations),
            rules_checked=len(critical_rules),
            highest_severity=highest,
            requires_human_review=True,
            source="DETERMINISTIC_FALLBACK",
            evaluation_notes="Full rule set unavailable — critical rules only applied.",
        )

        return {"rule_violations": output.model_dump()}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_triggered_value(self, rule_id: str, transaction: dict) -> str:
        field_map = {
            "R001": "amount",
            "R002": "transaction_count_10min",
            "R003": "location_country",
            "R004": "amount",
            "R005": "amount",
        }
        field = field_map.get(rule_id, "unknown")
        return str(transaction.get(field, "N/A"))
