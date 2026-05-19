"""
Pydantic output schemas for the multi-agent fraud detection pipeline.

Design rationale:
- extra='forbid' on every schema: structural role enforcement — LLMs physically
  cannot return fields outside the defined contract. Prompt constraints can be
  bypassed; schema constraints cannot.
- Literal types on severity/action fields: the set of valid states is finite and
  known at design time. Constraining them here prevents any agent from inventing
  new states (e.g. IMMEDIATE_BLOCK is intentionally absent — the system never
  blocks autonomously).
- Field validators on all 0-100 score fields: a score of 150 or -5 is a logic
  error that must be caught before it propagates downstream and inflates risk.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Agent 1 — Transaction Analyzer
# ---------------------------------------------------------------------------

class TransactionAnalyzerOutput(BaseModel):
    """
    Structured representation of a raw transaction after parsing.

    Role constraint: this agent ONLY structures input — it makes zero risk
    assessments. No fraud_likelihood, no risk_score, no action fields.
    Downstream agents rely on this being a clean, format-neutral dict.
    """

    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    amount: float
    currency: str
    merchant_name: str
    merchant_category: str
    # Fields below are optional because they cannot always be inferred from
    # plain text input — the LLM must not hallucinate them.
    merchant_country: Optional[str] = None
    transaction_timestamp: Optional[str] = None
    customer_id: Optional[str] = None
    card_present: Optional[bool] = None
    channel: Optional[Literal["online", "in-store", "ATM", "mobile", "unknown"]] = None
    customer_location: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Agent 2 — Anomaly Detection (nested + output)
# ---------------------------------------------------------------------------

class AnomalyFlag(BaseModel):
    """
    A single detected behavioral deviation.

    Kept as a nested model so each anomaly carries its own evidence string —
    this is what grounds the Critic Agent's challenge in specific facts rather
    than a vague summary score.
    """

    model_config = ConfigDict(extra="forbid")

    anomaly_type: str
    description: str
    evidence: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]


class AnomalyDetectionOutput(BaseModel):
    """
    Behavioral analysis output from the Anomaly Detection Agent.

    Role constraint: behavioral deviations only — no rule application, no final
    verdict. The agent compares THIS transaction against THIS customer's history.
    It must not reach into rule_violations or produce a recommended_action.

    severity_score and confidence validated 0-100: any value outside this range
    is a model error that must not silently propagate to Risk Scoring.
    """

    model_config = ConfigDict(extra="forbid")

    anomalies_detected: list[AnomalyFlag]
    severity_score: int
    confidence: int
    behavioral_summary: str
    customer_profile_note: str

    @field_validator("severity_score", "confidence")
    @classmethod
    def validate_score_range(cls, v: int, info) -> int:
        if not 0 <= v <= 100:
            raise ValueError(
                f"{info.field_name} must be between 0 and 100, got {v}"
            )
        return v


# ---------------------------------------------------------------------------
# Agent 3 — Rule Enforcement (nested + output)
# ---------------------------------------------------------------------------

class RuleViolation(BaseModel):
    """
    A single deterministic rule violation.

    Severity is strictly constrained to three levels. IMMEDIATE_BLOCK is
    intentionally absent: this system never autonomously blocks anything.
    MANDATORY_ESCALATION means a human must be involved — it is a handoff
    directive, not an autonomous action.
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    rule_name: str
    severity: Literal["ADVISORY", "MANDATORY_REVIEW", "MANDATORY_ESCALATION"]
    description: str
    evidence: str
    minimum_score_override: Optional[int] = None


class RuleEnforcementOutput(BaseModel):
    """
    Output from the Rule Enforcement Agent (deterministic — NO LLM).

    Role constraint: this agent applies fixed Python logic only. It has no
    reasoning capability and cannot be argued with. The schema has no score
    field because this agent does not produce scores — it produces violations
    that constrain downstream scores.
    """

    model_config = ConfigDict(extra="forbid")

    violations: list[RuleViolation]
    violations_found: int
    rules_checked: int
    highest_severity: Literal[
        "NONE", "ADVISORY", "MANDATORY_REVIEW", "MANDATORY_ESCALATION"
    ]
    requires_human_review: bool
    # "DETERMINISTIC" for normal run; "DETERMINISTIC_FALLBACK" when main run fails
    # and only MANDATORY_ESCALATION rules are applied.
    source: Literal["DETERMINISTIC", "DETERMINISTIC_FALLBACK"]
    evaluation_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Agent 4 — Risk Scoring
# ---------------------------------------------------------------------------

class RiskScoringOutput(BaseModel):
    """
    Multi-signal risk synthesis from the Risk Scoring Agent.

    Role constraint: synthesizes anomaly_report + rule_violations into a single
    scored verdict. It cannot finalize — the Critic must review every verdict
    before it becomes actionable.

    recommended_action is Literal["APPROVE", "REVIEW"]: the system never blocks.
    HIGH risk → REVIEW (human decides), not BLOCK.

    risk_score and confidence validated 0-100.
    """

    model_config = ConfigDict(extra="forbid")

    risk_score: int
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    primary_driver: str
    recommended_action: Literal["APPROVE", "REVIEW"]
    confidence: int
    reasoning: str
    signal_weights: Optional[dict[str, float]] = None
    contributing_factors: Optional[list[str]] = None

    @field_validator("risk_score", "confidence")
    @classmethod
    def validate_score_range(cls, v: int, info) -> int:
        if not 0 <= v <= 100:
            raise ValueError(
                f"{info.field_name} must be between 0 and 100, got {v}"
            )
        return v


# ---------------------------------------------------------------------------
# Agent 5 — Critic
# ---------------------------------------------------------------------------

class CriticOutput(BaseModel):
    """
    Adversarial review output from the Critic Agent.

    Role constraint: challenge every verdict — actively find innocent
    explanations. The Critic is a defence attorney, not a second prosecutor.

    verdict options:
      UPHELD      — no innocent explanation found, score unchanged
      OVERTURNED  — strong innocent explanation, score reduced significantly
      MODIFIED    — partial explanation, score reduced moderately
      ESCALATED   — new concerns found, score increased

    Constitutional constraint enforced in agent code (not here):
      If rule_violations exist → revised_score cannot drop below 50.
      This schema does not enforce that because the schema does not have
      access to pipeline state — the agent code applies the floor.

    All three score fields validated 0-100.
    """

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["UPHELD", "OVERTURNED", "MODIFIED", "ESCALATED"]
    original_score: int
    revised_score: int
    confidence_in_challenge: int
    reasoning: str
    innocent_explanations: Optional[list[str]] = None
    remaining_concerns: Optional[list[str]] = None
    evidence_cited: Optional[list[str]] = None
    loop_count: Optional[int] = None

    @field_validator("original_score", "revised_score", "confidence_in_challenge")
    @classmethod
    def validate_score_range(cls, v: int, info) -> int:
        if not 0 <= v <= 100:
            raise ValueError(
                f"{info.field_name} must be between 0 and 100, got {v}"
            )
        return v


# ---------------------------------------------------------------------------
# Agent 6 — Report Generator
# ---------------------------------------------------------------------------

class ReportGeneratorOutput(BaseModel):
    """
    Analyst-facing final report from the Report Generator.

    Role constraint: TRANSLATOR only. This agent formats and summarises — it
    does not add new analysis, change scores, or introduce its own risk
    assessment. final_risk_score must match critic_final_score exactly
    (enforced in agent code).

    recommended_action is Literal["APPROVE", "REVIEW"]: consistent with
    Risk Scoring — no BLOCK option.

    All PII in string fields must be masked before this schema is populated
    (enforced in agent code via PIIHandler).

    final_risk_score validated 0-100.
    """

    model_config = ConfigDict(extra="forbid")

    transaction_summary: str
    final_risk_score: int
    final_risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    recommended_action: Literal["APPROVE", "REVIEW"]
    key_findings: list[str]
    critic_verdict: Literal["UPHELD", "OVERTURNED", "MODIFIED", "ESCALATED"]
    analyst_questions: list[str]
    reliability: Literal["COMPLETE", "INCOMPLETE", "DEGRADED"]
    incomplete_agents: list[str]
    report_timestamp: str

    @field_validator("final_risk_score")
    @classmethod
    def validate_score_range(cls, v: int, info) -> int:
        if not 0 <= v <= 100:
            raise ValueError(
                f"{info.field_name} must be between 0 and 100, got {v}"
            )
        return v


# ---------------------------------------------------------------------------
# Agent 7 — Guardrail (cross-cutting — NO LLM)
# ---------------------------------------------------------------------------

class GuardrailFlag(BaseModel):
    """
    A single security flag raised by the Guardrail Agent.

    Severity levels:
      INFO     — logged only, no pipeline impact
      WARNING  — flagged, pipeline continues
      CRITICAL — pipeline halts immediately

    Role constraint: the Guardrail never makes fraud decisions. It only raises
    flags that the pipeline orchestrator acts on. A CRITICAL flag halts the
    pipeline — it does not produce a fraud verdict.
    """

    model_config = ConfigDict(extra="forbid")

    flag_type: str
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    agent_context: str
    description: str
    remediation: Optional[str] = None
    timestamp: Optional[str] = None
