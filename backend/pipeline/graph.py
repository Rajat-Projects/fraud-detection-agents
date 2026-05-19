"""
LangGraph pipeline definition for the fraud detection system.

build_pipeline() constructs the compiled graph each time it is called.
run_fraud_analysis() is the single public entry point — it creates initial
state, builds the pipeline, invokes it, and returns the final state dict.

Graph topology:
    guardrail_input
        ├── (CRITICAL) → security_halt → END
        └── (clean)    → transaction_analyzer
                             → anomaly_detection
                               → rule_enforcement
                                 → risk_scoring
                                   → critic
                                       ├── (OVERTURNED, loops < 2) → risk_scoring
                                       └── (otherwise)             → report_generator → END
"""

import uuid
from datetime import datetime, timezone

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.anomaly_detection import AnomalyDetectionAgent
from agents.critic import CriticAgent
from agents.report_generator import ReportGeneratorAgent
from agents.risk_scoring import RiskScoringAgent
from agents.rule_enforcement import RuleEnforcementAgent
from agents.transaction_analyzer import TransactionAnalyzerAgent
from pipeline.orchestrator import (
    _guardrail,
    make_agent_node,
    route_after_critic,
    route_after_guardrail,
    security_halt_node,
)
from pipeline.state import FraudPipelineState, create_initial_state
from utils.logger import FraudPipelineLogger

_logger = FraudPipelineLogger("graph")


def build_pipeline():
    """
    Instantiate all agents, build the LangGraph, and compile with MemorySaver.

    Returns a compiled LangGraph app ready for invoke().
    MemorySaver enables per-thread state checkpointing — each transaction
    gets its own thread_id and isolated state history.
    """
    analyzer = TransactionAnalyzerAgent()
    anomaly = AnomalyDetectionAgent()
    rules = RuleEnforcementAgent()
    risk = RiskScoringAgent()
    critic = CriticAgent()
    reporter = ReportGeneratorAgent()

    graph = StateGraph(FraudPipelineState)

    # ------------------------------------------------------------------
    # Guardrail input node — boundary check before any agent runs
    # ------------------------------------------------------------------
    def guardrail_input_node(state: FraudPipelineState) -> dict:
        flags = _guardrail.pre_agent_check(
            "pipeline_input",
            {"raw_input": state.get("raw_input", "")},
            state,
        )
        return {
            "guardrail_flags": state.get("guardrail_flags", []) + flags
        }

    # ------------------------------------------------------------------
    # Node registration
    # ------------------------------------------------------------------
    graph.add_node("guardrail_input", guardrail_input_node)
    graph.add_node("security_halt", security_halt_node)
    graph.add_node("transaction_analyzer", make_agent_node(analyzer, "transaction_analyzer"))
    graph.add_node("anomaly_detection", make_agent_node(anomaly, "anomaly_detection"))
    graph.add_node("rule_enforcement", make_agent_node(rules, "rule_enforcement"))
    graph.add_node("risk_scoring", make_agent_node(risk, "risk_scoring"))
    graph.add_node("critic", make_agent_node(critic, "critic"))
    graph.add_node("report_generator", make_agent_node(reporter, "report_generator"))

    # ------------------------------------------------------------------
    # Entry point and edges
    # ------------------------------------------------------------------
    graph.set_entry_point("guardrail_input")

    graph.add_conditional_edges(
        "guardrail_input",
        route_after_guardrail,
        {
            "security_halt": "security_halt",
            "transaction_analyzer": "transaction_analyzer",
        },
    )

    graph.add_edge("transaction_analyzer", "anomaly_detection")
    graph.add_edge("anomaly_detection", "rule_enforcement")
    graph.add_edge("rule_enforcement", "risk_scoring")
    graph.add_edge("risk_scoring", "critic")

    graph.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "risk_scoring": "risk_scoring",
            "report_generator": "report_generator",
        },
    )

    graph.add_edge("report_generator", END)
    graph.add_edge("security_halt", END)

    return graph.compile(checkpointer=MemorySaver())


def run_fraud_analysis(transaction_input: str) -> dict:
    """
    Entry point for a single fraud analysis run.

    Creates a fresh transaction reference, initialises state, builds the
    pipeline, invokes it, logs completion, and returns the final state.

    Args:
        transaction_input: Raw transaction text or JSON string.

    Returns:
        Final FraudPipelineState dict with all agent outputs and final_report.
    """
    transaction_ref = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    state = create_initial_state(transaction_input, transaction_ref)

    pipeline = build_pipeline()
    config = {"configurable": {"thread_id": transaction_ref}}

    _logger.log_agent_start("pipeline", transaction_ref)

    result = pipeline.invoke(state, config=config)

    reliability = "UNKNOWN"
    risk_level = result.get("final_risk_level", "UNKNOWN")
    if isinstance(result.get("final_report"), dict):
        reliability = result["final_report"].get("reliability", "UNKNOWN")

    duration_ms = (
        datetime.now(timezone.utc)
        - datetime.fromisoformat(result.get("pipeline_start_time", datetime.now(timezone.utc).isoformat()))
    ).total_seconds() * 1000

    _logger.log_pipeline_complete(
        duration_ms=duration_ms,
        reliability=reliability,
        risk_level=risk_level,
    )

    # Remove token_map before returning — it contains real PII values (the
    # originals behind each token). It must never leave the pipeline boundary,
    # appear in an API response, or be serialised into any log or audit record.
    result.pop("token_map", None)

    return result
