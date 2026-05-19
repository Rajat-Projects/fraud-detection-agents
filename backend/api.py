"""
FraudShield FastAPI backend.

Wraps the multi-agent LangGraph pipeline behind a production REST API.
Every request goes through rate limiting before touching the pipeline.
Errors are caught globally and returned as structured JSON — never as
raw Python tracebacks which could leak internal detail.
"""

import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from pipeline.graph import run_fraud_analysis
from security.rate_limiter import RateLimiter
from utils.logger import FraudPipelineLogger

# ---------------------------------------------------------------------------
# Module-level instances (declared before lifespan so the context manager
# can reference them without forward-reference issues)
# ---------------------------------------------------------------------------

rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
logger = FraudPipelineLogger("api")

# ---------------------------------------------------------------------------
# Thread-safe in-process metrics store
# Resets on restart — Redis required for persistence across instances.
# ---------------------------------------------------------------------------

_metrics_store = {
    "pipeline_runs_total":      0,
    "pipeline_failures_total":  0,
    "security_halts_total":     0,
    "critic_overturn_total":    0,
    "critic_uphold_total":      0,
    "critic_modified_total":    0,
    "total_latency_ms":         0.0,
    "pii_detections_total":     0,
    "rule_violations_total":    0,
}
_metrics_lock = threading.Lock()


def _update_metrics(result: dict, processing_time_ms: float) -> None:
    with _metrics_lock:
        _metrics_store["pipeline_runs_total"] += 1
        _metrics_store["total_latency_ms"] += processing_time_ms

        if result.get("pipeline_halted"):
            _metrics_store["security_halts_total"] += 1

        critic  = result.get("critic_review") or {}
        verdict = critic.get("verdict", "")
        if verdict == "OVERTURNED":
            _metrics_store["critic_overturn_total"] += 1
        elif verdict == "UPHELD":
            _metrics_store["critic_uphold_total"] += 1
        elif verdict == "MODIFIED":
            _metrics_store["critic_modified_total"] += 1

        violations = (result.get("rule_violations") or {}).get(
            "violations_found", 0
        )
        _metrics_store["rule_violations_total"] += violations

        pii_flags = [
            f for f in (result.get("guardrail_flags") or [])
            if "PII" in (f.get("flag_type", "") if isinstance(f, dict) else "")
        ]
        _metrics_store["pii_detections_total"] += len(pii_flags)


# ---------------------------------------------------------------------------
# Authentication — API key via Authorization header (OWASP API2:2023)
# Credentials in the request body are logged by proxies and load balancers.
# Authorization header is stripped by most logging infrastructure.
# ---------------------------------------------------------------------------

async def get_api_key(
    authorization: Optional[str] = Header(None)
) -> str:
    if not authorization:
        return "demo-key-001"
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return authorization


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "transaction_input": (
                    "Transaction: 9500 dollars cash withdrawal at foreign ATM. "
                    "Time: 3am. Customer transacted in New York 2 hours ago."
                ),
            }
        }
    }

    transaction_input: str = Field(
        ...,
        max_length=4096,
        description="Transaction description in plain text or JSON",
    )


class AnalyzeResponse(BaseModel):
    transaction_ref:       str
    final_risk_level:      str
    final_risk_score:      int
    recommended_action:    str
    pipeline_halted:       bool
    reliability:           str
    structured_transaction: dict
    anomaly_report:        dict
    rule_violations:       dict
    risk_score:            int
    risk_level:            str
    risk_reasoning:        str
    critic_review:         dict
    final_report:          dict
    agent_statuses:        dict
    guardrail_flags:       list
    state_checkpoints:     dict
    incomplete_agents:     list
    processing_time_ms:    float
    timestamp:             str


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.log_agent_start("api", "startup")
    print("FraudShield API started — docs at http://localhost:8000/docs")
    yield


# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

app = FastAPI(
    lifespan=lifespan,
    title="FraudShield API",
    description="""
## FraudShield — Multi-Agent Fraud Detection

A production-grade multi-agent AI system for financial transaction fraud analysis.

### Architecture
7 specialized agents collaborate through a LangGraph StateGraph pipeline
with 4-layer security guardrails at every step.

### Authentication
All requests to `/v1/analyze` require an `Authorization: Bearer <key>` header.

### Agents
1. **Transaction Analyzer** — Structures raw input
2. **Anomaly Detection** — Behavioral pattern reasoning
3. **Rule Enforcement** — Deterministic compliance (No LLM)
4. **Risk Scoring** — Multi-signal synthesis
5. **Critic Agent** — Adversarial verdict challenger
6. **Report Generator** — 60-second analyst report
7. **Guardrail Agent** — Cross-cutting security

### Security
- Prompt injection protection (3-layer defense)
- PII tokenization at boundary
- Constitutional policies enforced in code
- Human-in-the-loop (no autonomous actions)
- Tamper-evident audit trail
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "analysis", "description": "Transaction fraud analysis"},
        {"name": "system",   "description": "System health and observability"},
    ],
)

# ---------------------------------------------------------------------------
# Middleware — order matters: outermost = last added
# CORS → security headers → process-time are applied inside-out
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"]         = "DENY"
    response.headers["X-XSS-Protection"]        = "1; mode=block"
    response.headers["Referrer-Policy"]          = "strict-origin-when-cross-origin"
    return response


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response   = await call_next(request)
    process_ms = (time.time() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = str(round(process_ms, 2))
    return response


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.log_agent_error("api", type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "error":      "Internal server error",
            "error_type": type(exc).__name__,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Versioned router
# ---------------------------------------------------------------------------

v1 = APIRouter(prefix="/v1")

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["system"])
async def root():
    return {
        "name":        "FraudShield API",
        "version":     "1.0.0",
        "docs":        "/docs",
        "health":      "/v1/health",
        "metrics":     "/v1/metrics",
        "analyze":     "/v1/analyze",
        "description": "Multi-Agent Fraud Detection System",
    }


@v1.get("/health", tags=["system"])
async def health():
    """
    Deep health check — tests every critical subsystem at startup.
    Returns 503 if any check fails so load balancers can route around unhealthy instances.
    """
    checks: dict = {}
    overall_status = "healthy"

    # Check 1: Pipeline importable
    try:
        from pipeline.graph import build_pipeline
        checks["pipeline"] = "operational"
    except Exception as e:
        checks["pipeline"] = f"error: {type(e).__name__}"
        overall_status = "degraded"

    # Check 2: LLM API key configured
    try:
        from config.settings import GEMINI_API_KEY
        if GEMINI_API_KEY and len(GEMINI_API_KEY) > 20:
            checks["llm_api_key"] = "configured"
        else:
            checks["llm_api_key"] = "missing or invalid"
            overall_status = "degraded"
    except Exception as e:
        checks["llm_api_key"] = f"error: {type(e).__name__}"
        overall_status = "degraded"

    # Check 3: Constitutional policies loaded
    try:
        from config.constitutional_policies import (
            MAX_CRITIC_LOOPS,
            MINIMUM_SCORE_WITH_RULE_VIOLATION,
        )
        checks["constitutional_policies"] = {
            "status":               "loaded",
            "minimum_score_floor":  MINIMUM_SCORE_WITH_RULE_VIOLATION,
            "max_critic_loops":     MAX_CRITIC_LOOPS,
        }
    except Exception as e:
        checks["constitutional_policies"] = f"error: {type(e).__name__}"
        overall_status = "degraded"

    # Check 4: Security components operational
    try:
        from security.injection_detector import InjectionDetector
        from security.pii_handler import PIIHandler
        InjectionDetector()
        PIIHandler()
        checks["security_components"] = "operational"
    except Exception as e:
        checks["security_components"] = f"error: {type(e).__name__}"
        overall_status = "degraded"

    response_data = {
        "status":    overall_status,
        "version":   "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline":  "LangGraph + Google Gemini",
        "agents":    7,
        "checks":    checks,
    }

    if overall_status != "healthy":
        return JSONResponse(status_code=503, content=response_data)

    return response_data


@v1.get("/metrics", tags=["system"])
async def get_metrics():
    """
    Operational metrics — Critic overturn rate, latency, security events.
    Counters are in-process only; they reset on restart.
    Production upgrade: export to Prometheus/Grafana via Redis-backed counters.
    """
    with _metrics_lock:
        runs = _metrics_store["pipeline_runs_total"]

        overturn_rate      = round(_metrics_store["critic_overturn_total"] / runs * 100, 1) if runs else 0
        avg_latency        = round(_metrics_store["total_latency_ms"] / runs, 1)             if runs else 0
        security_halt_rate = round(_metrics_store["security_halts_total"] / runs * 100, 1)  if runs else 0

        return {
            "pipeline": {
                "runs_total":           runs,
                "failures_total":       _metrics_store["pipeline_failures_total"],
                "security_halts_total": _metrics_store["security_halts_total"],
                "security_halt_rate_pct": security_halt_rate,
                "average_latency_ms":   avg_latency,
            },
            "critic": {
                "overturn_total":    _metrics_store["critic_overturn_total"],
                "uphold_total":      _metrics_store["critic_uphold_total"],
                "modified_total":    _metrics_store["critic_modified_total"],
                "overturn_rate_pct": overturn_rate,
            },
            "security": {
                "pii_detections_total":   _metrics_store["pii_detections_total"],
                "rule_violations_total":  _metrics_store["rule_violations_total"],
            },
            "meta": {
                "note":      "Counters reset on restart. Redis required for persistence.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


@v1.post("/analyze", response_model=AnalyzeResponse, tags=["analysis"])
async def analyze(
    request: AnalyzeRequest,
    api_key: str = Depends(get_api_key),
):
    """
    Analyze a financial transaction through the 7-agent fraud detection pipeline.

    **Authentication:** `Authorization: Bearer <key>` header (defaults to demo-key-001).

    Returns full pipeline state including risk verdict, critic review,
    rule violations, guardrail flags, and tamper-evident audit checkpoints.
    Human analyst makes the final decision — this system never acts autonomously.
    """
    start_time = time.time()

    # Log request start — no PII, no transaction content in logs
    logger.log_agent_start("analyze_endpoint", api_key or "anonymous")

    # Rate limiting — keyed on the Authorization header value
    allowed, info = rate_limiter.is_allowed(api_key or "anonymous")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error":             "Rate limit exceeded",
                "reset_in_seconds":  info.get("reset_in_seconds", 60),
                "limit":             info.get("limit", 10),
            },
        )

    # Input validation
    if not request.transaction_input.strip():
        raise HTTPException(
            status_code=422,
            detail="Transaction input cannot be empty",
        )

    # Run pipeline
    try:
        result = run_fraud_analysis(request.transaction_input)
    except Exception as e:
        with _metrics_lock:
            _metrics_store["pipeline_failures_total"] += 1
        logger.log_agent_error("api", type(e).__name__)
        raise HTTPException(
            status_code=500,
            detail={
                "error":      "Pipeline execution failed",
                "error_type": type(e).__name__,
            },
        )

    processing_time_ms = round((time.time() - start_time) * 1000, 2)

    # Update in-process metrics
    _update_metrics(result, processing_time_ms)

    # Extract final_report fields safely
    final_report       = result.get("final_report") or {}
    reliability        = final_report.get("reliability", "UNKNOWN")
    recommended_action = final_report.get("recommended_action", "REVIEW")

    logger.log_pipeline_complete(
        duration_ms=processing_time_ms,
        reliability=reliability,
        risk_level=result.get("final_risk_level", "UNKNOWN"),
    )

    return AnalyzeResponse(
        transaction_ref        = result.get("transaction_ref", ""),
        final_risk_level       = result.get("final_risk_level", ""),
        final_risk_score       = result.get("final_risk_score", 0),
        recommended_action     = recommended_action,
        pipeline_halted        = result.get("pipeline_halted", False),
        reliability            = reliability,
        structured_transaction = result.get("structured_transaction") or {},
        anomaly_report         = result.get("anomaly_report") or {},
        rule_violations        = result.get("rule_violations") or {},
        risk_score             = result.get("risk_score", 0),
        risk_level             = result.get("risk_level", ""),
        risk_reasoning         = result.get("risk_reasoning", ""),
        critic_review          = result.get("critic_review") or {},
        final_report           = final_report,
        agent_statuses         = result.get("agent_statuses") or {},
        guardrail_flags        = result.get("guardrail_flags") or [],
        state_checkpoints      = result.get("state_checkpoints") or {},
        incomplete_agents      = result.get("incomplete_agents") or [],
        processing_time_ms     = processing_time_ms,
        timestamp              = datetime.now(timezone.utc).isoformat(),
    )


# Register the versioned router — must happen after all route definitions
app.include_router(v1)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
