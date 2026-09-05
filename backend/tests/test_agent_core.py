"""Tests for the bounded agent state machine and the guardrail engine."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from app.agent.core import (
    MAX_EXECUTION_STEPS,
    ActionStatus,
    AgentState,
    CommerceAgentCore,
)
from app.agent.guardrails import (
    CircuitBreaker,
    GuardrailDecision,
    PaymentGuardrailValidator,
    RiskScorer,
)
from app.core.config import Settings
from app.tools.razorpay_tools import RazorpayToolRegistry


# --------------------------------------------------------------------------- #
# Scripted fake Anthropic client
# --------------------------------------------------------------------------- #
def _text(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_use(tool_id: str, name: str, tool_input: Dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=tool_input)


def _response(content: List[SimpleNamespace], stop_reason: str = "tool_use") -> SimpleNamespace:
    return SimpleNamespace(content=content, stop_reason=stop_reason)


class _FakeMessages:
    def __init__(self, responses: List[SimpleNamespace]):
        self._responses = list(responses)
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        # If the script runs dry, keep returning a benign "end turn".
        if not self._responses:
            return _response([_text("done")], stop_reason="end_turn")
        return self._responses.pop(0)


class FakeAnthropic:
    def __init__(self, responses: List[SimpleNamespace]):
        self.messages = _FakeMessages(responses)


def _order_args(inr: float, receipt: str = "r1", currency: str = "INR") -> Dict[str, Any]:
    return {"amount_in_inr": inr, "currency": currency, "receipt_id": receipt, "notes": {}}


@pytest.fixture()
def tools() -> RazorpayToolRegistry:
    """Mock Razorpay tools with default (₹50,000) bounds."""
    return RazorpayToolRegistry(config=Settings(_env_file=None))


@pytest.fixture()
def guardrails() -> PaymentGuardrailValidator:
    """Fresh guardrails with the spec caps: ₹50k order / ₹1L session."""
    return PaymentGuardrailValidator()


def _agent(client, guardrails, tools) -> CommerceAgentCore:
    return CommerceAgentCore(client=client, guardrails=guardrails, tools=tools)


# =========================================================================== #
# Guardrail engine
# =========================================================================== #
class TestGuardrails:
    def test_allow_within_limits(self, guardrails: PaymentGuardrailValidator):
        verdict = guardrails.validate(10_000_00)  # ₹10,000
        assert verdict.decision is GuardrailDecision.ALLOW
        assert verdict.allowed

    def test_deny_over_single_order_cap(self, guardrails: PaymentGuardrailValidator):
        verdict = guardrails.validate(60_000_00)  # ₹60,000 > ₹50,000
        assert verdict.decision is GuardrailDecision.DENY
        assert verdict.checks["within_single_order_cap"] is False

    def test_deny_over_session_cap(self, guardrails: PaymentGuardrailValidator):
        guardrails.register_spend(80_000_00)  # ₹80,000 already spent
        verdict = guardrails.validate(30_000_00)  # +₹30,000 → ₹1,10,000 > ₹1,00,000
        assert verdict.decision is GuardrailDecision.DENY
        assert verdict.checks["within_session_cap"] is False

    def test_require_confirmation_on_high_risk(self, guardrails: PaymentGuardrailValidator):
        verdict = guardrails.validate(10_000_00, risk_score=0.95)
        assert verdict.decision is GuardrailDecision.REQUIRE_CONFIRMATION
        assert verdict.requires_confirmation

    def test_reject_non_positive_amount(self, guardrails: PaymentGuardrailValidator):
        assert guardrails.validate(0).decision is GuardrailDecision.DENY
        assert guardrails.validate(-500).decision is GuardrailDecision.DENY

    def test_register_spend_tracks_remaining(self, guardrails: PaymentGuardrailValidator):
        guardrails.register_spend(25_000_00)
        assert guardrails.session_spent_paise == 25_000_00
        assert guardrails.session_remaining_paise == 75_000_00

    def test_circuit_breaker_opens_after_three_failures(self):
        breaker = CircuitBreaker(failure_threshold=3)
        breaker.record_failure()
        breaker.record_failure()
        assert not breaker.is_open
        breaker.record_failure()
        assert breaker.is_open

    def test_circuit_breaker_resets_on_success(self):
        breaker = CircuitBreaker(failure_threshold=3)
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()
        assert breaker.sequential_failures == 0
        assert not breaker.is_open

    def test_open_breaker_denies_validation(self, guardrails: PaymentGuardrailValidator):
        for _ in range(3):
            guardrails.record_api_failure()
        verdict = guardrails.validate(1_000_00)
        assert verdict.decision is GuardrailDecision.DENY
        assert verdict.checks["circuit_closed"] is False

    def test_risk_scorer_is_deterministic_and_bounded(self):
        scorer = RiskScorer()
        cap = 50_000_00
        low = scorer.score(1_000_00, cap)
        high = scorer.score(49_000_00, cap, {"new_customer": True, "prior_failure": True})
        assert 0.0 <= low <= high <= 1.0
        assert scorer.score(1_000_00, cap) == low  # deterministic


# =========================================================================== #
# Agent state machine
# =========================================================================== #
class TestAgentCore:
    def test_completes_with_no_tool_call(self, guardrails, tools):
        client = FakeAnthropic([_response([_text("Namaste! How can I help?")], stop_reason="end_turn")])
        resp = _agent(client, guardrails, tools).run("hello")
        assert resp.is_complete is True
        assert resp.requires_escalation is False
        assert resp.final_state is AgentState.COMPLETE
        assert resp.actions_taken == []
        assert resp.steps_used == 1

    def test_executes_order_then_finalizes(self, guardrails, tools):
        client = FakeAnthropic([
            _response([_tool_use("t1", "create_order", _order_args(100.0))]),
            _response([_text("Your order is created.")], stop_reason="end_turn"),
        ])
        resp = _agent(client, guardrails, tools).run("create an order for 100 rupees")
        assert resp.is_complete is True
        assert len(resp.actions_taken) == 1
        assert resp.actions_taken[0].status is ActionStatus.EXECUTED
        # Session spend recorded (₹100 = 10_000 paise).
        assert guardrails.session_spent_paise == 10_000

    def test_guardrail_blocks_order_over_cap(self, guardrails, tools):
        client = FakeAnthropic([
            _response([_tool_use("t1", "create_order", _order_args(60_000.0))]),  # ₹60k > ₹50k
            _response([_text("Sorry, that exceeds the limit.")], stop_reason="end_turn"),
        ])
        resp = _agent(client, guardrails, tools).run("create an order for 60000 rupees")
        assert resp.actions_taken[0].status is ActionStatus.BLOCKED
        assert guardrails.session_spent_paise == 0  # never executed
        assert resp.is_complete is True

    def test_high_risk_requires_escalation(self, guardrails, tools):
        client = FakeAnthropic([
            _response([_tool_use("t1", "create_order", _order_args(40_000.0))]),
        ])
        # new_customer pushes the score above the 0.70 threshold.
        resp = _agent(client, guardrails, tools).run(
            "big order", context={"risk_context": {"new_customer": True}}
        )
        assert resp.requires_escalation is True
        assert resp.is_complete is False
        assert resp.final_state is AgentState.AWAITING_CONFIRMATION
        assert resp.actions_taken[0].status is ActionStatus.PENDING_CONFIRMATION
        assert guardrails.session_spent_paise == 0  # not executed pending confirmation

    def test_circuit_breaker_escalates_after_three_failures(self, guardrails, tools):
        # Each order passes the guardrail (low amount) but fails at the tool
        # layer (disallowed currency) → three sequential API failures.
        bad = _order_args(100.0, currency="USD")
        client = FakeAnthropic([_response([_tool_use(f"t{i}", "create_order", bad)]) for i in range(3)])
        resp = _agent(client, guardrails, tools).run("loop of failures")
        assert resp.requires_escalation is True
        assert resp.is_complete is False
        assert resp.final_state is AgentState.ESCALATED
        assert guardrails.circuit_open is True
        assert all(a.status is ActionStatus.FAILED for a in resp.actions_taken)

    def test_bounded_at_max_steps(self, guardrails, tools):
        # Model keeps calling a read-only tool and never finalizes.
        looping = [
            _response([_tool_use(f"t{i}", "verify_payment_status",
                                 {"payment_id": "pay_1", "order_id": "order_1"})])
            for i in range(MAX_EXECUTION_STEPS + 3)
        ]
        resp = _agent(client=FakeAnthropic(looping), guardrails=guardrails, tools=tools).run("loop")
        assert resp.steps_used == MAX_EXECUTION_STEPS
        assert resp.is_complete is False
        assert resp.requires_escalation is True
        assert resp.final_state is AgentState.ESCALATED

    def test_missing_api_key_raises(self, guardrails, tools):
        cfg = Settings(ANTHROPIC_API_KEY="", _env_file=None)
        agent = CommerceAgentCore(guardrails=guardrails, tools=tools, config=cfg)  # no client
        with pytest.raises(RuntimeError):
            agent.run("do something")

    def test_deterministic_temperature_zero(self, guardrails, tools):
        client = FakeAnthropic([_response([_text("hi")], stop_reason="end_turn")])
        _agent(client, guardrails, tools).run("hello")
        assert client.messages.calls[0]["temperature"] == 0
