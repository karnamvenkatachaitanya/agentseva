"""Secure Razorpay webhook receiver.

Verifies the ``X-Razorpay-Signature`` header (HMAC-SHA256 over the *raw* request
body, keyed by ``RAZORPAY_WEBHOOK_SECRET``) and dispatches recognised events to
handlers that write **immutable** audit records:

* ``payment.captured``   — funds captured; records a settlement audit row.
* ``payment.failed``     — triggers the automated revenue-recovery workflow.
* ``payment_link.paid``  — a recovery/checkout link was paid; records it.

If no webhook secret is configured (local/dev), signature verification is
skipped with a warning so tunnelled test events still flow — set the secret in
any real deployment to enforce it (a bad signature then returns ``401``).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.agent.recovery import revenue_recovery_engine
from app.audit.logger import audit_logger
from app.core.config import settings
from app.services import orders as orders_service
from app.tools.razorpay_tools import verify_webhook_signature

logger = logging.getLogger(__name__)

router = APIRouter()

HANDLED_EVENTS = {"payment.captured", "payment.failed", "payment_link.paid"}


def _extract_entity(body: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the relevant entity from a Razorpay webhook body, defensively.

    Razorpay nests entities under ``payload.<type>.entity``; we probe the known
    types in priority order and fall back to an empty dict.
    """
    payload = body.get("payload", {})
    if isinstance(payload, dict):
        for key in ("payment_link", "payment", "order"):
            node = payload.get(key)
            if isinstance(node, dict) and isinstance(node.get("entity"), dict):
                return node["entity"]
    return {}


def _session_id(entity: Dict[str, Any]) -> str:
    """Derive a stable session id for audit grouping."""
    notes = entity.get("notes") if isinstance(entity.get("notes"), dict) else {}
    return (notes or {}).get("session_id") or entity.get("order_id") or entity.get("id") or "webhook_unknown"


@router.post("/razorpay")
async def razorpay_webhook(request: Request) -> JSONResponse:
    """Receive, verify, and dispatch a Razorpay webhook."""
    raw = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    forwarded_proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    secret = settings.RAZORPAY_WEBHOOK_SECRET

    # 1) Signature verification (enforced only when a secret is configured).
    if secret:
        if not verify_webhook_signature(raw, signature or "", secret):
            logger.warning("Rejected Razorpay webhook: invalid signature")
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_signature", "detail": "X-Razorpay-Signature verification failed"},
            )
    else:
        logger.warning("RAZORPAY_WEBHOOK_SECRET not set — skipping signature verification (dev mode).")

    # 2) Parse body.
    try:
        body = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"error": "invalid_json", "detail": "Body is not JSON."})

    event = str(body.get("event", ""))
    entity = _extract_entity(body)
    session_id = _session_id(entity)

    # 3) Immutable receipt record for every accepted webhook.
    audit_logger.record(
        session_id, f"webhook:{event}", "received",
        user_intent="razorpay_webhook",
        agent_reasoning=f"event={event}; scheme={forwarded_proto}",
        payload_sent={"event": event, "entity_id": entity.get("id"), "order_id": entity.get("order_id")},
    )

    # 4) Dispatch.
    if event == "payment.failed":
        return _handle_payment_failed(body, raw, signature)
    if event == "payment.captured":
        return _handle_payment_captured(session_id, entity)
    if event == "payment_link.paid":
        return _handle_payment_link_paid(session_id, entity)

    return JSONResponse(status_code=200, content={"status": "ignored", "event": event, "session_id": session_id})


def _handle_payment_captured(session_id: str, entity: Dict[str, Any]) -> JSONResponse:
    """Record a captured payment as an immutable settlement audit row."""
    audit_logger.record(
        session_id, "webhook:payment.captured", "captured",
        user_intent="razorpay_webhook",
        agent_reasoning="payment captured — funds settled",
        payload_sent=entity,
        api_response={
            "payment_id": entity.get("id"),
            "order_id": entity.get("order_id"),
            "amount": entity.get("amount"),
            "currency": entity.get("currency"),
        },
    )
    _update_order_status(
        razorpay_order_id=entity.get("order_id"), status="paid", razorpay_payment_id=entity.get("id")
    )
    return JSONResponse(
        status_code=200,
        content={"status": "acknowledged", "event": "payment.captured", "session_id": session_id,
                 "payment_id": entity.get("id")},
    )


def _handle_payment_link_paid(session_id: str, entity: Dict[str, Any]) -> JSONResponse:
    """Record that a (recovery) payment link was paid."""
    audit_logger.record(
        session_id, "webhook:payment_link.paid", "paid",
        user_intent="razorpay_webhook",
        agent_reasoning="payment link paid — recovery/checkout completed",
        payload_sent=entity,
        api_response={
            "payment_link_id": entity.get("id"),
            "amount": entity.get("amount"),
            "amount_paid": entity.get("amount_paid"),
            "status": entity.get("status"),
        },
    )
    _update_order_status(razorpay_payment_link_id=entity.get("id"), status="paid")
    return JSONResponse(
        status_code=200,
        content={"status": "acknowledged", "event": "payment_link.paid", "session_id": session_id,
                 "payment_link_id": entity.get("id")},
    )


def _handle_payment_failed(body: Dict[str, Any], raw: bytes, signature: str | None) -> JSONResponse:
    """Mark the order failed, then run the automated revenue-recovery workflow."""
    entity = _extract_entity(body)
    _update_order_status(razorpay_order_id=entity.get("order_id"), status="failed")
    result = revenue_recovery_engine.handle_webhook(body, raw_body=raw, signature=signature)
    status_code = 401 if result.status.value == "rejected" else 200
    return JSONResponse(status_code=status_code, content=result.model_dump())


def _update_order_status(**kwargs: Any) -> None:
    """Best-effort order-status update from a webhook (never raises)."""
    try:
        orders_service.update_status_by_razorpay(**kwargs)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to update order status from webhook")
