"""Tests for PaymentGuardrailValidator — the financial-safety gate."""

from __future__ import annotations

import pytest

from app.engine.guardrails import GuardrailViolation, PaymentGuardrailValidator
from app.engine.schemas import Currency, GuardrailDecision


def test_valid_charge_is_allowed(guardrails: PaymentGuardrailValidator):
    result = guardrails.validate_charge("create_order", 5000, Currency.INR)
    assert result.allowed
    assert result.decision is GuardrailDecision.ALLOW
    assert all(result.checks.values())


def test_amount_below_minimum_denied(guardrails: PaymentGuardrailValidator):
    result = guardrails.validate_charge("create_order", 50, Currency.INR)  # ₹0.50 < ₹1 min
    assert not result.allowed
    assert result.checks["above_minimum"] is False


def test_amount_above_maximum_denied(guardrails: PaymentGuardrailValidator):
    result = guardrails.validate_charge("create_order", 100_001, Currency.INR)
    assert not result.allowed
    assert result.checks["below_maximum"] is False


def test_daily_cap_enforced(guardrails: PaymentGuardrailValidator):
    # Cap is ₹1,500 (150_000 paise). Two ₹800 charges are fine; a third exceeds.
    for _ in range(2):
        guardrails.register_charge(80_000)
    result = guardrails.validate_charge("capture_payment", 80_000, Currency.INR)
    assert not result.allowed
    assert result.checks["within_daily_cap"] is False
    assert guardrails.daily_total() == 160_000


def test_idempotency_key_blocks_duplicates(guardrails: PaymentGuardrailValidator):
    first = guardrails.validate_charge("create_order", 5000, Currency.INR, "receipt-1")
    assert first.allowed
    guardrails.register_charge(5000, "receipt-1")
    second = guardrails.validate_charge("create_order", 5000, Currency.INR, "receipt-1")
    assert not second.allowed
    assert second.checks["idempotency_unique"] is False


def test_refund_cannot_exceed_captured(guardrails: PaymentGuardrailValidator):
    guardrails.register_capture("pay_1", 10_000)
    ok = guardrails.validate_refund("pay_1", 4_000)
    assert ok.allowed
    guardrails.register_refund("pay_1", 4_000)
    # Only 6,000 left refundable; 7,000 must be denied.
    over = guardrails.validate_refund("pay_1", 7_000)
    assert not over.allowed
    assert over.checks["within_refundable_balance"] is False


def test_refund_on_uncaptured_payment_denied(guardrails: PaymentGuardrailValidator):
    result = guardrails.validate_refund("pay_unknown", 1_000)
    assert not result.allowed
    assert result.checks["payment_is_captured"] is False


def test_guard_charge_raises_on_denial(guardrails: PaymentGuardrailValidator):
    with pytest.raises(GuardrailViolation):
        guardrails.guard_charge("create_order", 1, Currency.INR)  # below minimum
