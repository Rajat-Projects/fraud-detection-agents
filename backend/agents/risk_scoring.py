"""
Risk Scoring Agent — multi-signal synthesis into one scored verdict.

This agent synthesizes anomaly signals and rule violations into a single
risk score with full reasoning. It cannot finalize — the Critic must review
every verdict before it becomes actionable.

Constitutional constraint:
    If rule violations exist, risk_score cannot drop below 50 regardless
    of how benign the anomaly signals appear. Rule violations represent
    hard compliance requirements that no amount of behavioral reasoning
    can override.

run() override:
    The schema field is named "reasoning" but the state field is named
    "risk_reasoning". The override maps this after the base invocation
    and applies the constitutional score floor.

    "reasoning" is included in get_allowed_state_writes so it passes
    the base agent's filter; the override then renames it to risk_reasoning
    before returning.
"""

from agents.base_agent import BaseAgent
from config.constitutional_policies import MINIMUM_SCORE_WITH_RULE_VIOLATION
from models.schemas import RiskScoringOutput
from pipeline.state import FraudPipelineState


class RiskScoringAgent(BaseAgent):

    def __init__(self):
        super().__init__("risk_scoring", "1.0.0")

    def get_system_prompt(self) -> str:
        return """You are a risk synthesis specialist.
Your job: combine anomaly signals and rule violations into ONE coherent
risk score with full reasoning.

Calibration examples — use these to ground your scoring:

Example 1 — Clear fraud pattern:
Context: Amount 60x above customer average,
         impossible travel velocity (11,000km in 2 hours),
         customer never previously left home city
Anomaly severity: 90, Rule violations: 1 MANDATORY_REVIEW
Correct score: 85, Level: HIGH
Reasoning: Multiple independent severe anomalies plus
           compliance violation. Combined signals
           multiply risk, not just add it.

Example 2 — Clear legitimate transaction:
Context: Amount within 10% of customer average,
         home city merchant, regular shopping time
Anomaly severity: 8, Rule violations: 0
Correct score: 12, Level: LOW
Reasoning: No meaningful deviation from established
           pattern. No compliance concern.

Example 3 — False positive with compliance floor:
Context: Amount normal for this customer's travel pattern,
         established international travel history,
         prior purchases at this merchant type
Anomaly severity: 15, Rule violations: 1 ADVISORY
Correct score: 50, Level: MEDIUM
Reasoning: Behavioral analysis suggests legitimate.
           Advisory violation triggers compliance floor.
           Cannot go below 50 per constitutional policy.

Example 4 — Genuine medium risk:
Context: Amount 3x above average, unfamiliar merchant,
         unusual time, no rule violations
Anomaly severity: 55, Rule violations: 0
Correct score: 58, Level: MEDIUM
Reasoning: Moderate anomaly warrants review
           but not escalation without compliance concern.

Use these examples to calibrate consistently.
Similar patterns should receive similar scores.
Do not anchor to these examples — use them
as calibration references only.

Scoring guide:
- 0-35: LOW risk → recommended_action: APPROVE
- 36-70: MEDIUM risk → recommended_action: REVIEW
- 71-100: HIGH risk → recommended_action: REVIEW

IMPORTANT: recommended_action is never BLOCK.
The system recommends. Humans decide.

If rule violations exist:
- Minimum score is 50 regardless of anomaly signals
- Rule violations represent compliance requirements

You MUST:
- Explain how anomaly signals and rules interact
- List specific contributing and mitigating factors
- Express appropriate uncertainty via confidence score
- Set risk_level consistent with risk_score

You MUST NOT:
- Recommend BLOCK — only APPROVE or REVIEW
- Override rule violations
- Express absolute certainty
- Make the final decision — you inform humans"""

    def get_output_schema(self):
        return RiskScoringOutput

    def get_required_context(self, state: FraudPipelineState) -> dict:
        return {
            "structured_transaction": state.get("structured_transaction", {}),
            "anomaly_report": state.get("anomaly_report", {}),
            "rule_violations": state.get("rule_violations", {}),
        }

    def get_allowed_state_writes(self) -> list[str]:
        # "reasoning" is included so it survives the base filter;
        # the run() override renames it to "risk_reasoning" before returning.
        return ["risk_score", "risk_level", "recommended_action",
                "risk_reasoning", "reasoning"]

    def run(self, state: FraudPipelineState) -> dict:
        # Call base agent to invoke LLM and filter by allowed writes.
        # "reasoning" passes through because it's in get_allowed_state_writes.
        result = super().run(state)

        # Map schema field name → state field name
        result["risk_reasoning"] = result.pop("reasoning", "")

        # Constitutional Policy 5: Hard Rule Finality
        # No reasoning can reduce a score below 50 when rule violations exist.
        rule_violations = (
            state.get("rule_violations", {}) or {}
        ).get("violations", [])
        if rule_violations and result.get("risk_score", 0) < MINIMUM_SCORE_WITH_RULE_VIOLATION:
            result["risk_score"] = MINIMUM_SCORE_WITH_RULE_VIOLATION
            result["risk_level"] = "MEDIUM"

        # Remove "reasoning" if it somehow survived (it was popped above,
        # but belt-and-suspenders since state must not get a "reasoning" key)
        result.pop("reasoning", None)

        return result
