"""
Report Generator Agent — translate pipeline outputs into a 60-second analyst report.

Role: TRANSLATOR and FORMATTER only.

This agent does not add analysis, does not change scores, and does not introduce
its own risk assessment. It converts what every prior agent produced into a report
a fraud analyst can read and act on in 60 seconds.

PII masking:
    token_map is retrieved from state (where it has lived safely since the
    Transaction Analyzer ran) and applied to all string fields in the report.
    This is the only agent that is permitted to touch token_map — it is used
    solely to replace tokens with partially-masked real values for the analyst.
    The raw values are never written to state or logs.

run() override:
    super().run(state) triggers the fallback-wrap in BaseAgent because no
    ReportGeneratorOutput schema field names match the single allowed write key
    "final_report". The full schema output is stored as {"final_report": {...}}.
    The override then applies PII masking and adds a generated_at timestamp.
"""

from datetime import datetime, timezone

from agents.base_agent import BaseAgent
from models.schemas import ReportGeneratorOutput
from pipeline.state import FraudPipelineState
from security.pii_handler import PIIHandler

_pii_handler = PIIHandler()


class ReportGeneratorAgent(BaseAgent):

    def __init__(self):
        super().__init__("report_generator", "1.0.0")

    def get_system_prompt(self) -> str:
        return """You are a report formatting specialist.
You are a TRANSLATOR and FORMATTER — not an analyst.

Your job: convert agent outputs into a clear report that a fraud analyst
can read and act on in 60 seconds.

You MUST:
- Accurately represent what each agent concluded
- Write in plain English — no technical jargon
- Maintain the final risk score EXACTLY as given — do not change it under any circumstances
- Include specific questions for the human analyst to consider before taking any action
- List concrete next steps for the analyst
- Flag any incomplete analysis clearly in missing_analysis field
- Set reliability based on pipeline completeness:
  COMPLETE: all agents ran successfully
  DEGRADED: some agents used fallback
  INCOMPLETE: some agents failed entirely

You MUST NOT:
- Add your own risk assessment
- Change any score or verdict
- Use action language like block or freeze
- Express false certainty
- Include unmasked PII

Keep executive_summary to 2-3 sentences maximum.
The analyst needs the key facts, not an essay."""

    def get_output_schema(self):
        return ReportGeneratorOutput

    def get_required_context(self, state: FraudPipelineState) -> dict:
        # Report Generator summarizes everything — it is the only agent that
        # sees the full pipeline picture. token_map is intentionally excluded;
        # PII masking is applied in the run() override after LLM output is
        # produced, not by passing token_map into the LLM context.
        return {
            "structured_transaction": state.get("structured_transaction", {}),
            "anomaly_report": state.get("anomaly_report", {}),
            "rule_violations": state.get("rule_violations", {}),
            "risk_score": state.get("risk_score", 0),
            "risk_reasoning": state.get("risk_reasoning", ""),
            "critic_review": state.get("critic_review", {}),
            "final_risk_score": state.get("final_risk_score", 0),
            "final_risk_level": state.get("final_risk_level", ""),
            "incomplete_agents": state.get("incomplete_agents", []),
            "agent_statuses": state.get("agent_statuses", {}),
        }

    def get_allowed_state_writes(self) -> list[str]:
        return ["final_report"]

    def run(self, state: FraudPipelineState) -> dict:
        # Step 1: super().run() triggers the fallback-wrap because no
        # ReportGeneratorOutput field names match "final_report".
        # Returns {"final_report": {transaction_summary: ..., ...}}
        result = super().run(state)

        # Step 2–3: Apply PII masking to all string fields in the report.
        token_map = state.get("token_map", {})
        if token_map and "final_report" in result:
            report = result["final_report"]
            for key, value in list(report.items()):
                if isinstance(value, str):
                    report[key] = _pii_handler.mask_for_output(value, token_map)
                elif isinstance(value, list):
                    report[key] = [
                        _pii_handler.mask_for_output(item, token_map)
                        if isinstance(item, str) else item
                        for item in value
                    ]

        # Step 4: Timestamp when this report was generated.
        if "final_report" in result:
            result["final_report"]["generated_at"] = (
                datetime.now(timezone.utc).isoformat()
            )

        return result
