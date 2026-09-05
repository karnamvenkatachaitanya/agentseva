"""Production FastAPI gateway for the AgentSeva Razorpay Agentic Commerce engine.

Wires together CORS, rate limiting (slowapi), structured exception handling, and
the four public gateway endpoints:

* ``POST /api/v1/agent/chat``          — session-aware agent interaction
* ``POST /api/v1/webhooks/razorpay``   — signature-verified webhook receiver
* ``GET  /api/v1/health``              — liveness + dependency status
* ``GET  /api/v1/metrics``             — transactions processed / money recovered / failure rate

The domain routers (AI, engine, audit traces, recovery) are also mounted under
``/api/v1`` via :data:`app.api.v1.api.api_router`.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import text
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.agent.core import CommerceAgentCore
from app.agent.guardrails import PaymentGuardrailValidator
from app.api.v1.api import api_router
from app.api.webhooks import router as webhooks_router
from app.audit.logger import audit_logger
from app.core.config import settings
from app.core.rate_limit import RATE_LIMIT_AVAILABLE, RateLimitExceeded, limiter
from app.db.base import SessionLocal, init_db
from app.engine.schemas import GuardrailViolation
from app.engine.razorpay_client import RazorpayError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Verify database connectivity and ensure catalog seed data is present."""
    init_db()
    yield


app = FastAPI(
    title="AgentSeva — Razorpay Agentic Commerce & Recovery Engine",
    description=(
        "Session-aware open-source payments agent with hard financial guardrails, "
        "an append-only audit trail, and an automated revenue-recovery engine."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# --------------------------------------------------------------------------- #
# Middleware
# --------------------------------------------------------------------------- #
# Honour proxy-supplied forwarded headers (X-Forwarded-Proto / X-Forwarded-For)
# so request.url.scheme reflects HTTPS behind Cloudflare / nginx / a load
# balancer, and client IPs are correct for rate limiting. trusted_hosts="*"
# because TLS terminates at the trusted edge in this deployment.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Rate limiting (real when slowapi is installed; otherwise a no-op).
app.state.limiter = limiter
if RATE_LIMIT_AVAILABLE:  # pragma: no cover - container-only path
    from slowapi.middleware import SlowAPIMiddleware

    async def _rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limit_exceeded", "detail": "Too many requests; slow down."},
        )

    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)


# --------------------------------------------------------------------------- #
# Structured exception handlers
# --------------------------------------------------------------------------- #
@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "detail": exc.errors()},
    )


@app.exception_handler(GuardrailViolation)
async def _guardrail_handler(request: Request, exc: GuardrailViolation) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": "guardrail_denied", "detail": exc.result.reason,
                 "checks": exc.result.checks},
    )


@app.exception_handler(RazorpayError)
async def _razorpay_handler(request: Request, exc: RazorpayError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"error": "razorpay_error", "category": exc.category, "detail": str(exc)},
    )


@app.exception_handler(HTTPException)
async def _http_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "http_error", "detail": exc.detail},
    )


@app.exception_handler(Exception)
async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": "An unexpected error occurred."},
    )


# --------------------------------------------------------------------------- #
# Session registry — one guardrail validator per conversation session
# --------------------------------------------------------------------------- #
_SESSION_GUARDRAILS: Dict[str, PaymentGuardrailValidator] = {}


def _guardrails_for(session_id: str) -> PaymentGuardrailValidator:
    """Return the session's guardrails, creating them on first use.

    Keeping the validator per-session makes the cumulative session cap and the
    circuit breaker stateful across turns of the same conversation.
    """
    return _SESSION_GUARDRAILS.setdefault(session_id, PaymentGuardrailValidator())


# --------------------------------------------------------------------------- #
# Request/response models
# --------------------------------------------------------------------------- #
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, max_length=64)
    context: Dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Gateway endpoints
# --------------------------------------------------------------------------- #
@app.post("/api/v1/agent/chat", tags=["Gateway"])
@limiter.limit("30/minute")
def agent_chat(request: Request, body: ChatRequest) -> Dict[str, Any]:
    """Session-aware agent interaction.

    Runs the bounded :class:`CommerceAgentCore` with the session's persistent
    guardrails. Returns ``503`` if Hugging Face inference is not configured.
    """
    session_id = body.session_id or f"sess_{uuid.uuid4().hex[:16]}"
    agent = CommerceAgentCore(guardrails=_guardrails_for(session_id))
    try:
        result = agent.run(body.message, context=body.context)
    except RuntimeError as exc:  # missing HUGGINGFACE_API_KEY
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"session_id": session_id, **result.model_dump()}


@app.get("/api/v1/health", tags=["Gateway"])
def health() -> Dict[str, Any]:
    """Liveness probe plus dependency status."""
    db_ok = True
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False

    dependencies = {
        "database": "ok" if db_ok else "unreachable",
        "razorpay_mode": settings.RAZORPAY_MODE,
        "razorpay_credentials": bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET),
        "huggingface_configured": bool(settings.HUGGINGFACE_API_KEY),
        "agent_model": settings.HF_LLM_MODEL,
        "rate_limiting": RATE_LIMIT_AVAILABLE,
    }
    return {
        "status": "ok" if db_ok else "degraded",
        "service": "agentseva-gateway",
        "version": app.version,
        "dependencies": dependencies,
    }


@app.get("/api/v1/metrics", tags=["Gateway"])
def metrics() -> Dict[str, Any]:
    """Operational metrics: transactions processed, money recovered, failure rate."""
    data = audit_logger.aggregate_metrics()
    data["active_sessions"] = len(_SESSION_GUARDRAILS)
    return data


# Mount the secure webhook receiver and the domain routers (AI, engine, audit, recovery).
app.include_router(webhooks_router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(api_router, prefix="/api/v1")

# Production builds place the Vite app here. Mounting it last keeps every API
# route authoritative while allowing client-side routes to fall back to index.
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
