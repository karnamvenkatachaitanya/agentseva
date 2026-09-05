"""Tests for the production FastAPI gateway (app.main)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    # `with` triggers startup (init_db) / shutdown events.
    with TestClient(app) as c:
        yield c


def test_root(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "AgentSeva" in resp.json()["app"]


def test_health(client: TestClient):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    deps = body["dependencies"]
    assert "database" in deps and "razorpay_mode" in deps and "anthropic_configured" in deps


def test_metrics_shape(client: TestClient):
    resp = client.get("/api/v1/metrics")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "transactions_processed", "transactions_failed", "failure_rate",
        "money_recovered_inr", "recovery_links_issued", "active_sessions",
    ):
        assert key in body


def test_webhook_recovers_failed_payment(client: TestClient):
    body = {
        "event": "payment.failed",
        "payload": {"payment": {"entity": {
            "id": "pay_gw", "order_id": "gw_test_1", "amount": 250000, "currency": "INR",
            "error_description": "insufficient funds", "contact": "+919876543210",
            "notes": {"session_id": "gw_test_1"},
        }}},
    }
    resp = client.post("/api/v1/webhooks/razorpay", json=body)
    assert resp.status_code == 200
    assert resp.json()["status"] == "recovered_link_issued"

    # The audit trail for that session is now queryable end-to-end.
    traces = client.get("/api/v1/audit/traces/gw_test_1")
    assert traces.status_code == 200
    statuses = [t["status"] for t in traces.json()]
    assert "initiated" in statuses and "success" in statuses


def test_webhook_acknowledges_payment_captured(client: TestClient):
    body = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": "pay_cap", "order_id": "gw_cap_1", "amount": 25000, "currency": "INR",
            "status": "captured", "notes": {"session_id": "gw_cap_1"},
        }}},
    }
    resp = client.post("/api/v1/webhooks/razorpay", json=body)
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"
    # A captured settlement audit row was written.
    traces = client.get("/api/v1/audit/traces/gw_cap_1").json()
    assert any(t["status"] == "captured" for t in traces)


def test_webhook_acknowledges_payment_link_paid(client: TestClient):
    body = {
        "event": "payment_link.paid",
        "payload": {"payment_link": {"entity": {
            "id": "plink_paid", "amount": 90000, "amount_paid": 90000, "status": "paid",
            "notes": {"session_id": "gw_paid_1"},
        }}},
    }
    resp = client.post("/api/v1/webhooks/razorpay", json=body)
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"
    traces = client.get("/api/v1/audit/traces/gw_paid_1").json()
    assert any(t["status"] == "paid" for t in traces)


def test_webhook_ignores_unknown_event(client: TestClient):
    resp = client.post("/api/v1/webhooks/razorpay", json={"event": "subscription.charged", "payload": {}})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_rejects_bad_signature_when_secret_set(monkeypatch):
    # With a webhook secret configured, an invalid signature must be rejected.
    from app.core.config import settings as live_settings

    monkeypatch.setattr(live_settings, "RAZORPAY_WEBHOOK_SECRET", "whsec_test", raising=False)
    with TestClient(app) as c:
        resp = c.post(
            "/api/v1/webhooks/razorpay",
            json={"event": "payment.captured", "payload": {}},
            headers={"X-Razorpay-Signature": "deadbeef"},
        )
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_signature"


def test_webhook_rejects_invalid_json(client: TestClient):
    resp = client.post(
        "/api/v1/webhooks/razorpay", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_json"


def test_chat_validation_error(client: TestClient):
    resp = client.post("/api/v1/agent/chat", json={"message": ""})
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"


def test_chat_without_api_key_returns_503(client: TestClient):
    # In the test environment ANTHROPIC_API_KEY is unset → structured 503.
    from app.core.config import settings

    if settings.ANTHROPIC_API_KEY:
        pytest.skip("ANTHROPIC_API_KEY is configured; live agent path not exercised in tests.")
    resp = client.post("/api/v1/agent/chat", json={"message": "create an order for 250 rupees"})
    assert resp.status_code == 503
    assert resp.json()["error"] == "http_error"


def test_audit_traces_404_for_unknown_session(client: TestClient):
    resp = client.get("/api/v1/audit/traces/definitely-not-a-session-xyz")
    assert resp.status_code == 404
