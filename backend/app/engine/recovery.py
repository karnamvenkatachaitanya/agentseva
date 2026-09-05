"""Deterministic payment-recovery engine.

A policy-driven (non-LLM) recovery flow for a single payment. It inspects the
payment's current state and applies the appropriate action, always routing
monetary moves through :class:`PaymentGuardrailValidator` and recording every
step to the append-only audit trail:

* ``captured``   → already collected, nothing to do (RECOVERED).
* ``authorized`` → capture the authorized amount (RECOVERED), retrying on
  transient transport failures up to ``max_retries``.
* ``failed``     → issue a fresh payment link for the customer (LINK_ISSUED).
* anything else  → ESCALATED for human follow-up.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from app.engine.audit import AuditLogger, audit_logger
from app.engine.guardrails import PaymentGuardrailValidator, payment_guardrails
from app.engine.razorpay_client import RazorpayClient, RazorpayError, razorpay_client
from app.engine.schemas import (
    ActionType,
    RecoveryOutcome,
    RecoveryRequest,
    RecoveryResponse,
)

logger = logging.getLogger(__name__)

#: Transport failure categories worth retrying (transient by nature).
_RETRYABLE = {"network", "timeout"}


class RecoveryEngine:
    """Recover a single failed / uncaptured Razorpay payment."""

    def __init__(
        self,
        razorpay: Optional[RazorpayClient] = None,
        guardrails: Optional[PaymentGuardrailValidator] = None,
        audit: Optional[AuditLogger] = None,
    ):
        self._razorpay = razorpay or razorpay_client
        self._guardrails = guardrails or payment_guardrails
        self._audit = audit or audit_logger

    def recover(self, request: RecoveryRequest) -> RecoveryResponse:
        """Run the recovery policy for ``request`` and return a structured outcome."""
        session_id = f"recovery_{uuid.uuid4().hex[:12]}"
        steps: List[str] = []
        self._audit.record(
            session_id, ActionType.RECOVERY, "recovery started",
            {"payment_id": request.payment_id, "amount": request.amount},
        )

        try:
            payment = self._razorpay.fetch_payment(request.payment_id)
        except RazorpayError as exc:
            self._audit.record(session_id, ActionType.ERROR, "fetch_payment failed during recovery",
                               {"category": exc.category, "message": str(exc)})
            return self._finish(session_id, request.payment_id, RecoveryOutcome.ESCALATED,
                                f"Could not fetch payment ({exc.category}): {exc}", steps)

        status = str(payment.get("status", "unknown"))
        steps.append(f"fetched payment status='{status}'")

        if status == "captured":
            return self._finish(session_id, request.payment_id, RecoveryOutcome.RECOVERED,
                                "Payment was already captured.", steps)

        if status == "authorized":
            return self._attempt_capture(session_id, request, steps)

        if status == "failed":
            return self._issue_link(session_id, request, steps)

        return self._finish(session_id, request.payment_id, RecoveryOutcome.ESCALATED,
                            f"Unhandled payment status '{status}'; escalating.", steps)

    # ------------------------------------------------------------------ #
    # Strategies
    # ------------------------------------------------------------------ #
    def _attempt_capture(self, session_id: str, request: RecoveryRequest, steps: List[str]) -> RecoveryResponse:
        verdict = self._guardrails.validate_charge("recovery_capture", request.amount, request.currency)
        self._audit.record(session_id, ActionType.GUARDRAIL, f"recovery_capture -> {verdict.decision.value}",
                           verdict.model_dump())
        if not verdict.allowed:
            steps.append(f"guardrail denied capture: {verdict.reason}")
            return self._finish(session_id, request.payment_id, RecoveryOutcome.ESCALATED,
                                f"Capture blocked by guardrail: {verdict.reason}", steps)

        last_error: Optional[RazorpayError] = None
        for attempt in range(1, request.max_retries + 2):  # first try + max_retries
            try:
                payment = self._razorpay.capture_payment(
                    payment_id=request.payment_id, amount=request.amount, currency=request.currency.value
                )
                self._guardrails.register_charge(request.amount)
                self._guardrails.register_capture(request.payment_id, request.amount)
                steps.append(f"captured on attempt {attempt}")
                self._audit.record(session_id, ActionType.TOOL_EXECUTION, "recovery capture succeeded", payment)
                return self._finish(session_id, request.payment_id, RecoveryOutcome.RECOVERED,
                                    "Authorized payment captured successfully.", steps)
            except RazorpayError as exc:
                last_error = exc
                steps.append(f"attempt {attempt} failed ({exc.category})")
                self._audit.record(session_id, ActionType.ERROR, f"capture attempt {attempt} failed",
                                   {"category": exc.category, "message": str(exc)})
                if exc.category not in _RETRYABLE:
                    break

        # Capture exhausted → fall back to issuing a payment link.
        steps.append("capture exhausted; falling back to payment link")
        return self._issue_link(session_id, request, steps, note=str(last_error) if last_error else None)

    def _issue_link(
        self, session_id: str, request: RecoveryRequest, steps: List[str], note: Optional[str] = None
    ) -> RecoveryResponse:
        reference_id = f"recover-{request.payment_id}"
        verdict = self._guardrails.validate_charge(
            "recovery_link", request.amount, request.currency, reference_id
        )
        self._audit.record(session_id, ActionType.GUARDRAIL, f"recovery_link -> {verdict.decision.value}",
                           verdict.model_dump())
        if not verdict.allowed:
            steps.append(f"guardrail denied link: {verdict.reason}")
            return self._finish(session_id, request.payment_id, RecoveryOutcome.ESCALATED,
                                f"Payment link blocked by guardrail: {verdict.reason}", steps)
        try:
            link = self._razorpay.create_payment_link(
                amount=request.amount,
                currency=request.currency.value,
                description=f"Payment recovery for {request.payment_id}",
                reference_id=reference_id,
                customer_contact=request.customer_contact,
                customer_email=request.customer_email,
            )
        except RazorpayError as exc:
            steps.append(f"payment link failed ({exc.category})")
            self._audit.record(session_id, ActionType.ERROR, "recovery link failed",
                               {"category": exc.category, "message": str(exc)})
            return self._finish(session_id, request.payment_id, RecoveryOutcome.ESCALATED,
                                f"Could not create payment link: {exc}", steps)

        self._guardrails.register_charge(request.amount, reference_id)
        short_url = link.get("short_url")
        steps.append(f"payment link issued: {short_url}")
        self._audit.record(session_id, ActionType.TOOL_EXECUTION, "recovery link issued", link)
        detail = "Issued a payment link for the customer to complete payment."
        if note:
            detail += f" (after capture failure: {note})"
        return self._finish(session_id, request.payment_id, RecoveryOutcome.LINK_ISSUED, detail, steps,
                            payment_link=short_url)

    # ------------------------------------------------------------------ #
    def _finish(
        self,
        session_id: str,
        payment_id: str,
        outcome: RecoveryOutcome,
        detail: str,
        steps: List[str],
        payment_link: Optional[str] = None,
    ) -> RecoveryResponse:
        self._audit.record(session_id, ActionType.OUTPUT, f"recovery finished: {outcome.value}",
                           {"detail": detail, "steps": steps})
        return RecoveryResponse(
            payment_id=payment_id, outcome=outcome, detail=detail, steps=steps, payment_link=payment_link
        )


#: Process-wide default recovery engine.
recovery_engine = RecoveryEngine()
