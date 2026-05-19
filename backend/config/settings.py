"""
Central configuration for the fraud detection pipeline.

All runtime values come from environment variables (via .env in development,
real env vars in production). Nothing is hardcoded except safe defaults.
Secrets (GEMINI_API_KEY, VALID_API_KEYS) must never appear in source control.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# API / Auth
# ---------------------------------------------------------------------------

# Primary LLM credential. Loaded from env — never hardcoded.
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# Comma-separated list in env → Python list at import time.
# Used by the rate limiter to scope per-key request tracking.
VALID_API_KEYS: list[str] = [
    k.strip()
    for k in os.getenv("VALID_API_KEYS", "").split(",")
    if k.strip()
]

# ---------------------------------------------------------------------------
# Runtime environment
# ---------------------------------------------------------------------------

ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

# ---------------------------------------------------------------------------
# Pipeline limits
# ---------------------------------------------------------------------------

# Maximum times the Critic can loop back to Risk Scoring.
# Mirrors constitutional_policies.MAX_CRITIC_LOOPS — settings.py owns the
# env-driven value; constitutional_policies.py owns the policy constant.
MAX_CRITIC_LOOPS: int = int(os.getenv("MAX_CRITIC_LOOPS", "2"))

# Per-agent wall-clock timeout in seconds. Triggers fallback logic.
AGENT_TIMEOUT_SECONDS: int = int(os.getenv("AGENT_TIMEOUT_SECONDS", "30"))

# API-level rate limit. The rate limiter enforces this per API key per minute.
MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "10"))

# ---------------------------------------------------------------------------
# LLM configuration
# ---------------------------------------------------------------------------

# Temperature MUST be 0.1 for every LLM agent.
# Identical transactions must receive identical treatment — variance in outputs
# on identical inputs is a compliance audit risk in regulated environments.
LLM_CONFIG: dict = {
    "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    "temperature": 0.1,
    "max_output_tokens": 4096,
}

# ---------------------------------------------------------------------------
# Risk thresholds
# ---------------------------------------------------------------------------

# Score → risk level mapping used by Risk Scoring and Critic agents.
# Thresholds are centralised here so a single change propagates everywhere.
RISK_THRESHOLDS: dict = {
    "low_max": 35,      # 0–35   → LOW
    "medium_max": 70,   # 36–70  → MEDIUM
    "high_min": 71,     # 71–100 → HIGH
}

# ---------------------------------------------------------------------------
# Confidence thresholds
# ---------------------------------------------------------------------------

# These gate when automatic decisions are possible vs when humans must review.
# minimum_acceptable:   below this → agent output is unreliable, flag it
# human_review_trigger: below this → always escalate regardless of risk level
# auto_low_risk:        above this + LOW risk → APPROVE without human review
CONFIDENCE_THRESHOLDS: dict = {
    "minimum_acceptable": 40,
    "human_review_trigger": 60,
    "auto_low_risk": 90,
}

# ---------------------------------------------------------------------------
# Environment-specific overrides
# ---------------------------------------------------------------------------

# Production tightens limits and enforces stricter validation.
# Development loosens them for local testing without a live API key.
ENV_CONFIG: dict = {
    "development": {
        "require_api_key": False,
        "log_level": "DEBUG",
        "mock_llm_allowed": True,
        "strict_pii_enforcement": False,
    },
    "production": {
        "require_api_key": True,
        "log_level": "INFO",
        "mock_llm_allowed": False,
        "strict_pii_enforcement": True,
    },
}

CURRENT_ENV_CONFIG: dict = ENV_CONFIG.get(ENVIRONMENT, ENV_CONFIG["development"])
