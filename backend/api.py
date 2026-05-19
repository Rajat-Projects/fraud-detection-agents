"""
FraudShield FastAPI backend.

Wraps the multi-agent LangGraph pipeline behind a production REST API.
Every request goes through rate limiting before touching the pipeline.
Errors are caught globally and returned as structured JSON — never as
raw Python tracebacks which could leak internal detail.
"""

import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from pipeline.graph import run_fraud_analysis
from security.rate_limiter import RateLimiter
from utils.logger import FraudPipelineLogger

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "transaction_input": (
                "Transaction: 9500 dollars cash "
                "withdrawal at foreign ATM. Time: 3am. "
                "Customer transacted in New York 2 hours ago."
            ),
            "api_key": "demo-key-001",
        }
    })

    transaction_input: str = Field(..., max_length=4096)
    api_key: Optional[str] = "demo-key-001"


class AnalyzeResponse(BaseModel):
    transaction_ref: str
    final_risk_level: str
    final_risk_score: int
    recommended_action: str
    pipeline_halted: bool
    reliability: str
    structured_transaction: dict
    anomaly_report: dict
    rule_violations: dict
    risk_score: int
    risk_level: str
    risk_reasoning: str
    critic_review: dict
    final_report: dict
    agent_statuses: dict
    guardrail_flags: list
    state_checkpoints: dict
    incomplete_agents: list
    processing_time_ms: float
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    pipeline: str
    agents: int
    framework: str


# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.log_agent_start("api", "startup")
    print("FraudShield API started — docs at http://localhost:8000/docs")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="FraudShield API",
    description="""
## FraudShield — Multi-Agent Fraud Detection

A production-grade multi-agent AI system for
financial transaction fraud analysis.

### Architecture
7 specialized agents collaborate through a
LangGraph StateGraph pipeline with 4-layer
security guardrails at every step.

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

### Assignment
Wipro WEGA Forward Deployed Engineer
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "analysis", "description": "Transaction fraud analysis"},
        {"name": "system",   "description": "System health and status"},
    ],
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = str(round(process_time, 2))
    return response


# ---------------------------------------------------------------------------
# Module-level instances
# ---------------------------------------------------------------------------

rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
logger = FraudPipelineLogger("api")


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.log_agent_error("api", type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "error_type": type(exc).__name__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Versioned router — all business endpoints live under /v1
# Root (/) stays unversioned: it's an API discovery endpoint, not a resource.
# Adding a new version later means adding a v2 router without breaking v1.
# ---------------------------------------------------------------------------

v1 = APIRouter(prefix="/v1")

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["system"])
async def root():
    return {
        "name": "FraudShield API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/v1/health",
        "analyze": "/v1/analyze",
        "description": "Multi-Agent Fraud Detection System",
    }


@v1.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        pipeline="7-agent LangGraph StateGraph",
        agents=7,
        framework="LangGraph + Google Gemini",
    )


@v1.post("/analyze", response_model=AnalyzeResponse, tags=["analysis"])
async def analyze(request: AnalyzeRequest):
    """
    Analyze a financial transaction through the 7-agent fraud detection pipeline.

    Returns full pipeline state including risk verdict, critic review,
    rule violations, guardrail flags, and tamper-evident audit checkpoints.
    Human analyst makes the final decision — this system never acts autonomously.
    """
    start_time = time.time()

    # Log request start — no PII, no transaction content in logs
    logger.log_agent_start("analyze_endpoint", request.api_key or "anonymous")

    # Rate limiting
    allowed, info = rate_limiter.is_allowed(request.api_key or "anonymous")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "reset_in_seconds": info.get("reset_in_seconds", 60),
                "limit": info.get("limit", 10),
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
        logger.log_agent_error("api", type(e).__name__)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Pipeline execution failed",
                "error_type": type(e).__name__,
            },
        )

    processing_time_ms = round((time.time() - start_time) * 1000, 2)

    # Extract final_report fields safely
    final_report = result.get("final_report") or {}
    reliability        = final_report.get("reliability", "UNKNOWN")
    recommended_action = final_report.get("recommended_action", "REVIEW")

    logger.log_pipeline_complete(
        duration_ms=processing_time_ms,
        reliability=reliability,
        risk_level=result.get("final_risk_level", "UNKNOWN"),
    )

    return AnalyzeResponse(
        transaction_ref      = result.get("transaction_ref", ""),
        final_risk_level     = result.get("final_risk_level", ""),
        final_risk_score     = result.get("final_risk_score", 0),
        recommended_action   = recommended_action,
        pipeline_halted      = result.get("pipeline_halted", False),
        reliability          = reliability,
        structured_transaction = result.get("structured_transaction") or {},
        anomaly_report       = result.get("anomaly_report") or {},
        rule_violations      = result.get("rule_violations") or {},
        risk_score           = result.get("risk_score", 0),
        risk_level           = result.get("risk_level", ""),
        risk_reasoning       = result.get("risk_reasoning", ""),
        critic_review        = result.get("critic_review") or {},
        final_report         = final_report,
        agent_statuses       = result.get("agent_statuses") or {},
        guardrail_flags      = result.get("guardrail_flags") or [],
        state_checkpoints    = result.get("state_checkpoints") or {},
        incomplete_agents    = result.get("incomplete_agents") or [],
        processing_time_ms   = processing_time_ms,
        timestamp            = datetime.now(timezone.utc).isoformat(),
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
