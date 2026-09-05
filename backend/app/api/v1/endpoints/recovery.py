"""Revenue-recovery API — failed-payment webhooks and dropped-checkout recovery."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request

from app.agent.recovery import CheckoutSnapshot, RecoveryResult, revenue_recovery_engine

router = APIRouter()


@router.post("/webhook", response_model=RecoveryResult)
async def razorpay_webhook(request: Request) -> RecoveryResult:
    """Receive a Razorpay webhook and attempt recovery on ``payment.failed``.

    The raw body and ``X-Razorpay-Signature`` header are used for HMAC-SHA256
    signature verification when a webhook secret is configured.
    """
    raw = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    try:
        body = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        body = {}
    return revenue_recovery_engine.handle_webhook(body, raw_body=raw, signature=signature)


@router.post("/checkout", response_model=RecoveryResult)
def recover_checkout(snapshot: CheckoutSnapshot) -> RecoveryResult:
    """Attempt recovery for a dropped/abandoned checkout session."""
    return revenue_recovery_engine.recover_dropped_checkout(snapshot)
