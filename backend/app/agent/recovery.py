"""Revenue Recovery Engine.

Detects lost/at-risk revenue and executes *compliant* recovery interventions:

* **Triggers** — a failed Razorpay webhook (``payment.failed``) or a dropped
  checkout session (idle / abandoned before payment).
* **Diagnosis** — a deterministic root-cause classifier
  (``bank_decline``, ``insufficient_funds``, ``user_dropoff``,
  ``session_timeout``, ``unknown``).
* **Intervention** — a bounded, policy-driven action:
    - bank decline / insufficient funds → **alternate UPI retry link** (same amount),
    - user drop-off → **automated discount link** (discount capped at
      ``max_discount_pct``, never stacked),
    - session timeout → **fresh retry link** (same amount),
    - unknown → **escalate** to a human, no automated money action.

Every payment-link generation is wrapped in the append-only audit trail via
:meth:`AuditLogger.trace`, so each intervention leaves an immutable before/after
record keyed by the recovery ``session_id``.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.audit.logger import AuditLogger, audit_logger
from app.core.config import settings
from app.tools.razorpay_tools import (
    RazorpayToolRegistry,
    razorpay_tools,
    verify_webhook_signature,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_DISCOUNT_PCT = 10.0
#: Idle seconds beyond which a dropped checkout is treated as a hard timeout.
DEFAULT_TIMEOUT_SECONDS = 900  # 15 minutes


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class RecoveryTrigger(str, Enum):
    WEBHOOK_PAYMENT_FAILED = "webhook_payment_failed"
    DROPPED_CHECKOUT = "dropped_checkout"


class RootCause(str, Enum):
    BANK_DECLINE = "bank_decline"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    USER_DROPOFF = "user_dropoff"
    SESSION_TIMEOUT = "session_timeout"
    UNKNOWN = "unknown"


class Intervention(str, Enum):
    UPI_RETRY_LINK = "upi_retry_link"
    DISCOUNT_LINK = "discount_link"
    FRESH_RETRY_LINK = "fresh_retry_link"
    ESCALATE = "escalate"
    NONE = "none"


class RecoveryStatus(str, Enum):
    RECOVERED_LINK_ISSUED = "recovered_link_issued"
    ESCALATED = "escalated"
    IGNORED = "ignored"
    REJECTED = "rejected"
    FAILED = "failed"


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class CheckoutSnapshot(BaseModel):
    """A point-in-time view of a checkout session for drop-off detection."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=64)
    order_id: str = Field(min_length=1, max_length=64)
    amount_inr: float = Field(gt=0)
    customer_name: str = Field(default="Valued Customer", max_length=120)
    customer_phone: str = Field(min_length=8, max_length=20)
    last_stage: str = Field(default="cart", max_length=40)
    idle_seconds: int = Field(ge=0)
    payment_attempted: bool = False


class RecoveryResult(BaseModel):
    """Structured outcome of a recovery attempt."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    order_id: Optional[str] = None
    trigger: RecoveryTrigger
    root_cause: RootCause
    intervention: Intervention
    status: RecoveryStatus
    detail: str
    payment_link: Optional[str] = None
    discount_pct: Optional[float] = None
    recovery_amount_inr: Optional[float] = None


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #


class RevenueRecoveryEngine:
    """Diagnose lost revenue and issue compliant recovery interventions."""

    def __init__(
        self,
        tools: Optional[RazorpayToolRegistry] = None,
        audit: Optional[AuditLogger] = None,
        webhook_secret: Optional[str] = None,
        max_discount_pct: float = DEFAULT_MAX_DISCOUNT_PCT,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.tools = tools or razorpay_tools
        self.audit = audit or audit_logger
        self.webhook_secret = webhook_secret if webhook_secret is not None else settings.RAZORPAY_WEBHOOK_SECRET
        self.max_discount_pct = max_discount_pct
        self.timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------ #
    # Trigger 1: failed-payment webhook
    # ------------------------------------------------------------------ #
    def handle_webhook(
        self, body: Dict[str, Any], raw_body: Optional[bytes] = None, signature: Optional[str] = None
    ) -> RecoveryResult:
        """Process a Razorpay webhook and recover a ``payment.failed`` event."""
        # 1) Optional signature verification (only when a secret is configured).
        if self.webhook_secret and raw_body is not None:
            if not verify_webhook_signature(raw_body, signature or "", self.webhook_secret):
                return RecoveryResult(
                    session_id="unknown", trigger=RecoveryTrigger.WEBHOOK_PAYMENT_FAILED,
                    root_cause=RootCause.UNKNOWN, intervention=Intervention.NONE,
                    status=RecoveryStatus.REJECTED, detail="invalid webhook signature",
                )

        event = str(body.get("event", ""))
        if event != "payment.failed":
            return RecoveryResult(
                session_id=str(body.get("event", "unknown")),
                trigger=RecoveryTrigger.WEBHOOK_PAYMENT_FAILED,
                root_cause=RootCause.UNKNOWN, intervention=Intervention.NONE,
                status=RecoveryStatus.IGNORED, detail=f"ignoring non-recoverable event '{event}'",
            )

        entity = self._extract_payment_entity(body)
        order_id = entity.get("order_id") or entity.get("id") or "unknown"
        session_id = entity.get("notes", {}).get("session_id") or order_id
        amount_inr = float(Decimal(str(entity.get("amount", 0))) / 100)
        phone = entity.get("contact") or ""
        name = entity.get("notes", {}).get("customer_name") or "Valued Customer"

        root_cause = self.diagnose_webhook(entity)
        return self._intervene(
            trigger=RecoveryTrigger.WEBHOOK_PAYMENT_FAILED,
            root_cause=root_cause, session_id=session_id, order_id=order_id,
            amount_inr=amount_inr, customer_name=name, customer_phone=phone,
        )

    # ------------------------------------------------------------------ #
    # Trigger 2: dropped checkout
    # ------------------------------------------------------------------ #
    def recover_dropped_checkout(self, snapshot: CheckoutSnapshot) -> RecoveryResult:
        """Detect and recover an abandoned checkout session."""
        root_cause = self.diagnose_checkout(snapshot)
        return self._intervene(
            trigger=RecoveryTrigger.DROPPED_CHECKOUT,
            root_cause=root_cause, session_id=snapshot.session_id, order_id=snapshot.order_id,
            amount_inr=snapshot.amount_inr, customer_name=snapshot.customer_name,
            customer_phone=snapshot.customer_phone,
        )

    # ------------------------------------------------------------------ #
    # Diagnosis
    # ------------------------------------------------------------------ #
    def diagnose_webhook(self, entity: Dict[str, Any]) -> RootCause:
        """Classify the root cause of a failed payment from its error fields."""
        text = " ".join(str(entity.get(k, "")) for k in (
            "error_description", "error_reason", "error_code", "error_source", "error_step"
        )).lower()

        if any(w in text for w in ("insufficient", "low balance", "exceeds")):
            return RootCause.INSUFFICIENT_FUNDS
        if any(w in text for w in ("declin", "do_not_honour", "blocked", "fraud", "bank")):
            return RootCause.BANK_DECLINE
        if any(w in text for w in ("timeout", "timed out", "gateway", "network")):
            return RootCause.SESSION_TIMEOUT
        if any(w in text for w in ("cancel", "abandon", "customer")):
            return RootCause.USER_DROPOFF
        return RootCause.UNKNOWN

    def diagnose_checkout(self, snapshot: CheckoutSnapshot) -> RootCause:
        """Classify why a checkout was dropped."""
        if snapshot.idle_seconds >= self.timeout_seconds:
            return RootCause.SESSION_TIMEOUT
        return RootCause.USER_DROPOFF

    # ------------------------------------------------------------------ #
    # Intervention policy
    # ------------------------------------------------------------------ #
    def _intervene(
        self,
        *,
        trigger: RecoveryTrigger,
        root_cause: RootCause,
        session_id: str,
        order_id: str,
        amount_inr: float,
        customer_name: str,
        customer_phone: str,
    ) -> RecoveryResult:
        """Select and execute the compliant recovery action for a root cause."""
        # Map root cause → intervention.
        if root_cause in (RootCause.BANK_DECLINE, RootCause.INSUFFICIENT_FUNDS):
            intervention = Intervention.UPI_RETRY_LINK
        elif root_cause is RootCause.USER_DROPOFF:
            intervention = Intervention.DISCOUNT_LINK
        elif root_cause is RootCause.SESSION_TIMEOUT:
            intervention = Intervention.FRESH_RETRY_LINK
        else:
            intervention = Intervention.ESCALATE

        base = RecoveryResult(
            session_id=session_id, order_id=order_id, trigger=trigger,
            root_cause=root_cause, intervention=intervention, status=RecoveryStatus.ESCALATED,
            detail="",
        )

        if intervention is Intervention.ESCALATE:
            base.detail = "Root cause could not be determined automatically; escalating to a human agent."
            return base

        # Compute the recovery amount + discount (compliant, bounded).
        discount_pct: Optional[float] = None
        recovery_amount = round(amount_inr, 2)
        description = f"Complete your AgentSeva order {order_id}"
        if intervention is Intervention.DISCOUNT_LINK:
            discount_pct = self.max_discount_pct
            recovery_amount = round(amount_inr * (1 - discount_pct / 100.0), 2)
            description = f"Here's {discount_pct:g}% off — complete order {order_id}"
        elif intervention is Intervention.UPI_RETRY_LINK:
            description = f"Retry payment via UPI for order {order_id}"
        elif intervention is Intervention.FRESH_RETRY_LINK:
            description = f"Your session expired — fresh payment link for order {order_id}"

        base.discount_pct = discount_pct
        base.recovery_amount_inr = recovery_amount

        if recovery_amount <= 0 or not customer_phone:
            base.status = RecoveryStatus.ESCALATED
            base.detail = "Missing customer contact or non-positive amount; cannot auto-recover."
            return base

        # Generate the payment link inside an audited before/after span.
        payload = {
            "amount": recovery_amount, "customer_name": customer_name,
            "customer_phone": customer_phone, "description": description,
        }
        reasoning = f"trigger={trigger.value}; root_cause={root_cause.value}; intervention={intervention.value}"
        with self.audit.trace(
            session_id, "generate_payment_link", payload,
            user_intent="revenue_recovery", agent_reasoning=reasoning,
        ) as span:
            result = self.tools.generate_payment_link(
                amount=recovery_amount, customer_name=customer_name,
                customer_phone=customer_phone, description=description,
            )
            ok = result.get("status") == "success"
            span.set_response(result, status="success" if ok else "failed")

        if not ok:
            base.status = RecoveryStatus.FAILED
            base.detail = f"payment link generation failed: {result.get('error')}"
            return base

        base.status = RecoveryStatus.RECOVERED_LINK_ISSUED
        base.payment_link = result.get("short_url")
        base.detail = (
            f"{intervention.value} issued for ₹{recovery_amount:g}"
            + (f" ({discount_pct:g}% off)" if discount_pct else "")
        )
        return base

    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_payment_entity(body: Dict[str, Any]) -> Dict[str, Any]:
        """Pull the payment entity from a Razorpay webhook body, defensively.

        Razorpay nests it at ``payload.payment.entity``; we fall back to a flat
        ``payload`` dict or the body itself so partial payloads still parse.
        """
        payload = body.get("payload", {})
        if isinstance(payload, dict):
            payment = payload.get("payment", {})
            if isinstance(payment, dict) and isinstance(payment.get("entity"), dict):
                return payment["entity"]
            if payment:
                return payment if isinstance(payment, dict) else {}
            if payload:
                return payload
        return body


#: Process-wide default recovery engine.
revenue_recovery_engine = RevenueRecoveryEngine()
