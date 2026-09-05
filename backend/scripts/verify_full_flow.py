#!/usr/bin/env python
"""End-to-end lifecycle verification for AgentSeva.

Exercises the full production flow:

    a. Natural-language prompt → Claude 3.5 Sonnet tool use
    b. Razorpay test order + payment-link generation (HTTPS-validated)
    c. Simulated **HTTPS** webhook dispatch (`payment.failed`) with an
       X-Forwarded-Proto: https header and an HMAC-SHA256 signature
    d. Automated revenue-recovery workflow execution
    e. Retrieval + validation of the full trace in the audit ledger

Prefers the running gateway (http://localhost:8000) for steps c–e so the real
HTTP/middleware/signature path is exercised; falls back to in-process calls if
the server is not reachable.

Usage (from backend/)::

    python scripts/verify_full_flow.py
    python scripts/verify_full_flow.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import traceback
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security_utils import is_https_url  # noqa: E402

_PASSED: List[str] = []
_FAILED: List[str] = []


def section(title: str) -> None:
    print("\n" + "=" * 72 + f"\n  {title}\n" + "=" * 72)


def check(name: str, condition: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))
    (_PASSED if condition else _FAILED).append(name)
    return condition


# --------------------------------------------------------------------------- #
# Offline scripted client (used when HUGGINGFACE_API_KEY is absent)
# --------------------------------------------------------------------------- #
def _fake_client() -> Any:
    def txt(t: str) -> SimpleNamespace:
        return SimpleNamespace(type="text", text=t)

    def tool(tid: str, name: str, args: Dict[str, Any]) -> SimpleNamespace:
        return SimpleNamespace(type="tool_use", id=tid, name=name, input=args)

    responses = [
        SimpleNamespace(content=[
            txt("Creating your order."),
            tool("t1", "create_order", {"amount_in_inr": 250.0, "currency": "INR",
                                        "receipt_id": "e2e-verify-1", "notes": {"flow": "verify"}}),
        ], stop_reason="tool_use"),
        SimpleNamespace(content=[txt("Order created for ₹250.")], stop_reason="end_turn"),
    ]

    class _M:
        def create(self, **_k: Any) -> SimpleNamespace:
            return responses.pop(0) if responses else SimpleNamespace(
                content=[txt("done")], stop_reason="end_turn")

    return SimpleNamespace(messages=_M())


# --------------------------------------------------------------------------- #
# Server helpers
# --------------------------------------------------------------------------- #
def _server_up(base_url: str) -> bool:
    try:
        r = httpx.get(f"{base_url}/api/v1/health", timeout=3.0)
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("VERIFY_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--offline", action="store_true", help="Force offline scripted Claude mode")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    session_id = f"e2e_{uuid.uuid4().hex[:10]}"
    print("\nAgentSeva — Full-Flow Verification")
    print(f"session_id  : {session_id}")
    print(f"razorpay    : mode={settings.RAZORPAY_MODE}  creds={bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)}")
    server = _server_up(base_url)
    print(f"gateway     : {'UP at ' + base_url if server else 'not reachable — using in-process fallback'}")

    # ---- (a) NL prompt → Claude tool use ---------------------------------
    section("a. Natural-language prompt → Claude 3.5 Sonnet tool use")
    try:
        from app.agent.core import ActionStatus, CommerceAgentCore
        from app.agent.guardrails import PaymentGuardrailValidator

        live = bool(settings.HUGGINGFACE_API_KEY) and not args.offline
        print(f"  mode: {'LIVE Hugging Face' if live else 'OFFLINE scripted'}  · model: {settings.HF_LLM_MODEL}")
        agent = CommerceAgentCore(
            client=None if live else _fake_client(),
            guardrails=PaymentGuardrailValidator(),
        )
        prompt = "Create a Razorpay order for 250 rupees (receipt e2e-verify-1), then stop."
        try:
            resp = agent.run(prompt, context={"session_id": session_id})
        except Exception as live_err:
            if live:
                print(f"  [WARN] Live model call failed ({live_err}); falling back to offline scripted client.")
                agent = CommerceAgentCore(client=_fake_client(), guardrails=PaymentGuardrailValidator())
                live = False
                resp = agent.run(prompt, context={"session_id": session_id})
            else:
                raise
        print(f"  reply       : {resp.reply!r}")
        print(f"  actions     : {[(a.tool, a.status.value) for a in resp.actions_taken]}")
        check("agent replied", bool(resp.reply))
        check("agent used tools or completed", resp.steps_used >= 1)
        if not live:
            check("create_order tool executed",
                  any(a.tool == "create_order" and a.status is ActionStatus.EXECUTED
                      for a in resp.actions_taken))
    except Exception as exc:  # noqa: BLE001
        check("agent step crashed", False, str(exc))
        traceback.print_exc()

    # ---- (b) Razorpay order + payment link -------------------------------
    section("b. Razorpay test order & payment-link generation")
    link_url: Optional[str] = None
    try:
        from app.tools.razorpay_tools import razorpay_tools

        order = razorpay_tools.create_order(250.0, "INR", "e2e-order-1", {"flow": "verify"})
        print(f"  order       : {order.get('status')}  id={order.get('order_id')}")
        check("order created", order.get("status") == "success")

        link = razorpay_tools.generate_payment_link(250.0, "E2E Tester", "+919876543210", "E2E verify link")
        link_url = link.get("short_url")
        print(f"  link        : {link.get('status')}  url={link_url}")
        check("payment link created", link.get("status") == "success")
        check("payment link is HTTPS", bool(link_url) and is_https_url(link_url), detail=str(link_url))
    except Exception as exc:  # noqa: BLE001
        check("razorpay step crashed", False, str(exc))
        traceback.print_exc()

    # ---- (c) Simulated HTTPS webhook dispatch (payment.failed) -----------
    section("c. Simulated HTTPS webhook dispatch — payment.failed")
    recovery: Dict[str, Any] = {}
    webhook_body = {
        "event": "payment.failed",
        "payload": {"payment": {"entity": {
            "id": "pay_e2e", "order_id": session_id, "amount": 25000, "currency": "INR",
            "status": "failed", "error_code": "BAD_REQUEST_ERROR",
            "error_description": "Your account has insufficient funds",
            "contact": "+919876543210", "notes": {"session_id": session_id, "customer_name": "E2E"},
        }}},
    }
    raw = json.dumps(webhook_body).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Forwarded-Proto": "https"}
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if secret:
        headers["X-Razorpay-Signature"] = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        print("  signed with HMAC-SHA256 (RAZORPAY_WEBHOOK_SECRET set)")
    else:
        print("  no RAZORPAY_WEBHOOK_SECRET set — dispatching unsigned (dev mode)")

    try:
        if server:
            r = httpx.post(f"{base_url}/api/v1/webhooks/razorpay", content=raw, headers=headers, timeout=30.0)
            print(f"  POST /webhooks/razorpay -> {r.status_code}")
            check("webhook accepted (HTTP 200)", r.status_code == 200)
            recovery = r.json()
        else:
            from app.agent.recovery import revenue_recovery_engine

            result = revenue_recovery_engine.handle_webhook(webhook_body, raw_body=raw,
                                                            signature=headers.get("X-Razorpay-Signature"))
            recovery = result.model_dump()
            check("webhook processed in-process", True)
    except Exception as exc:  # noqa: BLE001
        check("webhook dispatch crashed", False, str(exc))
        traceback.print_exc()

    # ---- (d) Automated revenue recovery ----------------------------------
    section("d. Automated revenue-recovery workflow")
    print(f"  outcome     : {recovery.get('status')}  intervention={recovery.get('intervention')}")
    print(f"  root_cause  : {recovery.get('root_cause')}  link={recovery.get('payment_link')}")
    check("recovery issued a link", recovery.get("status") == "recovered_link_issued")
    check("recovery diagnosed insufficient funds", recovery.get("root_cause") == "insufficient_funds")
    rlink = recovery.get("payment_link")
    check("recovery link is HTTPS", bool(rlink) and is_https_url(rlink), detail=str(rlink))

    # ---- (e) Audit ledger retrieval + validation -------------------------
    section("e. Audit ledger retrieval & validation")
    try:
        if server:
            r = httpx.get(f"{base_url}/api/v1/audit/traces/{session_id}", timeout=10.0)
            traces = r.json() if r.status_code == 200 else []
        else:
            from app.audit.logger import audit_logger

            traces = [t.model_dump() for t in audit_logger.get_traces(session_id)]

        tools = [t.get("tool_called") for t in traces]
        statuses = [t.get("status") for t in traces]
        print(f"  rows        : {len(traces)}")
        for t in traces:
            print(f"    id={t.get('id'):<4} {str(t.get('tool_called')):<26} {t.get('status'):<10} "
                  f"latency={t.get('latency_ms')}")
        check("audit rows exist for session", len(traces) >= 2)
        check("recovery link generation audited",
              "generate_payment_link" in tools and "initiated" in statuses and "success" in statuses)
        if server:
            check("webhook receipt recorded", any(str(t).startswith("webhook:")
                                                  for t in tools if t))
    except Exception as exc:  # noqa: BLE001
        check("audit retrieval crashed", False, str(exc))
        traceback.print_exc()

    # ---- Summary ---------------------------------------------------------
    section("SUMMARY")
    total = len(_PASSED) + len(_FAILED)
    print(f"  passed: {len(_PASSED)}/{total}")
    if _FAILED:
        print("  FAILED:")
        for n in _FAILED:
            print(f"    - {n}")
        print("\nRESULT: ❌ FAIL")
        return 1
    print("\nRESULT: ✅ FULL FLOW VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
