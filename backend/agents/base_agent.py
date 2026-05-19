"""
Abstract base class for all LLM-backed agents in the fraud detection pipeline.

What BaseAgent is:
    A structural contract that every LLM agent must satisfy. It is not a
    convenience class — it is a compliance mechanism. Any agent that inherits
    from BaseAgent is forced to declare its role (get_system_prompt), its
    output shape (get_output_schema), what state it reads (get_required_context),
    and what state it writes (get_allowed_state_writes). Omitting any of these
    causes a TypeError at class definition time, not at runtime during a demo.

Why abstract methods enforce contracts:
    Prompt-based constraints ("please only write to your fields") can be
    bypassed or forgotten. Abstract methods cannot — Python itself enforces
    them. A new agent that doesn't declare its write scope simply cannot be
    instantiated. This is the same principle as extra='forbid' on Pydantic
    schemas: structural enforcement beats instructional enforcement every time.

The configuration drift problem it solves:
    Without BaseAgent, each agent would call ChatGoogleGenerativeAI()
    independently, risking different temperature values, different models,
    or missing API keys across agents. A single _initialize_llm() method
    means changing LLM_CONFIG in settings.py propagates to all 5 LLM agents
    simultaneously. No agent can silently use temperature=0.7 while others
    use 0.1 — the configuration is owned in one place.

Why run() is not abstract:
    The execution sequence (start → build prompt → invoke LLM → filter writes
    → log → return) is identical for every LLM agent. Making it abstract would
    require each agent to re-implement the same boilerplate, creating seven
    opportunities for subtle differences in error handling, logging, or write
    filtering. Inheriting the concrete run() means that sequence is tested once
    and guaranteed for all agents.

    NOTE: Rule Enforcement and Guardrail agents do NOT inherit from BaseAgent
    because they have no LLM. They are plain Python classes with their own
    run() implementations.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from config.settings import GEMINI_API_KEY, LLM_CONFIG
from pipeline.state import FraudPipelineState
from utils.logger import FraudPipelineLogger
from utils.prompt_builder import build_secure_prompt


class BaseAgent(ABC):

    def __init__(self, agent_name: str, agent_version: str = "1.0.0"):
        self.agent_name = agent_name
        self.agent_version = agent_version
        self.logger = FraudPipelineLogger(agent_name)
        self.llm = self._initialize_llm()

    def _initialize_llm(self) -> ChatGoogleGenerativeAI:
        # Single initialization point — change LLM_CONFIG in settings.py
        # to update all agents.
        return ChatGoogleGenerativeAI(
            model=LLM_CONFIG["model"],
            temperature=LLM_CONFIG["temperature"],
            max_output_tokens=LLM_CONFIG["max_output_tokens"],
            google_api_key=GEMINI_API_KEY,
        )

    # ------------------------------------------------------------------
    # Abstract interface — every LLM agent must implement all four
    # ------------------------------------------------------------------

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Define agent role, constraints, and instructions."""

    @abstractmethod
    def get_output_schema(self) -> type[BaseModel]:
        """Return the Pydantic schema class for this agent's output."""

    @abstractmethod
    def get_required_context(self, state: FraudPipelineState) -> dict:
        """Return ONLY the state fields this agent needs.
        Context constraint — agents see only what they need."""

    @abstractmethod
    def get_allowed_state_writes(self) -> list[str]:
        """Return list of state field names this agent can write.
        Write restriction — enforced in run()."""

    # ------------------------------------------------------------------
    # Concrete execution sequence — inherited as-is by all LLM agents
    # ------------------------------------------------------------------

    def run(self, state: FraudPipelineState) -> dict:
        start_time = datetime.now(timezone.utc)

        self.logger.log_agent_start(
            self.agent_name,
            state.get("transaction_ref", ""),
        )

        try:
            agent_context = self.get_required_context(state)

            prompt = build_secure_prompt(
                agent_role=self.agent_name,
                agent_instructions=self.get_system_prompt(),
                data=str(agent_context),
            )

            structured_llm = self.llm.with_structured_output(
                self.get_output_schema()
            )

            result = structured_llm.invoke(prompt)
            result_dict = result.model_dump()

            allowed = self.get_allowed_state_writes()
            safe_output = {k: v for k, v in result_dict.items() if k in allowed}

            # Fallback wrap: when no schema field names match the allowed write
            # keys (e.g. AnomalyDetectionOutput fields vs allowed key
            # "anomaly_report"), store the entire schema output under the single
            # allowed key. This handles agents whose Pydantic schema represents
            # the *content* of one state field rather than a flat state patch.
            if not safe_output and len(allowed) == 1:
                safe_output = {allowed[0]: result_dict}

            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            self.logger.log_agent_complete(
                self.agent_name,
                duration_ms=duration_ms,
                success=True,
            )

            return safe_output

        except Exception as e:
            # Log error TYPE only — never the message. Exception messages can
            # contain PII, stack frames, or partial LLM output.
            self.logger.log_agent_error(self.agent_name, type(e).__name__)
            raise
