"""
Shared pipeline state for the multi-agent fraud detection system.

Why TypedDict over plain dict:
    TypedDict gives static type checking (mypy, pyright, IDE autocomplete)
    with zero runtime overhead — it is a plain dict at runtime. This means
    LangGraph's graph execution and Python's json.dumps() both work on it
    without adapters, while editors catch field-name typos at write time
    rather than at runtime during a live demo.

Why token_map is excluded from checkpointing:
    token_map contains real PII values (the originals behind each token).
    Hashing it would serialize PII into the checkpoint record, which could
    then appear in logs, audit trails, or error messages. Excluding it from
    the hash means the tamper-evidence guarantee covers all business logic
    fields (scores, verdicts, flags) without exposing PII in derived data.
    token_map itself is never passed to any LLM agent — it stays at the
    pipeline boundary and is only used by the Report Generator for output
    masking.

Grow-only principle:
    State fields are set once by the agent responsible for them and never
    removed or reset by downstream agents. This ensures that any agent can
    read any previously-written field safely and that the audit trail
    (via state_checkpoints) reflects a monotonically growing record of
    what each agent contributed.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import TypedDict


class FraudPipelineState(TypedDict):
    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    raw_input: str
    transaction_ref: str

    # ------------------------------------------------------------------
    # After Transaction Analyzer
    # ------------------------------------------------------------------
    structured_transaction: dict
    token_map: dict  # NEVER PASS TO LLM AGENTS

    # ------------------------------------------------------------------
    # After Anomaly Detection
    # ------------------------------------------------------------------
    anomaly_report: dict

    # ------------------------------------------------------------------
    # After Rule Enforcement
    # ------------------------------------------------------------------
    rule_violations: dict

    # ------------------------------------------------------------------
    # After Risk Scoring
    # ------------------------------------------------------------------
    risk_score: int
    risk_level: str
    recommended_action: str
    risk_reasoning: str

    # ------------------------------------------------------------------
    # After Critic
    # ------------------------------------------------------------------
    critic_review: dict
    final_risk_score: int
    final_risk_level: str
    critic_loop_count: int

    # ------------------------------------------------------------------
    # After Report Generator
    # ------------------------------------------------------------------
    final_report: dict

    # ------------------------------------------------------------------
    # Cross-cutting — updated throughout pipeline
    # ------------------------------------------------------------------
    guardrail_flags: list
    pipeline_halted: bool
    halt_reason: str

    # ------------------------------------------------------------------
    # Pipeline metadata
    # ------------------------------------------------------------------
    agent_statuses: dict        # agent_name -> "SUCCESS" | "FALLBACK" | "FAILED"
    incomplete_agents: list
    state_checkpoints: dict     # agent_name -> SHA-256 hex string
    pipeline_start_time: str


def create_initial_state(
    raw_input: str,
    transaction_ref: str,
) -> FraudPipelineState:
    """
    Return a fully-initialised state with safe defaults for every field.

    All mutable defaults (dicts, lists) are fresh instances — never shared
    across calls. pipeline_start_time is set to UTC ISO-8601 at call time.
    """
    return FraudPipelineState(
        # Input
        raw_input=raw_input,
        transaction_ref=transaction_ref,
        # Transaction Analyzer
        structured_transaction={},
        token_map={},
        # Anomaly Detection
        anomaly_report={},
        # Rule Enforcement
        rule_violations={},
        # Risk Scoring
        risk_score=0,
        risk_level="",
        recommended_action="",
        risk_reasoning="",
        # Critic
        critic_review={},
        final_risk_score=0,
        final_risk_level="",
        critic_loop_count=0,
        # Report Generator
        final_report={},
        # Cross-cutting
        guardrail_flags=[],
        pipeline_halted=False,
        halt_reason="",
        # Metadata
        agent_statuses={},
        incomplete_agents=[],
        state_checkpoints={},
        pipeline_start_time=datetime.now(timezone.utc).isoformat(),
    )


def checkpoint_state(
    state: FraudPipelineState,
    agent_name: str,
) -> FraudPipelineState:
    """
    Hash the current state and store the result under agent_name.

    Excluded from hashing:
      state_checkpoints  — would create a circular reference (the hash of the
                           hash map cannot include itself).
      token_map          — contains real PII values; must not be serialized
                           into any derived record (see module docstring).
      pipeline_start_time — timing metadata, not business logic. Two states
                           with identical business logic but created milliseconds
                           apart must produce the same hash so that token_map
                           exclusion tests (and similar) are deterministic. The
                           audit trail already records the timestamp independently.

    sort_keys=True is required for reproducibility: Python dicts preserve
    insertion order but that order can differ between agents or Python
    versions. Sorting ensures the same logical state always produces the
    same hash regardless of how the dict was constructed.

    default=str handles datetime objects, Pydantic models, or any other
    non-JSON-serializable value that might appear in agent outputs, so
    the checkpoint never crashes on unexpected types.
    """
    checkpoint_data = {
        k: v
        for k, v in state.items()
        if k not in ("state_checkpoints", "token_map", "pipeline_start_time")
    }
    serialized = json.dumps(checkpoint_data, sort_keys=True, default=str).encode()
    state["state_checkpoints"][agent_name] = hashlib.sha256(serialized).hexdigest()
    return state
