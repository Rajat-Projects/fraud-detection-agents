"""
Inviolable system policies for the fraud detection pipeline.

These constants enforce the five constitutional rules that no agent, no LLM
reasoning, and no pipeline configuration can override. They are imported
directly into agent code and applied in logic — not in prompts — because
prompt constraints can be argued around by LLMs; code constraints cannot.

Constitutional rule summary:
  Policy 1 — No Autonomous Actions: every output is a recommendation to a human.
  Policy 2 — Graduated Response: risk cannot skip levels without intermediate review.
  Policy 3 — Evidence-Based Verdicts: every score must cite specific input evidence.
  Policy 4 — Critic Primacy on False Positives: plausible innocent explanation
             downgrades verdict to minimum MEDIUM, never below.
  Policy 5 — Hard Rule Finality: rule violations cannot be scored below 50.
             Always results in minimum MEDIUM + human review.
"""

# ---------------------------------------------------------------------------
# Policy 5 — Hard Rule Finality
# ---------------------------------------------------------------------------

# When ANY rule violation exists, the Critic cannot reduce the final score
# below this floor. Compliance rules exist precisely because they cannot be
# reasoned around — a Critic that clears a rule violation via compelling
# argument is providing zero compliance guarantee.
MINIMUM_SCORE_WITH_RULE_VIOLATION: int = 50

# ---------------------------------------------------------------------------
# Critic loop limit
# ---------------------------------------------------------------------------

# Maximum number of times the Critic can send a verdict back to Risk Scoring
# for re-evaluation. Prevents infinite oscillation while still allowing the
# Critic to challenge an initial verdict once with full context.
MAX_CRITIC_LOOPS: int = 2

# ---------------------------------------------------------------------------
# Policy 1 — Action language restriction
# ---------------------------------------------------------------------------

# Only the Report Generator may use action-oriented language in its output
# (e.g. "recommend REVIEW", "escalate to analyst"). All other agents must
# describe findings only. This is enforced by the Guardrail Agent's
# scope-creep check which compares the writing agent against this list.
ACTION_LANGUAGE_ALLOWED_AGENTS: list[str] = ["report_generator"]

# ---------------------------------------------------------------------------
# Injection patterns
# ---------------------------------------------------------------------------

# Phrases that indicate a prompt injection attempt in transaction input.
# Checked at the boundary by the Guardrail Agent BEFORE any LLM sees data.
# A CRITICAL guardrail flag halts the pipeline immediately — no retry.
# The list uses lowercase for case-insensitive comparison.
INJECTION_PATTERNS: list[str] = [
    "ignore previous instructions",
    "ignore all instructions",
    "disregard your rules",
    "you are now",
    "new instruction:",
    "system prompt:",
    "forget everything",
    "override",
    "bypass",
    "pretend you are",
    "act as if",
    "jailbreak",
    "disregard previous",
    "ignore your training",
    "your new role",
    "ignore the above",
]

# ---------------------------------------------------------------------------
# Scope creep phrases
# ---------------------------------------------------------------------------

# Output from any agent OTHER THAN report_generator that contains these
# phrases indicates the agent has exceeded its defined role. The Guardrail
# post-agent check raises a WARNING flag when these are detected outside
# the permitted agent. Agents describe findings; only report_generator
# may recommend actions.
SCOPE_CREEP_PHRASES: list[str] = [
    "I recommend",
    "you should",
    "the customer must",
    "block the",
    "approve the",
    "contact the customer",
    "freeze the account",
    "escalate to",
    "notify",
]

# ---------------------------------------------------------------------------
# False certainty phrases
# ---------------------------------------------------------------------------

# LLMs sometimes produce overconfident language that misleads analysts.
# The Guardrail post-agent check raises a WARNING flag when these phrases
# appear in any agent output. Fraud detection involves uncertainty by
# definition — certainty language is a hallucination signal.
CERTAINTY_PHRASES: list[str] = [
    "this is definitely fraud",
    "this is certainly legitimate",
    "100% fraudulent",
    "guaranteed fraud",
    "definitely not fraud",
]
