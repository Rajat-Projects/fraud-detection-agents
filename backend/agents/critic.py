"""
Critic Agent — adversarial challenger of every risk verdict.

Role:
    Defence attorney, not second prosecutor. The Critic assumes the transaction
    is legitimate and actively searches for innocent explanations before
    accepting that fraud occurred. This is the most important agent for
    preventing false positives from reaching analysts as HIGH risk.

Constitutional constraint:
    Even if the Critic finds a compelling innocent explanation, it cannot
    reduce the score below MINIMUM_SCORE_WITH_RULE_VIOLATION (50) when rule
    violations exist. Compliance rules have authority that no reasoning can
    override. The Critic documents this in the reasoning field.

run() override logic:
    super().run(state) returns the schema fields that matched get_allowed_state_writes()
    — verdict, original_score, revised_score, confidence_in_challenge — as a flat dict.
    The override assembles these into a critic_review dict, applies the constitutional
    floor, then sets final_risk_score and final_risk_level on the state.

Demo moment this enables:
    False positive: Risk Scoring → HIGH (85) → Critic → OVERTURNED → MEDIUM (52)
    "This is why false positives don't reach analysts as HIGH risk."
"""

from agents.base_agent import BaseAgent
from config.constitutional_policies import MINIMUM_SCORE_WITH_RULE_VIOLATION
from models.schemas import CriticOutput
from pipeline.state import FraudPipelineState


def _score_to_level(score: int) -> str:
    if score <= 35:
        return "LOW"
    elif score <= 70:
        return "MEDIUM"
    else:
        return "HIGH"


class CriticAgent(BaseAgent):

    def __init__(self):
        super().__init__("critic", "1.0.0")

    def get_system_prompt(self) -> str:
        return """You are the Critic Agent — the defense attorney for every transaction.

Your job is NOT to confirm the risk verdict.
Your job is to CHALLENGE it.

Assume the transaction is LEGITIMATE until proven otherwise.
Actively search for innocent explanations before accepting that fraud occurred.

For every anomaly flagged, ask:
- Could a legitimate customer do this?
- Does the customer history explain this pattern?
- Is there context the other agents missed?
- Are multiple flags actually explained by one innocent cause
  (e.g. travel explains location AND time AND merchant type simultaneously)?

Verdict options:
UPHELD: You genuinely found no innocent explanation. Score unchanged.
OVERTURNED: Strong innocent explanation found. Reduce score significantly.
MODIFIED: Partial innocent explanation found. Reduce score moderately.
ESCALATED: You found NEW concerns not in original analysis. Increase score.

Mandatory reasoning process — follow these steps:

Step 1 — Inventory:
List every anomaly that was flagged.
Do not skip any flag, however minor.

Step 2 — Challenge each flag independently:
For EACH anomaly ask:
"What legitimate reason could produce this pattern?"
Consider: travel, emergencies, new merchants,
seasonal purchases, business expenses.

Step 3 — Check customer history:
Does the customer history specifically support
any innocent explanation you identified?
Prior similar transactions are strong evidence.

Step 4 — Look for unified explanations:
Critical question: Can ONE innocent explanation
account for MULTIPLE anomalies simultaneously?
Example: International travel explains BOTH
unusual location AND unfamiliar merchant AND
different transaction time — all at once.
A unified explanation is much stronger than
separate explanations for each flag.

Step 5 — Assess remaining concerns:
After applying innocent explanations —
what genuine concerns remain unexplained?

Step 6 — Reach your verdict:
OVERTURNED: Strong innocent explanation found
            that accounts for primary risk drivers
MODIFIED:   Partial explanation — reduces but
            does not eliminate concern
UPHELD:     Genuinely found no innocent explanation
            after completing all steps above
ESCALATED:  Found new concerns not in original analysis

Do not reach Step 6 without completing Steps 1-5.
Rushing to UPHELD without genuine investigation
defeats the purpose of the Critic Agent.

Output fields:
- verdict: one of UPHELD / OVERTURNED / MODIFIED / ESCALATED
- reasoning: your full adversarial analysis (1-3 sentences)
- innocent_explanations: list of plausible innocent explanations found (empty list if none)
- remaining_concerns: list of concerns that could not be explained innocently (empty list if none)
- original_score: the incoming risk score
- revised_score: the score after your challenge
- confidence_in_challenge: 0-100

You MUST NOT:
- Simply agree without genuine investigation
- Override hard rule violations below score 50
- Express absolute certainty
- Make the final decision — you inform humans

Be genuinely adversarial. If you find nothing, say so clearly. But look hard first."""

    def get_output_schema(self):
        return CriticOutput

    def get_required_context(self, state: FraudPipelineState) -> dict:
        # The Critic sees ALL prior agent outputs — it must challenge the
        # complete picture, not just the raw transaction.
        return {
            "structured_transaction": state.get("structured_transaction", {}),
            "anomaly_report": state.get("anomaly_report", {}),
            "rule_violations": state.get("rule_violations", {}),
            "risk_score": state.get("risk_score", 0),
            "risk_level": state.get("risk_level", ""),
            "risk_reasoning": state.get("risk_reasoning", ""),
        }

    def get_allowed_state_writes(self) -> list[str]:
        # Broad list so schema fields (verdict, original_score, revised_score,
        # confidence_in_challenge) pass the base filter. The run() override
        # assembles them into critic_review and adds final_risk_score/level.
        return [
            "critic_review", "final_risk_score", "final_risk_level",
            "verdict", "original_score", "revised_score",
            "innocent_explanations", "remaining_concerns",
            "reasoning", "confidence_in_challenge",
            "evidence_cited", "loop_count",
        ]

    def run(self, state: FraudPipelineState) -> dict:
        # Step 1: Invoke LLM via base agent. Returns schema fields that match
        # the allowed writes list: verdict, original_score, revised_score,
        # confidence_in_challenge (plus any others that happen to match).
        result = super().run(state)

        # Step 2: Assemble critic_review.
        # super().run() returns a flat dict of schema fields; critic_review
        # is not a schema field, so result.get("critic_review", {}) is empty.
        # The "fallback for schema mapping differences" uses result itself.
        critic_review = result.get("critic_review", {})
        if not critic_review:
            critic_review = dict(result)

        # Step 3: Extract revised score, defaulting to the incoming risk_score.
        revised_score = critic_review.get(
            "revised_score", state.get("risk_score", 0)
        )

        # Step 4: Apply constitutional policy — Policy 5 (Hard Rule Finality).
        # No reasoning, however compelling, can clear a rule violation below 50.
        rule_violations = (
            state.get("rule_violations", {}) or {}
        ).get("violations", [])
        if rule_violations and revised_score < MINIMUM_SCORE_WITH_RULE_VIOLATION:
            revised_score = MINIMUM_SCORE_WITH_RULE_VIOLATION
            if isinstance(critic_review, dict):
                critic_review["revised_score"] = revised_score
                existing = critic_review.get("reasoning", "")
                critic_review["reasoning"] = (
                    existing
                    + f" [Constitutional policy: minimum score "
                    f"{MINIMUM_SCORE_WITH_RULE_VIOLATION} "
                    f"when rule violations exist]"
                )

        # Step 5 & 6: Map final scores and return.
        final_level = _score_to_level(revised_score)
        return {
            "critic_review": critic_review,
            "final_risk_score": revised_score,
            "final_risk_level": final_level,
        }
