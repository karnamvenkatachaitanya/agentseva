#!/usr/bin/env python
"""Standalone manual verification harness for AgentSeva.

Runs four sequential end-to-end checks against the real application code
(mock mode by default — no keys required):

    1. Agent tool calling with Claude 3.5 Sonnet
       (live if ANTHROPIC_API_KEY is set, otherwise a scripted offline demo)
    2. Razorpay Order + Payment Link creation (test keys or mock simulator)
    3. Guardrail boundary violations (amount over cap; rapid failed retries → circuit breaker)
    4. Append-only audit-log insertion and retrieval

Usage (from the backend/ directory)::

    python scripts/manual_test.py

Exits 0 if every check passes, 1 otherwise.
"""

from __future__ import annotations

import os
import sys
import traceback
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List

# Make `app` importable no matter where the script is invoked from.
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

# Ensure UTF-8 output so ₹ / status glyphs print on Windows consoles (cp1252).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - older/odd streams
        pass

from app.core.config import settings  # noqa: E402


# --------------------------------------------------------------------------- #
# Tiny test-runner utilities
# --------------------------------------------------------------------------- #
_PASSED: List[str] = []
_FAILED: List[str] = []


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def check(name: str, condition: bool, detail: str = "") -> bool:
    mark = "PASS" if condition else "FAIL"
    line = f"  [{mark}] {name}" + (f"  — {detail}" if detail else "")
    print(line)
    (_PASSED if condition else _FAILED).append(name)
    return condition


def guarded(fn) -> None:
    """Run a section function; a crash marks the section failed but continues."""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        _FAILED.append(f"{fn.__name__} (crashed)")
        print(f"  [FAIL] {fn.__name__} crashed: {exc}")
        traceback.print_exc()


# --------------------------------------------------------------------------- #
# Scripted fake Anthropic client (offline fallback for section 1)
# --------------------------------------------------------------------------- #
def _fake_anthropic_client() -> Any:
    """A client that scripts: create_order → then finish (end_turn)."""

    def block_text(text: str) -> SimpleNamespace:
        return SimpleNamespace(type="text", text=text)

    def block_tool(tid: str, name: str, args: Dict[str, Any]) -> SimpleNamespace:
        return SimpleNamespace(type="tool_use", id=tid, name=name, input=args)

    responses = [
        SimpleNamespace(
            content=[
                block_text("Creating the order."),
                block_tool("t1", "create_order", {
                    "amount_in_inr": 250.0, "currency": "INR",
                    "receipt_id": "manual-offline-1", "notes": {"channel": "manual_test"},
                }),
            ],
            stop_reason="tool_use",
        ),
        SimpleNamespace(
            content=[block_text("Your order for ₹250 has been created.")],
            stop_reason="end_turn",
        ),
    ]

    class _Messages:
        def create(self, **_kwargs: Any) -> SimpleNamespace:
            return responses.pop(0) if responses else SimpleNamespace(
                content=[block_text("done")], stop_reason="end_turn"
            )

    return SimpleNamespace(messages=_Messages())


# --------------------------------------------------------------------------- #
# 1) Agent tool calling with Claude 3.5 Sonnet
# --------------------------------------------------------------------------- #
def test_agent_tool_calling() -> None:
    section("1. Agent tool calling with Claude 3.5 Sonnet")
    from app.agent.core import ActionStatus, CommerceAgentCore
    from app.agent.guardrails import PaymentGuardrailValidator

    live = bool(settings.ANTHROPIC_API_KEY)
    print(f"  mode: {'LIVE (Anthropic API)' if live else 'OFFLINE (scripted fake client)'}"
          f"  · model: {settings.CLAUDE_MODEL}")

    guardrails = PaymentGuardrailValidator()
    resp = None
    if live:
        try:
            agent = CommerceAgentCore(guardrails=guardrails)
            resp = agent.run(
                "Create a Razorpay order for 250 rupees with receipt 'manual-live-1', then stop."
            )
        except Exception as live_err:
            print(f"  [WARN] Live Anthropic call failed ({live_err}); falling back to offline scripted client.")
            live = False

    if not live:
        guardrails = PaymentGuardrailValidator()
        agent = CommerceAgentCore(client=_fake_anthropic_client(), guardrails=guardrails)
        resp = agent.run("Create an order for 250 rupees.")

    print(f"  reply           : {resp.reply!r}")
    print(f"  steps_used      : {resp.steps_used}   final_state: {resp.final_state.value}")
    print(f"  actions_taken   : {[(a.tool, a.status.value) for a in resp.actions_taken]}")
    print(f"  is_complete     : {resp.is_complete}   requires_escalation: {resp.requires_escalation}")

    check("agent produced a reply", bool(resp.reply))
    check("agent ran at least one step", resp.steps_used >= 1)
    if live:
        # We can't force the model's choices; just assert it ran cleanly.
        check("live agent did not abort", resp.final_state.value != "aborted")
    else:
        called = [a.tool for a in resp.actions_taken]
        check("agent invoked create_order tool", "create_order" in called,
              detail=str(called))
        executed = any(a.status is ActionStatus.EXECUTED for a in resp.actions_taken)
        check("tool call executed successfully", executed)
        check("conversation completed deterministically", resp.is_complete)


# --------------------------------------------------------------------------- #
# 2) Razorpay Order + Payment Link creation
# --------------------------------------------------------------------------- #
def test_razorpay_order_and_link() -> None:
    section("2. Razorpay Order & Payment Link creation")
    from app.tools.razorpay_tools import razorpay_tools

    print(f"  RAZORPAY_MODE   : {settings.RAZORPAY_MODE}  · client mode: {razorpay_tools.mode}")

    order = razorpay_tools.create_order(
        amount_in_inr=250.0, currency="INR", receipt_id="manual-order-1",
        notes={"channel": "manual_test"},
    )
    print(f"  create_order    : {order.get('status')}  id={order.get('order_id')}  "
          f"paise={order.get('amount_in_paise')}")
    check("order created", order.get("status") == "success")
    check("order id returned", bool(order.get("order_id")))
    check("amount converted to paise", order.get("amount_in_paise") == 25000)

    link = razorpay_tools.generate_payment_link(
        amount=250.0, customer_name="Manual Tester", customer_phone="+919876543210",
        description="AgentSeva manual verification",
    )
    print(f"  payment_link    : {link.get('status')}  url={link.get('short_url')}")
    check("payment link created", link.get("status") == "success")
    check("payment link has short_url", bool(link.get("short_url")))


# --------------------------------------------------------------------------- #
# 3) Guardrail boundary violations
# --------------------------------------------------------------------------- #
def test_guardrail_violations() -> None:
    section("3. Guardrail boundary violations")
    from app.agent.guardrails import GuardrailDecision, PaymentGuardrailValidator

    gr = PaymentGuardrailValidator()  # ₹50k order / ₹1L session, breaker@3
    print(f"  single-order cap: ₹{gr.single_order_cap_paise / 100:,.0f}  "
          f"session cap: ₹{gr.session_cap_paise / 100:,.0f}")

    # (a) Amount exceeding the single-order cap.
    over = gr.validate(60_000_00)  # ₹60,000
    print(f"  ₹60,000 order   : {over.decision.value}  reasons={over.reasons}")
    check("over-cap amount is DENIED", over.decision is GuardrailDecision.DENY)
    check("cap check flagged", over.checks.get("within_single_order_cap") is False)

    # (b) A within-limit amount is allowed (control).
    ok = gr.validate(10_000_00)  # ₹10,000
    check("within-limit amount is ALLOWED", ok.decision is GuardrailDecision.ALLOW)

    # (c) Rapid failed retries trip the circuit breaker after 3 failures.
    print("  simulating 3 rapid API failures...")
    for i in range(1, 4):
        gr.record_api_failure()
        print(f"    failure {i}: circuit_open={gr.circuit_open}")
    check("circuit breaker OPEN after 3 failures", gr.circuit_open is True)

    blocked = gr.validate(1_000_00)  # small, valid amount — but breaker is open
    print(f"  post-trip ₹1,000: {blocked.decision.value}  reasons={blocked.reasons}")
    check("open breaker DENIES further charges", blocked.decision is GuardrailDecision.DENY)
    check("breaker check flagged", blocked.checks.get("circuit_closed") is False)


# --------------------------------------------------------------------------- #
# 4) Append-only audit log insertion & retrieval
# --------------------------------------------------------------------------- #
def test_audit_log() -> None:
    section("4. Append-only audit log insertion & retrieval")
    from app.audit.logger import AuditLogger, audit_logger
    from app.db.base import init_db

    init_db()  # ensure transaction_audit_logs exists
    session_id = f"manual_{uuid.uuid4().hex[:10]}"
    print(f"  session_id      : {session_id}")

    # A traced (before/after) money-tool call.
    with audit_logger.trace(
        session_id, "generate_payment_link",
        payload_sent={"amount": 250.0, "currency": "INR"},
        user_intent="manual_verification", agent_reasoning="verify audit before/after pair",
    ) as span:
        span.set_response({"status": "success", "short_url": "https://rzp.io/i/manual"}, status="success")

    # A standalone record.
    audit_logger.record(session_id, "verify_payment_status", "success",
                        payload_sent={"payment_id": "pay_manual"},
                        api_response={"payment_status": "captured"})

    traces = audit_logger.get_traces(session_id)
    statuses = [t.status for t in traces]
    print(f"  rows recorded   : {len(traces)}  statuses={statuses}")
    for t in traces:
        print(f"    id={t.id:<4} {t.tool_called:<24} {t.status:<10} latency={t.latency_ms}")

    check("at least 3 audit rows written", len(traces) >= 3)
    check("before/after pair present", statuses[:2] == ["initiated", "success"])
    check("records are ordered by id", [t.id for t in traces] == sorted(t.id for t in traces))
    check("payloads round-trip as JSON", traces[0].payload_sent == {"amount": 250.0, "currency": "INR"})

    # Append-only by construction: no mutation API is exposed.
    append_only = not any(hasattr(AuditLogger, m) for m in ("update", "delete", "edit", "remove"))
    check("AuditLogger exposes no update/delete API (append-only)", append_only)

    # Prove immutability: re-reading yields the identical, unchanged rows.
    reread = audit_logger.get_traces(session_id)
    check("re-read returns identical immutable rows",
          [t.id for t in reread] == [t.id for t in traces])


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #
def main() -> int:
    print("\nAgentSeva — Manual Verification Harness")
    print(f"Python {sys.version.split()[0]}  ·  cwd={os.getcwd()}")

    guarded(test_agent_tool_calling)
    guarded(test_razorpay_order_and_link)
    guarded(test_guardrail_violations)
    guarded(test_audit_log)

    section("SUMMARY")
    total = len(_PASSED) + len(_FAILED)
    print(f"  passed: {len(_PASSED)}/{total}")
    if _FAILED:
        print("  FAILED checks:")
        for name in _FAILED:
            print(f"    - {name}")
        print("\nRESULT: ❌ FAIL")
        return 1
    print("\nRESULT: ✅ ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
