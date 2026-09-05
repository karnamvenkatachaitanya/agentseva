"""Tests for the append-only audit logger and the revenue recovery engine."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.recovery import (
    CheckoutSnapshot,
    Intervention,
    RecoveryStatus,
    RevenueRecoveryEngine,
    RootCause,
)
from app.audit.logger import AuditLogger, TransactionAuditLog
from app.core.config import Settings
from app.db.base import Base
from app.tools.razorpay_tools import RazorpayToolRegistry


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture()
def audit() -> AuditLogger:
    """AuditLogger backed by a shared in-memory SQLite database."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return AuditLogger(session_factory=factory)


@pytest.fixture()
def tools() -> RazorpayToolRegistry:
    return RazorpayToolRegistry(config=Settings(_env_file=None))


@pytest.fixture()
def engine_(tools: RazorpayToolRegistry, audit: AuditLogger) -> RevenueRecoveryEngine:
    """Recovery engine with signature verification disabled (no secret)."""
    return RevenueRecoveryEngine(tools=tools, audit=audit, webhook_secret="")


def _failed_webhook(
    *, amount_paise: int = 100_000, description: str, reason: str = "", source: str = "",
    code: str = "BAD_REQUEST_ERROR", order_id: str = "order_1", contact: str = "+919876543210",
) -> Dict[str, Any]:
    return {
        "event": "payment.failed",
        "payload": {"payment": {"entity": {
            "id": "pay_1", "order_id": order_id, "amount": amount_paise, "currency": "INR",
            "status": "failed", "error_code": code, "error_description": description,
            "error_reason": reason, "error_source": source,
            "contact": contact, "notes": {"customer_name": "Asha", "session_id": order_id},
        }}},
    }


# =========================================================================== #
# Audit logger
# =========================================================================== #
class TestAuditLogger:
    def test_trace_writes_before_and_after(self, audit: AuditLogger):
        with audit.trace("s1", "generate_payment_link", {"amount": 100}) as span:
            span.set_response({"status": "success", "short_url": "https://x"}, status="success")
        traces = audit.get_traces("s1")
        assert len(traces) == 2
        assert traces[0].status == "initiated"
        assert traces[0].api_response is None
        assert traces[1].status == "success"
        assert traces[1].api_response["short_url"] == "https://x"
        assert traces[1].latency_ms is not None
        assert traces[0].trace_id == traces[1].trace_id  # paired

    def test_trace_records_error_and_reraises(self, audit: AuditLogger):
        with pytest.raises(ValueError):
            with audit.trace("s2", "create_order", {"a": 1}):
                raise ValueError("boom")
        traces = audit.get_traces("s2")
        assert [t.status for t in traces] == ["initiated", "error"]
        assert traces[1].api_response["error"] == "boom"

    def test_records_are_ordered_and_appended(self, audit: AuditLogger):
        audit.record("s3", "t1", "success")
        audit.record("s3", "t2", "success")
        traces = audit.get_traces("s3")
        assert [t.tool_called for t in traces] == ["t1", "t2"]
        assert traces[0].id < traces[1].id

    def test_payload_and_response_roundtrip(self, audit: AuditLogger):
        audit.record("s4", "tool", "success", payload_sent={"k": 1}, api_response={"ok": True})
        rec = audit.get_traces("s4")[0]
        assert rec.payload_sent == {"k": 1}
        assert rec.api_response == {"ok": True}

    def test_empty_session_returns_empty(self, audit: AuditLogger):
        assert audit.get_traces("nope") == []


# =========================================================================== #
# Recovery — webhook trigger
# =========================================================================== #
class TestWebhookRecovery:
    def test_insufficient_funds_gets_upi_retry(self, engine_: RevenueRecoveryEngine):
        body = _failed_webhook(description="Your account has insufficient funds")
        result = engine_.handle_webhook(body)
        assert result.root_cause is RootCause.INSUFFICIENT_FUNDS
        assert result.intervention is Intervention.UPI_RETRY_LINK
        assert result.status is RecoveryStatus.RECOVERED_LINK_ISSUED
        assert result.payment_link.startswith("https://rzp.io/i/")
        assert result.discount_pct is None  # no discount for bank issues

    def test_bank_decline_gets_upi_retry(self, engine_: RevenueRecoveryEngine):
        body = _failed_webhook(description="Payment was declined by the issuing bank")
        result = engine_.handle_webhook(body)
        assert result.root_cause is RootCause.BANK_DECLINE
        assert result.intervention is Intervention.UPI_RETRY_LINK

    def test_gateway_timeout_gets_fresh_link(self, engine_: RevenueRecoveryEngine):
        body = _failed_webhook(description="Payment gateway timeout while processing")
        result = engine_.handle_webhook(body)
        assert result.root_cause is RootCause.SESSION_TIMEOUT
        assert result.intervention is Intervention.FRESH_RETRY_LINK
        assert result.status is RecoveryStatus.RECOVERED_LINK_ISSUED

    def test_unknown_cause_escalates(self, engine_: RevenueRecoveryEngine):
        body = _failed_webhook(description="something totally unexpected", code="")
        result = engine_.handle_webhook(body)
        assert result.root_cause is RootCause.UNKNOWN
        assert result.intervention is Intervention.ESCALATE
        assert result.status is RecoveryStatus.ESCALATED
        assert result.payment_link is None

    def test_non_failed_event_is_ignored(self, engine_: RevenueRecoveryEngine):
        result = engine_.handle_webhook({"event": "payment.captured", "payload": {}})
        assert result.status is RecoveryStatus.IGNORED

    def test_webhook_writes_audit_trail(self, engine_: RevenueRecoveryEngine, audit: AuditLogger):
        body = _failed_webhook(description="insufficient funds", order_id="order_audit")
        engine_.handle_webhook(body)
        traces = audit.get_traces("order_audit")
        assert [t.status for t in traces] == ["initiated", "success"]
        assert traces[0].tool_called == "generate_payment_link"

    def test_missing_contact_escalates(self, engine_: RevenueRecoveryEngine):
        body = _failed_webhook(description="insufficient funds", contact="")
        result = engine_.handle_webhook(body)
        assert result.status is RecoveryStatus.ESCALATED
        assert "contact" in result.detail.lower()


# =========================================================================== #
# Recovery — signature verification
# =========================================================================== #
class TestWebhookSignature:
    def test_invalid_signature_rejected(self, tools, audit):
        engine_ = RevenueRecoveryEngine(tools=tools, audit=audit, webhook_secret="whsec")
        body = _failed_webhook(description="insufficient funds")
        raw = json.dumps(body).encode()
        result = engine_.handle_webhook(body, raw_body=raw, signature="deadbeef")
        assert result.status is RecoveryStatus.REJECTED

    def test_valid_signature_accepted(self, tools, audit):
        engine_ = RevenueRecoveryEngine(tools=tools, audit=audit, webhook_secret="whsec")
        body = _failed_webhook(description="insufficient funds")
        raw = json.dumps(body).encode()
        sig = hmac.new(b"whsec", raw, hashlib.sha256).hexdigest()
        result = engine_.handle_webhook(body, raw_body=raw, signature=sig)
        assert result.status is RecoveryStatus.RECOVERED_LINK_ISSUED


# =========================================================================== #
# Recovery — dropped checkout trigger
# =========================================================================== #
class TestCheckoutRecovery:
    def test_user_dropoff_gets_discount_link(self, engine_: RevenueRecoveryEngine):
        snap = CheckoutSnapshot(
            session_id="sess_drop", order_id="order_2", amount_inr=1000.0,
            customer_phone="+919876543210", last_stage="payment", idle_seconds=120,
            payment_attempted=False,
        )
        result = engine_.recover_dropped_checkout(snap)
        assert result.root_cause is RootCause.USER_DROPOFF
        assert result.intervention is Intervention.DISCOUNT_LINK
        assert result.discount_pct == 10.0
        assert result.recovery_amount_inr == 900.0  # 10% off ₹1000
        assert result.payment_link.startswith("https://rzp.io/i/")

    def test_long_idle_is_session_timeout(self, engine_: RevenueRecoveryEngine):
        snap = CheckoutSnapshot(
            session_id="sess_to", order_id="order_3", amount_inr=1000.0,
            customer_phone="+919876543210", last_stage="cart", idle_seconds=1000,
            payment_attempted=False,
        )
        result = engine_.recover_dropped_checkout(snap)
        assert result.root_cause is RootCause.SESSION_TIMEOUT
        assert result.intervention is Intervention.FRESH_RETRY_LINK
        assert result.recovery_amount_inr == 1000.0  # no discount

    def test_discount_never_exceeds_cap(self, tools, audit):
        engine_ = RevenueRecoveryEngine(tools=tools, audit=audit, webhook_secret="", max_discount_pct=5.0)
        snap = CheckoutSnapshot(
            session_id="sess_cap", order_id="order_4", amount_inr=2000.0,
            customer_phone="+919876543210", idle_seconds=60,
        )
        result = engine_.recover_dropped_checkout(snap)
        assert result.discount_pct == 5.0
        assert result.recovery_amount_inr == 1900.0
