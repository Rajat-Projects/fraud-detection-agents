# FraudShield — Architecture & Design Decisions

## Overview

FraudShield is a multi-agent AI system for financial transaction fraud analysis.
Seven specialized agents collaborate through a LangGraph StateGraph pipeline
with 4-layer security guardrails and an adversarial Critic Agent that challenges
every verdict before it reaches a human analyst.

---

## Why Multi-Agent, Not One LLM?

A single LLM producing a fraud verdict gives unauditable output. When the verdict
is wrong, you cannot determine which reasoning step failed. Specialized agents
give full traceability:

- If the verdict is wrong, you know exactly which agent is responsible.
- Each agent's output is independently validatable.
- Role constraints enforced in code cannot be bypassed by prompt manipulation.

**Trade-off accepted:** Higher latency (5 sequential LLM calls vs. 1).
**Why acceptable:** Fraud analysis is asynchronous — analysts work queues,
not real-time authorization paths.

---

## Agent Design Decisions

### Decision 1 — Rule Enforcement Has No LLM

```python
# Rule Enforcement uses pure Python — no LLM
class RuleEnforcementAgent:  # Does NOT inherit BaseAgent
    def run(self, state):
        # Deterministic logic only
```

**Why:** Compliance rules exist precisely because they cannot be reasoned around.
An LLM that reasons "this $10,001 is essentially the same as $9,999" provides
zero compliance guarantee. Deterministic Python provides an absolute guarantee.

### Decision 2 — Pydantic `extra='forbid'` on Every Schema

Every agent output schema uses `model_config = ConfigDict(extra='forbid')`.

**Why:** Structural constraints, not prompt constraints. An LLM cannot return
fields outside the schema because the structured output enforcer rejects them.
Prompt-based constraints can be overridden; type-system constraints cannot.

### Decision 3 — Constitutional Policies in Code, Not Prompts

Five inviolable rules enforced in Python:

```python
MINIMUM_SCORE_WITH_RULE_VIOLATION = 50
MAX_CRITIC_LOOPS = 2
```

**Why:** Policies in prompts can be bypassed by sufficiently clever inputs.
Policies in code cannot. This is the difference between a suggestion and a constraint.

### Decision 4 — The Critic Agent Loop

The Critic acts as a defense attorney, not a second prosecutor. It actively
searches for innocent explanations before accepting that fraud occurred.

```
Risk Scoring → HIGH (85)
       ↓
Critic (OVERTURNED — annual traveler pattern found)
       ↓
Risk Scoring re-evaluates with traveler context
       ↓
MEDIUM (52) → Human Analyst
```

**Trade-off:** Adds 1-2 LLM calls. **Why acceptable:** False positives are
expensive — blocking legitimate customer transactions damages trust more than
the latency cost of re-evaluation.

### Decision 5 — MANDATORY_ESCALATION, Not IMMEDIATE_BLOCK

```python
severity: Literal["ADVISORY", "MANDATORY_REVIEW", "MANDATORY_ESCALATION"]
# IMMEDIATE_BLOCK does not exist in this system
```

**Why:** The system never blocks, freezes, or approves anything autonomously.
Every output is a recommendation to a human analyst. MANDATORY_ESCALATION means
a human must be involved — not that the system acted. Human authority is always
preserved.

---

## Security Architecture

### Layer 1 — Boundary

| Control | Implementation |
|---|---|
| Rate limiting | Sliding window, 10 req/min per API key |
| Injection detection | Pattern + entropy + structural (3 independent checks) |
| PII tokenization | Regex-based, zero external dependencies |
| Input length | Hard limit, 4096 characters |

**PII Tokenization approach:** We chose regex-based over ML-based (spaCy, Presidio)
for deterministic behavior. Production upgrade path: Microsoft Presidio or enterprise
DLP for contextual detection. The current approach covers card numbers, emails, phones,
SSNs, and account numbers with zero false negatives on explicit patterns.

### Layer 2 — Pipeline (at every agent boundary)

Pre-agent checks: injection patterns, entropy anomalies, PII in agent input.
Post-agent checks: schema compliance, scope creep, false certainty, PII in output,
ground truth consistency.

**Scope creep detection:** An agent that writes to fields outside its authorized
list is a hallucination signal. We detect this at every handoff.

### Layer 3 — Decision

- Constitutional policies enforced in code
- `recommended_action: Literal["APPROVE", "REVIEW"]` — no BLOCK option exists
- Incomplete pipelines always disclosed (`reliability: "DEGRADED"`)

### Layer 4 — Infrastructure

- Secrets via environment variables only — never in code or Docker image layers
- SHA-256 state checkpoints after every agent (tamper-evident audit trail)
- `token_map` deleted before API response — PII never leaves the backend
- PII-aware logging — event metadata only, transaction content never logged

---

## Pipeline State Flow

```
FraudPipelineState (TypedDict)
│
├── raw_input              → set at boundary
├── structured_transaction → Transaction Analyzer
├── token_map              → Transaction Analyzer (NEVER passed to LLMs)
├── anomaly_report         → Anomaly Detection
├── rule_violations        → Rule Enforcement
├── risk_score             → Risk Scoring
├── risk_level             → Risk Scoring
├── risk_reasoning         → Risk Scoring
├── critic_review          → Critic Agent
├── final_risk_score       → Critic Agent (constitutional floor applied)
├── final_risk_level       → Critic Agent
├── final_report           → Report Generator
├── guardrail_flags        → Guardrail (cross-cutting)
├── agent_statuses         → all agents
└── state_checkpoints      → SHA-256 per agent
```

Each agent reads only the fields it needs. Write restrictions are enforced in
`BaseAgent.run()` — the base class filters the output dict before returning.

---

## LLM Configuration

| Setting | Value | Reason |
|---|---|---|
| Model | gemini-2.5-flash | Free tier, strong reasoning |
| Temperature | 0.1 | Identical transactions → identical treatment |
| Max output tokens | 4096 | Sufficient for structured JSON outputs |

**Why temperature 0.1?** In regulated environments, variance in AI outputs on
identical inputs raises audit questions. Consistency of treatment is a compliance
requirement, not a preference.

---

## Failure Handling

| Failure type | Response |
|---|---|
| Transient (timeout, rate limit) | Retry with exponential backoff (max 3 attempts) |
| Format (schema mismatch) | Retry once, then structured fallback |
| Security (injection detected) | Halt immediately — never retry |
| Rule Enforcement failure | Deterministic fallback (MANDATORY_ESCALATION rules only) |
| Non-critical agent failure | Mark incomplete, pipeline continues |
| Any failure | Disclosed in `reliability` field of final report |

**Fallback principle:** A system that hides its failures produces false confidence.
The human analyst always knows how complete the analysis is.

---

## Agent Authority Hierarchy

```
Constitutional Policies  ← Highest — cannot be overridden
Rule Enforcement         ← No LLM — deterministic
Guardrail Agent          ← Cross-cutting — can halt pipeline
LLM Agents              ← All other agents
Human Analyst           ← Final decision — always required
```

No agent in a lower tier can override a constraint set by a higher tier.

---

## Production Upgrade Path

| Current (demo) | Production |
|---|---|
| In-process rate limiter | Redis-backed distributed limiter |
| Gemini free tier | Paid API with SLA |
| Synchronous pipeline | Async job queue (Celery/Redis) |
| Regex PII detection | Microsoft Presidio + enterprise DLP |
| Single process | Horizontal scaling with load balancer |

The three most important production changes:
1. **Paid LLM API** — fraud analysis cannot tolerate downtime or rate limits
2. **Async processing** — concurrent transactions require job queue architecture
3. **Model monitoring** — track Critic overturn rate; if > 80%, Risk Scoring has drifted

---

## Deployment Architecture

```
Internet → Vercel CDN (React SPA)
                ↓ HTTPS
        Railway.app (FastAPI + Uvicorn)
                ↓
        Google Gemini API
```

Frontend env var `VITE_API_URL` set at build time — no runtime injection.
Backend `GEMINI_API_KEY` set as Railway environment variable — never in image.
