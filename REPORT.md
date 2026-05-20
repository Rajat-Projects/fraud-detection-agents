# FraudShield — Multi-Agent Fraud Detection System
## Wipro WEGA Forward Deployed Engineer Assignment

**Live Demo:** https://majestic-travesseiro-0d8d70.netlify.app
**API:** https://rare-spirit-production-efc1.up.railway.app/docs
**GitHub:** https://github.com/Rajat-Projects/fraud-detection-agents

---

## Problem Statement

Financial institutions lose more to false positives ($118B annually) than to actual fraud ($28B). FraudShield targets the analyst review queue — the 2-3% of transactions real-time ML flags for investigation — reducing analysis time from 7 minutes to 90 seconds through specialized agents, adversarial self-review, and tamper-evident decision trails.

---

## 1. Multi-Agent Architecture

A single LLM blends reasoning domains: behavioral analysis contaminates compliance checking, which contaminates scoring, creating circular reasoning. Seven agents make each failure traceable to a specific component.

The Transaction Analyzer handles unstructured text extraction. Anomaly Detection performs customer-specific behavioral comparison, context-constrained to prevent anchoring on violations not yet evaluated. Rule Enforcement applies compliance logic in pure Python — an LLM reasoning "this $10,001 is essentially the same as $9,999" provides zero compliance guarantee. Risk Scoring synthesizes signals with four-example few-shot calibration. The Critic challenges every verdict via defense attorney framing, requiring a 6-step chain of thought. The Report Generator translates outputs into 60-second analyst briefings. The Guardrail runs on every boundary with no LLM, making it uninjectible.

Communication uses a shared TypedDict state. Write restrictions in `BaseAgent.run()` prevent scope creep; context constraints prevent anchoring bias. Sequential over parallel: state-merging complexity outweighed the 2-second latency saving. The Critic loop (`MAX_CRITIC_LOOPS = 2`) creates genuine agent negotiation.

---

## 2. Security, Safety, and Guardrails

Four security layers: Boundary (injection, PII, rate limiting), Pipeline (Guardrail at every agent boundary), Decision (constitutional policies, human-in-the-loop), and Infrastructure (secrets, tamper-evident checkpointing).

Three independent injection-defense methods: pattern matching against 16 known phrases, Shannon entropy analysis for obfuscated attacks, and structural bracket-density checks. The Sandwich Defense wraps all input in `<untrusted_data>` tags. Injection halts in under 100ms before any LLM call.

PII handling uses tokenization, not deletion — deletion destroys cross-transaction linking required by the Anomaly Agent. The `token_map` is removed via `result.pop()` before the API response; Pydantic exclusion alone does not protect intermediate logging layers.

`MINIMUM_SCORE_WITH_RULE_VIOLATION = 50` is enforced in Python after every LLM call, applied independently in both Risk Scoring and the Critic Agent — closing the gap a single enforcement point would leave. `recommended_action` is declared `Literal["APPROVE", "REVIEW"]`; BLOCK does not exist in any schema.

---

## 3. Implementation Approach

LangGraph over CrewAI (no conditional routing for the Critic loop) and AutoGen (non-deterministic ordering unacceptable in compliance). `graph.py` is the architecture diagram.

`BaseAgent` implements the Template Method Pattern. The fixed `run()` algorithm — context constraint, secure prompt, LLM call, write restriction, logging — cannot be bypassed by subclasses. Abstract methods enforce class-time contracts — `TypeError` at development, not silent runtime failure.

Three error levels: exponential backoff with jitter for transient failures; a deterministic fallback for Rule Enforcement applying only `MANDATORY_ESCALATION` rules when the primary run fails; and graceful degradation disclosed through the `reliability` field. `SecurityViolationError` is never retried. The suite covers 66 tests across 4 tiers in 0.75 seconds with no API key required. Acknowledged gap: output quality is validated through known scenarios rather than statistical precision-recall.

---

## 4. Use of AI/LLMs and Collaboration

Five agents use LLMs for reasoning deterministic code cannot replicate. The Transaction Analyzer handles ambiguous natural language parsers fail on. Anomaly Detection reasons about what is anomalous for a specific customer — rules flag all high-value transactions, LLMs reason contextually. Risk Scoring handles non-linear signal interaction where combined anomalies amplify risk in ways formulas miss. The Critic's defense attorney framing activates reasoning from legal and dispute resolution training data. The Report Generator translates without adding analysis.

Two agents exclude LLMs. Rule Enforcement applies binary compliance logic. The Guardrail uses deterministic pattern matching — uninjectible, adding microseconds not seconds per boundary.

The Critic loop creates adversarial negotiation bounded to two rounds, with full autonomy over reasoning and zero autonomy over actions. A wrong autonomous block — a customer locked out during an emergency — always exceeds the cost of 90 seconds of human review.

---

FraudShield demonstrates that responsible AI in regulated domains is not about limiting capability — it is about directing it. Seven agents reason freely within their domains. No agent acts autonomously. The system informs. The human decides.
