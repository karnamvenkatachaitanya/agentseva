"""Unit tests for the bounded Razorpay tool registry.

Covers success paths and failure edge cases (validation, bounds, sanitisation,
signature verification, mock/live mode) — all offline via mock mode.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.tools.razorpay_tools import (
    RazorpayToolRegistry,
    compute_payment_signature,
    verify_payment_signature,
    verify_webhook_signature,
)


@pytest.fixture()
def registry(test_settings: Settings) -> RazorpayToolRegistry:
    """Registry in mock mode with test bounds (min ₹1, max ₹1,000)."""
    return RazorpayToolRegistry(config=test_settings)


# --------------------------------------------------------------------------- #
# Mode / mock fallback
# --------------------------------------------------------------------------- #
def test_defaults_to_mock_without_credentials(registry: RazorpayToolRegistry):
    assert registry.mode == "mock"
    assert registry.gateway.mock is True


def test_live_mode_when_credentials_present():
    cfg = Settings(RAZORPAY_KEY_ID="rzp_test_x", RAZORPAY_KEY_SECRET="secret", _env_file=None)
    reg = RazorpayToolRegistry(config=cfg)
    assert reg.mode == "live"
    assert reg.gateway.mock is False


# --------------------------------------------------------------------------- #
# create_order
# --------------------------------------------------------------------------- #
def test_create_order_success(registry: RazorpayToolRegistry):
    result = registry.create_order(500.0, "INR", "order-001", {"channel": "kiosk"})
    assert result["status"] == "success"
    assert result["amount_in_paise"] == 50_000
    assert result["order_id"].startswith("order_mock_")
    assert result["currency"] == "INR"


def test_create_order_rejects_amount_above_max(registry: RazorpayToolRegistry):
    result = registry.create_order(2000.0, "INR", "order-002", {})  # ₹2,000 > ₹1,000 max
    assert result["status"] == "error"
    assert result["error"] == "amount_above_maximum"


def test_create_order_rejects_amount_below_min(registry: RazorpayToolRegistry):
    result = registry.create_order(0.50, "INR", "order-003", {})  # 50 paise < ₹1 min
    assert result["status"] == "error"
    assert result["error"] == "amount_below_minimum"


def test_create_order_rejects_zero_and_negative(registry: RazorpayToolRegistry):
    for bad in (0.0, -100.0):
        result = registry.create_order(bad, "INR", "order-x", {})
        assert result["status"] == "error"
        assert result["error"] == "validation_error"


def test_create_order_rejects_sub_paise_precision(registry: RazorpayToolRegistry):
    result = registry.create_order(100.999, "INR", "order-004", {})
    assert result["status"] == "error"
    assert result["error"] == "validation_error"


def test_create_order_rejects_disallowed_currency(registry: RazorpayToolRegistry):
    result = registry.create_order(100.0, "USD", "order-005", {})
    assert result["status"] == "error"
    assert result["error"] == "currency_not_allowed"


def test_create_order_rejects_malformed_currency(registry: RazorpayToolRegistry):
    result = registry.create_order(100.0, "US", "order-006", {})  # not 3 chars
    assert result["status"] == "error"
    assert result["error"] == "validation_error"


def test_create_order_sanitizes_receipt(registry: RazorpayToolRegistry):
    result = registry.create_order(100.0, "INR", "  order\x00-\n07  ", {})
    assert result["status"] == "success"
    assert result["receipt_id"] == "order-07"  # control chars + whitespace stripped


def test_create_order_rejects_empty_receipt_after_sanitisation(registry: RazorpayToolRegistry):
    result = registry.create_order(100.0, "INR", "\x00\x01", {})
    assert result["status"] == "error"
    assert result["error"] == "validation_error"


def test_create_order_rejects_too_many_notes(registry: RazorpayToolRegistry):
    notes = {f"k{i}": "v" for i in range(20)}
    result = registry.create_order(100.0, "INR", "order-008", notes)
    assert result["status"] == "error"
    assert result["error"] == "validation_error"


# --------------------------------------------------------------------------- #
# generate_payment_link
# --------------------------------------------------------------------------- #
def test_payment_link_success(registry: RazorpayToolRegistry):
    result = registry.generate_payment_link(250.0, "Asha Devi", "+91 98765-43210", "Grocery bill")
    assert result["status"] == "success"
    assert result["short_url"].startswith("https://rzp.io/i/")
    assert result["customer_phone"] == "+919876543210"  # normalised
    assert result["amount_in_paise"] == 25_000


def test_payment_link_rejects_invalid_phone(registry: RazorpayToolRegistry):
    result = registry.generate_payment_link(250.0, "Asha", "not-a-phone", "Bill")
    assert result["status"] == "error"
    assert result["error"] == "validation_error"


def test_payment_link_rejects_too_short_phone(registry: RazorpayToolRegistry):
    result = registry.generate_payment_link(250.0, "Asha", "12345", "Bill")
    assert result["status"] == "error"
    assert result["error"] == "validation_error"


def test_payment_link_respects_amount_bounds(registry: RazorpayToolRegistry):
    result = registry.generate_payment_link(5000.0, "Asha", "+919876543210", "Bill")
    assert result["status"] == "error"
    assert result["error"] == "amount_above_maximum"


# --------------------------------------------------------------------------- #
# verify_payment_status + HMAC-SHA256
# --------------------------------------------------------------------------- #
def test_verify_status_captured_is_paid(registry: RazorpayToolRegistry):
    result = registry.verify_payment_status("pay_success_1", "order_1")
    assert result["status"] == "success"
    assert result["payment_status"] == "captured"
    assert result["is_paid"] is True
    assert result["signature_valid"] is None  # no signature supplied


def test_verify_status_failed_not_paid(registry: RazorpayToolRegistry):
    result = registry.verify_payment_status("pay_fail_1", "order_1")
    assert result["payment_status"] == "failed"
    assert result["is_paid"] is False


def test_verify_valid_signature(registry: RazorpayToolRegistry):
    secret = registry.gateway.effective_secret
    sig = compute_payment_signature("order_9", "pay_9", secret)
    result = registry.verify_payment_status("pay_9", "order_9", signature=sig)
    assert result["signature_valid"] is True


def test_verify_invalid_signature(registry: RazorpayToolRegistry):
    result = registry.verify_payment_status("pay_9", "order_9", signature="deadbeef")
    assert result["signature_valid"] is False


def test_verify_rejects_empty_ids(registry: RazorpayToolRegistry):
    result = registry.verify_payment_status("\x00", "order_1")
    assert result["status"] == "error"
    assert result["error"] == "validation_error"


def test_hmac_helpers_are_constant_time_correct():
    secret = "s3cr3t"
    sig = compute_payment_signature("o1", "p1", secret)
    assert verify_payment_signature("o1", "p1", sig, secret) is True
    assert verify_payment_signature("o1", "p1", sig, "wrong") is False
    assert verify_payment_signature("o1", "p1", "", secret) is False


def test_webhook_signature_verification():
    secret = "whsec"
    body = b'{"event":"payment.captured"}'
    import hashlib
    import hmac

    good = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, good, secret) is True
    assert verify_webhook_signature(body, "bad", secret) is False


# --------------------------------------------------------------------------- #
# trigger_payment_recovery
# --------------------------------------------------------------------------- #
def test_recovery_with_known_order_issues_link(registry: RazorpayToolRegistry):
    created = registry.create_order(300.0, "INR", "order-rec", {})
    order_id = created["order_id"]
    result = registry.trigger_payment_recovery(order_id, "Card declined: insufficient balance", "sms")
    assert result["status"] == "success"
    assert result["strategy"] == "suggest_alternate_instrument"
    assert result["payment_link"].startswith("https://rzp.io/i/")
    assert result["next_action"] == "notify_customer_via_sms"


def test_recovery_unknown_order_has_no_link(registry: RazorpayToolRegistry):
    result = registry.trigger_payment_recovery("order_unknown", "gateway timeout", "whatsapp")
    assert result["status"] == "success"
    assert result["payment_link"] is None
    assert result["strategy"] == "immediate_retry_same_channel"
    assert "unavailable" in result["note"]


def test_recovery_rejects_invalid_channel(registry: RazorpayToolRegistry):
    result = registry.trigger_payment_recovery("order_1", "cancelled by user", "pigeon")
    assert result["status"] == "error"
    assert result["error"] == "validation_error"


def test_recovery_strategy_mapping(registry: RazorpayToolRegistry):
    assert registry._recovery_strategy("user abandoned checkout") == "dunning_reminder_sequence"
    assert registry._recovery_strategy("some other reason") == "reissue_payment_link"


# --------------------------------------------------------------------------- #
# Tool schemas
# --------------------------------------------------------------------------- #
def test_anthropic_tool_schemas(registry: RazorpayToolRegistry):
    tools = registry.anthropic_tools()
    names = {t["name"] for t in tools}
    assert names == {
        "search_product_catalog", "create_order", "generate_payment_link",
        "verify_payment_status", "trigger_payment_recovery",
    }
    for tool in tools:
        assert tool["input_schema"]["type"] == "object"
