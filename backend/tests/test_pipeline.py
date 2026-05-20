"""
Pipeline integration tests.

Tier 1 — Routing tests (no LLM needed): verify graph routing logic
Tier 2 — Integration tests (@pytest.mark.llm): require Gemini API key

Run without API key:
    pytest tests/test_pipeline.py -v -m "not llm"

Run full suite (needs key):
    pytest tests/test_pipeline.py -v
"""

import sys

import pytest

sys.path.insert(0, ".")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "llm: marks tests requiring LLM API access (deselect with -m 'not llm')",
    )


# ---------------------------------------------------------------------------
# Routing tests — pure logic, no LLM
# ---------------------------------------------------------------------------

class TestPipelineRouting:

    def setup_method(self):
        from pipeline.orchestrator import (
            route_after_critic,
            route_after_guardrail,
            security_halt_node,
        )
        from pipeline.state import create_initial_state
        self.route_after_guardrail = route_after_guardrail
        self.route_after_critic = route_after_critic
        self.security_halt_node = security_halt_node
        self.create_state = create_initial_state

    def test_clean_input_routes_to_analyzer(self):
        state = self.create_state("test", "TXN-001")
        assert self.route_after_guardrail(state) == "transaction_analyzer"

    def test_critical_flag_routes_to_halt(self):
        state = self.create_state("test", "TXN-002")
        state["guardrail_flags"] = [
            {"severity": "CRITICAL", "flag_type": "INJECTION",
             "description": "test", "agent_context": "test"}
        ]
        assert self.route_after_guardrail(state) == "security_halt"

    def test_warning_flag_does_not_halt(self):
        state = self.create_state("test", "TXN-003")
        state["guardrail_flags"] = [
            {"severity": "WARNING", "flag_type": "SCOPE_CREEP",
             "description": "test", "agent_context": "test"}
        ]
        assert self.route_after_guardrail(state) == "transaction_analyzer"

    def test_upheld_routes_to_report(self):
        state = self.create_state("test", "TXN-004")
        state["critic_review"] = {"verdict": "UPHELD"}
        state["critic_loop_count"] = 0
        assert self.route_after_critic(state) == "report_generator"

    def test_modified_routes_to_report(self):
        state = self.create_state("test", "TXN-005")
        state["critic_review"] = {"verdict": "MODIFIED"}
        state["critic_loop_count"] = 0
        assert self.route_after_critic(state) == "report_generator"

    def test_escalated_routes_to_report(self):
        state = self.create_state("test", "TXN-006")
        state["critic_review"] = {"verdict": "ESCALATED"}
        state["critic_loop_count"] = 0
        assert self.route_after_critic(state) == "report_generator"

    def test_overturned_within_limit_loops_to_risk(self):
        state = self.create_state("test", "TXN-007")
        state["critic_review"] = {"verdict": "OVERTURNED"}
        state["critic_loop_count"] = 0
        assert self.route_after_critic(state) == "risk_scoring"

    def test_overturned_at_limit_proceeds_to_report(self):
        from config.constitutional_policies import MAX_CRITIC_LOOPS
        state = self.create_state("test", "TXN-008")
        state["critic_review"] = {"verdict": "OVERTURNED"}
        state["critic_loop_count"] = MAX_CRITIC_LOOPS
        assert self.route_after_critic(state) == "report_generator"

    def test_security_halt_node_sets_halted_true(self):
        state = self.create_state("test", "TXN-009")
        state["guardrail_flags"] = [
            {"severity": "CRITICAL", "flag_type": "INJECTION",
             "description": "Injection detected", "agent_context": "input"}
        ]
        result = self.security_halt_node(state)
        assert result["pipeline_halted"] is True

    def test_security_halt_node_sets_score_100(self):
        state = self.create_state("test", "TXN-010")
        state["guardrail_flags"] = [
            {"severity": "CRITICAL", "flag_type": "INJECTION",
             "description": "test", "agent_context": "test"}
        ]
        result = self.security_halt_node(state)
        assert result["final_risk_score"] == 100
        assert result["final_risk_level"] == "HIGH"

    def test_security_halt_node_produces_final_report(self):
        state = self.create_state("test", "TXN-011")
        state["guardrail_flags"] = [
            {"severity": "CRITICAL", "flag_type": "INJECTION",
             "description": "test", "agent_context": "test"}
        ]
        result = self.security_halt_node(state)
        assert "final_report" in result
        report = result["final_report"]
        assert "executive_summary" in report
        assert "analyst_questions" in report
        assert report["recommended_action"] == "REVIEW"

    def test_pipeline_builds_without_error(self):
        from pipeline.graph import build_pipeline
        pipeline = build_pipeline()
        assert pipeline is not None

    def test_score_to_level_boundaries(self):
        from agents.critic import _score_to_level
        assert _score_to_level(0) == "LOW"
        assert _score_to_level(35) == "LOW"
        assert _score_to_level(36) == "MEDIUM"
        assert _score_to_level(70) == "MEDIUM"
        assert _score_to_level(71) == "HIGH"
        assert _score_to_level(100) == "HIGH"


# ---------------------------------------------------------------------------
# Integration tests — require Gemini API key
# ---------------------------------------------------------------------------

class TestPipelineIntegration:

    @pytest.mark.llm
    def test_legitimate_transaction_scores_low_or_medium(self):
        from pipeline.graph import run_fraud_analysis
        from tests.test_data import TEST_TRANSACTIONS

        result = run_fraud_analysis(TEST_TRANSACTIONS["obvious_legitimate"][0])

        assert result.get("final_risk_level") in ("LOW", "MEDIUM"), (
            f"Expected LOW or MEDIUM, got {result.get('final_risk_level')}"
        )
        assert result.get("final_report", {}).get("reliability") == "COMPLETE"
        assert len(result.get("agent_statuses", {})) == 6

    @pytest.mark.llm
    def test_injection_halts_or_flags_pipeline(self):
        from pipeline.graph import run_fraud_analysis
        from tests.test_data import TEST_TRANSACTIONS

        result = run_fraud_analysis(TEST_TRANSACTIONS["adversarial"][0])

        pipeline_halted = result.get("pipeline_halted", False)
        critical_flags = [
            f for f in result.get("guardrail_flags", [])
            if f.get("severity") == "CRITICAL"
        ]
        assert pipeline_halted or len(critical_flags) > 0, (
            "Injection attempt must either halt pipeline or produce critical flags"
        )

    @pytest.mark.llm
    def test_rule_violation_enforces_minimum_score(self):
        from config.constitutional_policies import MINIMUM_SCORE_WITH_RULE_VIOLATION
        from pipeline.graph import run_fraud_analysis

        result = run_fraud_analysis(
            "Transaction: 15000 dollars electronics purchase. "
            "Regular customer 3 years clean history."
        )

        violations = result.get("rule_violations", {}).get("violations", [])
        final_score = result.get("final_risk_score", 0)

        assert len(violations) >= 1, "High-value transaction must trigger R001"
        assert final_score >= MINIMUM_SCORE_WITH_RULE_VIOLATION, (
            f"Score {final_score} below constitutional floor "
            f"{MINIMUM_SCORE_WITH_RULE_VIOLATION}"
        )

    @pytest.mark.llm
    def test_false_positive_challenged_by_critic(self):
        from pipeline.graph import run_fraud_analysis
        from tests.test_data import TEST_TRANSACTIONS

        result = run_fraud_analysis(TEST_TRANSACTIONS["false_positives"][0])

        critic = result.get("critic_review", {})
        assert critic, "Critic review must be present"
        assert critic.get("verdict") in (
            "UPHELD", "OVERTURNED", "MODIFIED", "ESCALATED"
        ), f"Invalid critic verdict: {critic.get('verdict')}"

    @pytest.mark.llm
    def test_all_agents_produce_checkpoints(self):
        from pipeline.graph import run_fraud_analysis
        from tests.test_data import TEST_TRANSACTIONS

        result = run_fraud_analysis(TEST_TRANSACTIONS["obvious_legitimate"][1])

        checkpoints = result.get("state_checkpoints", {})
        statuses = result.get("agent_statuses", {})
        successful = [k for k, v in statuses.items() if v == "SUCCESS"]

        # Every successful agent should have created a checkpoint
        for agent in successful:
            assert agent in checkpoints, (
                f"Agent {agent} succeeded but has no checkpoint"
            )
