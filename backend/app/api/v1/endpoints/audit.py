"""Audit-trace read API — the step-by-step decision tree for evaluators."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from app.agent.guardrails import (
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_RISK_THRESHOLD,
    DEFAULT_SESSION_CAP_PAISE,
    DEFAULT_SINGLE_ORDER_CAP_PAISE,
)
from app.audit.logger import AuditTraceOut, audit_logger

router = APIRouter()


@router.get("/recent", response_model=List[AuditTraceOut])
def get_recent_traces(limit: int = Query(default=50, ge=1, le=500)) -> List[AuditTraceOut]:
    """Return the most recent audit records across all sessions (newest first)."""
    return audit_logger.get_recent(limit)


@router.get("/limits")
def get_guardrail_limits() -> Dict[str, Any]:
    """Expose the monetary guardrail limits for the Audit & Guardrails view."""
    return {
        "single_order_cap_inr": DEFAULT_SINGLE_ORDER_CAP_PAISE / 100,
        "session_cap_inr": DEFAULT_SESSION_CAP_PAISE / 100,
        "circuit_breaker_failure_threshold": DEFAULT_FAILURE_THRESHOLD,
        "risk_score_threshold": DEFAULT_RISK_THRESHOLD,
    }


@router.get("/traces/{session_id}", response_model=List[AuditTraceOut])
def get_session_traces(session_id: str) -> List[AuditTraceOut]:
    """Return the full, ordered append-only audit trail for a session.

    Each logical tool call appears as a before (``initiated``) / after
    (``success`` | ``failed`` | ``error``) pair sharing a ``trace_id``, so the
    complete decision tree can be replayed in order.
    """
    traces = audit_logger.get_traces(session_id)
    if not traces:
        raise HTTPException(status_code=404, detail=f"No audit traces for session '{session_id}'.")
    return traces
