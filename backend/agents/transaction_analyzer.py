"""
Transaction Analyzer Agent — converts any input format into a structured dict.

Two input paths, one output shape:
  JSON path  — structured JSON from a bank system. No LLM needed. Pure
               Python validation and field mapping. Deterministic.
  Text path  — plain English description. LLM extracts fields.

All downstream agents receive the same structured_transaction dict regardless
of which path was used. They are completely unaware of input format — adding
a new format is a one-file change.

PII tokenization runs BEFORE any LLM sees data. The token_map (real values)
is stored in state but NEVER passed to any LLM agent in get_required_context.
"""

import json

from agents.base_agent import BaseAgent
from models.schemas import TransactionAnalyzerOutput
from pipeline.state import FraudPipelineState
from security.pii_handler import PIIHandler
from utils.prompt_builder import build_secure_prompt

_pii_handler = PIIHandler()


class TransactionAnalyzerAgent(BaseAgent):

    def __init__(self):
        super().__init__("transaction_analyzer", "1.0.0")

    def get_system_prompt(self) -> str:
        return """You are a transaction data structuring specialist.
Your ONLY job: convert transaction descriptions into structured JSON data.

You MUST:
- Extract every available field from the input
- Set confidence levels: HIGH for exact values,
  MEDIUM for inferred values, LOW for uncertain values
- List all fields you could not find in missing_fields
- Never invent information not present in the input
- Set is_parseable=False if input is not a transaction

You MUST NOT:
- Make any fraud assessment
- Draw conclusions about risk or suspicion
- Recommend any action
- Add information beyond what is in the input"""

    def get_output_schema(self):
        return TransactionAnalyzerOutput

    def get_required_context(self, state: FraudPipelineState) -> dict:
        # raw_input is already tokenized by the time this is called
        return {"transaction_input": state.get("raw_input", "")}

    def get_allowed_state_writes(self) -> list[str]:
        return ["structured_transaction"]

    # ------------------------------------------------------------------
    # run() override — adds PII tokenization and format routing
    # ------------------------------------------------------------------

    def run(self, state: FraudPipelineState) -> dict:
        raw_input = state.get("raw_input", "")

        # Attempt structured JSON detection first
        try:
            data = json.loads(raw_input)
            if isinstance(data, dict) and (
                "amount" in data or "transaction_id" in data
            ):
                return self._process_structured_json(raw_input)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        return self._process_unstructured_text(state)

    # ------------------------------------------------------------------
    # JSON path — deterministic, no LLM
    # ------------------------------------------------------------------

    def _process_structured_json(self, json_str: str) -> dict:
        """
        Parse production JSON from a bank core system.

        No LLM needed — field mapping is deterministic. Both paths produce
        an identical structured_transaction shape; downstream agents cannot
        distinguish JSON input from text input.
        """
        data = json.loads(json_str)
        merchant = data.get("merchant", {}) or {}

        return {
            "structured_transaction": {
                "amount": data.get("amount"),
                "amount_confidence": "HIGH",
                "currency": data.get("currency", "USD"),
                "merchant_name": merchant.get("name"),
                "merchant_category": merchant.get("category_name"),
                "location_country": merchant.get("country"),
                "location_city": merchant.get("city"),
                "transaction_time": data.get("timestamp"),
                "time_confidence": "EXACT",
                "customer_history": data.get("customer_history", {}),
                "network_signals": data.get("network_signals", {}),
                "missing_fields": [],
                "parsing_notes": "Structured JSON input",
                "is_parseable": True,
                "data_source": "STRUCTURED_JSON",
            }
        }

    # ------------------------------------------------------------------
    # Text path — LLM extracts fields
    # ------------------------------------------------------------------

    def _process_unstructured_text(self, state: FraudPipelineState) -> dict:
        """
        Extract transaction fields from plain text via LLM.

        PII tokenization runs first — the LLM only ever sees tokens, never
        real card numbers, emails, or account numbers. token_map stays in
        state for Report Generator output masking only.
        """
        # Step 1 & 2: Tokenize PII, update state
        tokenized, token_map = _pii_handler.detect_and_tokenize(
            state.get("raw_input", "")
        )
        state["raw_input"] = tokenized
        state["token_map"] = token_map

        # Build prompt and invoke LLM directly so we can wrap the output
        # under structured_transaction (schema fields ≠ state field name)
        context = self.get_required_context(state)
        prompt = build_secure_prompt(
            agent_role=self.agent_name,
            agent_instructions=self.get_system_prompt(),
            data=str(context),
        )
        structured_llm = self.llm.with_structured_output(TransactionAnalyzerOutput)
        result = structured_llm.invoke(prompt)

        structured_tx = result.model_dump()
        structured_tx["data_source"] = "TEXT_EXTRACTION"

        return {"structured_transaction": structured_tx}
