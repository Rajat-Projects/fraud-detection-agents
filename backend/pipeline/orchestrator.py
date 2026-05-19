"""
Pipeline orchestrator — routing logic, failure handling, and guardrail wrapping.

Key design decisions:

1. Routing functions are PURE — they read state but do not mutate it.
   LangGraph 1.x does not persist routing function state mutations: the state
   snapshot passed to a routing function is not checkpointed after the function
   returns. All state updates must come from node return values.

2. critic_loop_count increment happens in make_agent_node for the critic, not
   in route_after_critic. This is the only place where the increment actually
   persists in the LangGraph checkpoint.

3. Guardrail wraps every agent node (pre + post). A CRITICAL pre-check flag
   halts the pipeline before the agent runs. A CRITICAL post-check flag is
   appended but the pipeline continues (the agent has already run — the flag
   surfaces in the report for the analyst).

4. handle_agent_failure applies the Rule Enforcement fallback (critical rules
   only) when that specific agent fails. All other agent failures mark the
   pipeline as INCOMPLETE and continue — a degraded report is better than no
   report.
"""

import time
from datetime import datetime, timezone

from agents.critic import _score_to_level
from agents.guardrail import GuardrailAgent
from agents.rule_enforcement import RuleEnforcementAgent
from config.constitutional_policies import MAX_CRITIC_LOOPS
from pipeline.state import FraudPipelineState, checkpoint_state
from utils.logger import FraudPipelineLogger

_guardrail = GuardrailAgent()
_rule_agent = RuleEnforcementAgent()
_logger = FraudPipelineLogger("orchestrator")


# ---------------------------------------------------------------------------
# Routing functions — pure reads, no state mutations
# ---------------------------------------------------------------------------

def route_after_guardrail(state: FraudPipelineState) -> str:
    """Route to security_halt if any guardrail flag is CRITICAL, else continue."""
    for flag in state.get("guardrail_flags", []):
        if flag.get("severity") == "CRITICAL":
            return "security_halt"
    return "transaction_analyzer"


def route_after_critic(state: FraudPipelineState) -> str:
    """
    Route OVERTURNED verdicts back to Risk Scoring for re-evaluation,
    up to MAX_CRITIC_LOOPS times. All other verdicts proceed to the report.

    NOTE: The loop count increment happens in make_agent_node (not here)
    because LangGraph routing function mutations are not checkpointed.
    """
    critic_review = state.get("critic_review", {})
    loop_count = state.get("critic_loop_count", 0)

    if (
        critic_review.get("verdict") == "OVERTURNED"
        and loop_count < MAX_CRITIC_LOOPS
    ):
        return "risk_scoring"
    return "report_generator"


# ---------------------------------------------------------------------------
# Terminal nodes
# ---------------------------------------------------------------------------

def security_halt_node(state: FraudPipelineState) -> dict:
    """
    Produce a minimal final report when the pipeline is halted by the Guardrail.
    Called when any CRITICAL guardrail flag is detected on pipeline input or
    during a pre-agent check.
    """
    critical_flags = [
        f for f in state.get("guardrail_flags", [])
        if f.get("severity") == "CRITICAL"
    ]
    key_findings = [
        f.get("description", "Security violation detected")
        for f in critical_flags
    ]

    _logger.log_guardrail_flag(
        "SECURITY_HALT", "CRITICAL", "pipeline_input", "PIPELINE_HALTED"
    )

    return {
        "final_report": {
            "executive_summary": (
                "Pipeline halted — security violation detected in input."
            ),
            "final_risk_level": "HIGH",
            "final_risk_score": 100,
            "recommended_action": "REVIEW",
            "reliability": "INCOMPLETE",
            "analyst_questions": [
                "Review the guardrail flags below",
                "Determine if this is a legitimate input or attack attempt",
                "Do not process without manual review",
            ],
            "key_findings": key_findings or ["Security violation — no details available"],
            "next_steps": ["Manual review required"],
            "transaction_summary": "Blocked at security boundary",
            "missing_analysis": ["All agents — pipeline halted"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "pipeline_halted": True,
        "final_risk_score": 100,
        "final_risk_level": "HIGH",
    }


# ---------------------------------------------------------------------------
# Failure handler
# ---------------------------------------------------------------------------

def handle_agent_failure(
    state: FraudPipelineState,
    agent_name: str,
    error: Exception,
) -> dict:
    """
    Handle agent failure according to the fallback hierarchy.

    Rule Enforcement failure → apply critical rules only, mark FALLBACK.
    All other failures → mark FAILED, add to incomplete_agents, continue.
    """
    _logger.log_agent_error(agent_name, type(error).__name__)
    state["agent_statuses"][agent_name] = "FAILED"

    if agent_name == "rule_enforcement":
        try:
            fallback_result = _rule_agent.run_fallback(state)
            state["agent_statuses"]["rule_enforcement"] = "FALLBACK"
            return fallback_result
        except Exception as fallback_err:
            _logger.log_agent_error("rule_enforcement_fallback", type(fallback_err).__name__)
            state["incomplete_agents"].append(agent_name)
            return {}

    state["incomplete_agents"].append(agent_name)
    return {}


# ---------------------------------------------------------------------------
# Guardrail-wrapped node factory
# ---------------------------------------------------------------------------

def make_agent_node(agent, agent_name: str):
    """
    Wrap an agent with guardrail pre/post checks, failure handling,
    and state checkpointing. Returns a LangGraph-compatible node function.
    """

    def node_fn(state: FraudPipelineState) -> dict:
        # 1. Pre-agent guardrail check
        pre_flags = _guardrail.pre_agent_check(
            agent_name,
            {"context": state.get("raw_input", "")},
            state,
        )
        state["guardrail_flags"] = state.get("guardrail_flags", []) + pre_flags

        # 2. Halt if pre-check raised CRITICAL
        if _guardrail.should_halt_pipeline(pre_flags):
            halt_result = security_halt_node(state)
            state.update(halt_result)
            return dict(state)

        # 3. Run agent with rate-limit retry, fall back on final failure
        _MAX_RETRIES = 2
        _last_exc = None
        for _attempt in range(_MAX_RETRIES + 1):
            try:
                result = agent.run(state)
                state.update(result)
                state["agent_statuses"][agent_name] = "SUCCESS"
                _last_exc = None
                break
            except Exception as e:
                _last_exc = e
                err_str = str(e)
                is_rate_limit = (
                    "429" in err_str
                    or "RESOURCE_EXHAUSTED" in err_str
                    or "rate" in err_str.lower()
                )
                if is_rate_limit and _attempt < _MAX_RETRIES:
                    _delay = 5 * (2 ** _attempt)  # 5s, 10s
                    _logger.log_guardrail_flag(
                        "RATE_LIMIT_RETRY", "WARNING", agent_name,
                        f"retry_{_attempt + 1}_in_{_delay}s"
                    )
                    time.sleep(_delay)
                    continue
                break  # non-rate-limit error or retries exhausted
        if _last_exc is not None:
            failure_result = handle_agent_failure(state, agent_name, _last_exc)
            state.update(failure_result)

        # 4. Critic loop count — must be incremented here, not in the routing
        #    function, because LangGraph does not checkpoint routing mutations.
        if agent_name == "critic":
            critic_review = state.get("critic_review", {})
            if critic_review.get("verdict") == "OVERTURNED":
                state["critic_loop_count"] = state.get("critic_loop_count", 0) + 1

        # 5. Post-agent guardrail check
        post_flags = _guardrail.post_agent_check(
            agent_name,
            state.get(
                # Check the primary output field for this agent
                _AGENT_OUTPUT_FIELD.get(agent_name, "final_report"), {}
            ),
            state,
        )
        state["guardrail_flags"] = state.get("guardrail_flags", []) + post_flags

        # 6. Tamper-evident checkpoint
        state = checkpoint_state(state, agent_name)

        return dict(state)

    node_fn.__name__ = f"{agent_name}_node"
    return node_fn


# Primary output field per agent — used for targeted post-agent PII checks
_AGENT_OUTPUT_FIELD = {
    "transaction_analyzer": "structured_transaction",
    "anomaly_detection": "anomaly_report",
    "rule_enforcement": "rule_violations",
    "risk_scoring": "risk_reasoning",
    "critic": "critic_review",
    "report_generator": "final_report",
}
