"""
Deterministic fraud rules applied by the Rule Enforcement Agent.

These rules are pure Python — no LLM, no reasoning, no exceptions.
An LLM that "reasons around" a compliance rule provides zero compliance
guarantee. Deterministic rules are what regulators actually require.

Severity levels:
  ADVISORY              — informational; pipeline continues unchanged
  MANDATORY_REVIEW      — human must review; minimum score floor of 50
  MANDATORY_ESCALATION  — immediate human involvement required; minimum
                          score floor of 50. This is a handoff directive,
                          not an autonomous block — the human decides action.

IMMEDIATE_BLOCK does not exist in this system. The system never autonomously
blocks, freezes, or denies anything. Human authority is always preserved.
"""

from dataclasses import dataclass
from typing import Callable, Literal

# ---------------------------------------------------------------------------
# Countries under comprehensive OFAC sanctions.
# Transactions originating from or destined to these jurisdictions require
# immediate escalation regardless of amount or customer history.
# ---------------------------------------------------------------------------
HIGH_RISK_COUNTRIES: list[str] = ["KP", "IR", "SY", "CU", "SD"]

SeverityLevel = Literal["ADVISORY", "MANDATORY_REVIEW", "MANDATORY_ESCALATION"]


@dataclass
class FraudRule:
    """
    A single deterministic compliance rule.

    check_function receives the structured transaction dict and returns True
    when the rule is violated. It must be a pure function — no side effects,
    no external calls, no randomness. Same input always produces same output.
    """

    rule_id: str
    rule_name: str
    description: str
    severity: SeverityLevel
    check_function: Callable[[dict], bool]
    threshold_description: str


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

def _check_high_value(txn: dict) -> bool:
    """R001: BSA/AML reporting threshold. $10,000+ triggers CTR requirements."""
    return float(txn.get("amount", 0)) > 10_000


def _check_velocity(txn: dict) -> bool:
    """R002: More than 3 transactions in a 10-minute window is structuring risk."""
    return int(txn.get("transaction_count_10min", 0)) > 3


def _check_high_risk_country(txn: dict) -> bool:
    """R003: OFAC-sanctioned jurisdiction. Always requires escalation."""
    return txn.get("location_country", "") in HIGH_RISK_COUNTRIES


def _check_zero_or_negative(txn: dict) -> bool:
    """R004: Amount ≤ 0 indicates data error or potential reversal fraud."""
    return float(txn.get("amount", 1)) <= 0


def _check_cnp_high_value(txn: dict) -> bool:
    """R005: Card-not-present + high value is elevated fraud vector."""
    card_present = txn.get("card_present", True)
    amount = float(txn.get("amount", 0))
    return (not card_present) and (amount > 500)


FRAUD_RULES: list[FraudRule] = [
    FraudRule(
        rule_id="R001",
        rule_name="HIGH_VALUE_THRESHOLD",
        description="Transaction exceeds high-value threshold",
        severity="MANDATORY_REVIEW",
        check_function=_check_high_value,
        threshold_description="amount > $10,000 — BSA/AML Currency Transaction Report threshold",
    ),
    FraudRule(
        rule_id="R002",
        rule_name="VELOCITY_CHECK",
        description="Excessive transactions in short window",
        severity="MANDATORY_REVIEW",
        check_function=_check_velocity,
        threshold_description="more than 3 transactions within a 10-minute window",
    ),
    FraudRule(
        rule_id="R003",
        rule_name="HIGH_RISK_COUNTRY",
        description="Transaction from high-risk country",
        severity="MANDATORY_ESCALATION",
        check_function=_check_high_risk_country,
        threshold_description=f"merchant_country in OFAC-sanctioned list: {HIGH_RISK_COUNTRIES}",
    ),
    FraudRule(
        rule_id="R004",
        rule_name="ZERO_OR_NEGATIVE_AMOUNT",
        description="Transaction has zero or negative amount",
        severity="ADVISORY",
        check_function=_check_zero_or_negative,
        threshold_description="amount <= 0 — likely data error or reversal attempt",
    ),
    FraudRule(
        rule_id="R005",
        rule_name="CARD_NOT_PRESENT_HIGH_VALUE",
        description="Card not present with high value",
        severity="ADVISORY",
        check_function=_check_cnp_high_value,
        threshold_description="card_present is False AND amount > $500",
    ),
]
