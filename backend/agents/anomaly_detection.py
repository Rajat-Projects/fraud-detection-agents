"""
Anomaly Detection Agent — behavioral deviation analysis, LLM-backed.

Scope:
    Identify patterns in THIS transaction that deviate from THIS customer's
    established history. Nothing more. No rule application, no risk score,
    no final verdict.

Context constraint:
    This agent only sees structured_transaction and customer_history. It
    does NOT see rule_violations, risk_score, or critic_review. This is
    intentional — behavioral anomaly reasoning must be independent of
    compliance rules and downstream verdicts to avoid circular reasoning.

Output stored as anomaly_report in state. The base agent's fallback-wrap
stores the entire AnomalyDetectionOutput dict under the "anomaly_report"
key since the schema field names don't match the state write key.
"""

from agents.base_agent import BaseAgent
from models.schemas import AnomalyDetectionOutput
from pipeline.state import FraudPipelineState


class AnomalyDetectionAgent(BaseAgent):

    def __init__(self):
        super().__init__("anomaly_detection", "1.0.0")

    def get_system_prompt(self) -> str:
        return """You are a behavioral anomaly detection specialist.
Your ONLY job: identify patterns in this transaction that deviate from
the customer's established history.

For EACH anomaly you find, assess:
- Which dimension deviates (amount, location, time, merchant_type, velocity)
- How severely it deviates (LOW/MEDIUM/HIGH/CRITICAL)
- What specific evidence from history supports this

You MUST:
- Compare against THIS customer's specific history
- Flag multiple simultaneous anomalies — they amplify risk
- Set confidence based on quality of history data
- Provide specific evidence for each flag

You MUST NOT:
- Make a final fraud verdict
- Assign a risk score
- Recommend any action (approve/block/review)
- Apply compliance rules — that is another agent's job
- Express absolute certainty"""

    def get_output_schema(self):
        return AnomalyDetectionOutput

    def get_required_context(self, state: FraudPipelineState) -> dict:
        # Context constraint: behavioral analysis needs only the transaction
        # and the customer's own history. Rule violations, risk scores, and
        # critic reviews are intentionally excluded to prevent reasoning loops.
        return {
            "structured_transaction": state.get("structured_transaction", {}),
            "customer_history": state.get(
                "structured_transaction", {}
            ).get("customer_history", {}),
        }

    def get_allowed_state_writes(self) -> list[str]:
        return ["anomaly_report"]
