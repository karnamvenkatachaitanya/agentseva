"""FastAPI routes for the Razorpay Agentic Commerce & Recovery Engine."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, HTTPException

from app.engine.agent import commerce_agent
from app.engine.audit import audit_logger
from app.engine.recovery import recovery_engine
from app.engine.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AuditRecordOut,
    RecoveryRequest,
    RecoveryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/agent/run", response_model=AgentRunResponse)
def run_agent(request: AgentRunRequest) -> AgentRunResponse:
    """Run the Hugging Face commerce agent for a single instruction.

    Returns the deterministic stop reason plus every tool call it made.
    Responds ``503`` if Hugging Face inference is not configured.
    """
    try:
        return commerce_agent.run(request)
    except RuntimeError as exc:  # e.g. missing HUGGINGFACE_API_KEY
        logger.warning("Agent unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/recovery/run", response_model=RecoveryResponse)
def run_recovery(request: RecoveryRequest) -> RecoveryResponse:
    """Run the deterministic payment-recovery policy for one payment."""
    return recovery_engine.recover(request)


@router.get("/audit/{session_id}", response_model=List[AuditRecordOut])
def get_audit_trail(session_id: str) -> List[AuditRecordOut]:
    """Return the full append-only audit trail for a session/recovery id."""
    trail = audit_logger.get_trail(session_id)
    if not trail:
        raise HTTPException(status_code=404, detail=f"No audit records for session '{session_id}'.")
    return trail
