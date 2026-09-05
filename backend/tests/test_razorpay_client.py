"""Tests for the Razorpay client — mock backend + error mapping."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.engine.razorpay_client import RazorpayClient, RazorpayError


def test_mock_create_order(razorpay: RazorpayClient):
    order = razorpay.create_order(amount=5000, currency="INR", receipt="r1", notes={})
    assert order["id"].startswith("order_mock_")
    assert order["amount"] == 5000
    assert order["status"] == "created"


def test_mock_payment_link_has_short_url(razorpay: RazorpayClient):
    link = razorpay.create_payment_link(
        amount=5000, currency="INR", description="pay", reference_id="ref1"
    )
    assert link["short_url"].startswith("https://rzp.io/i/")


def test_mock_fetch_derives_failed_status(razorpay: RazorpayClient):
    payment = razorpay.fetch_payment("pay_fail_123")
    assert payment["status"] == "failed"


def test_mock_fetch_derives_authorized_status(razorpay: RazorpayClient):
    payment = razorpay.fetch_payment("pay_ok_123")
    assert payment["status"] == "authorized"


def test_mock_capture_and_refund(razorpay: RazorpayClient):
    captured = razorpay.capture_payment(payment_id="pay_1", amount=5000, currency="INR")
    assert captured["status"] == "captured"
    refund = razorpay.refund_payment(payment_id="pay_1", amount=2000)
    assert refund["entity"] == "refund"
    assert refund["amount"] == 2000


def test_seeded_payment_state(razorpay: RazorpayClient):
    razorpay.mock.seed_payment("pay_x", status="captured", amount=9000)
    assert razorpay.fetch_payment("pay_x")["status"] == "captured"


def test_live_mode_without_credentials_raises_auth_error():
    cfg = Settings(RAZORPAY_MODE="live", RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="", _env_file=None)
    client = RazorpayClient(config=cfg)
    with pytest.raises(RazorpayError) as excinfo:
        client.create_order(amount=5000, currency="INR", receipt="r1", notes={})
    assert excinfo.value.category == "auth"
