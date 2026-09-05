"""Tests for the Claude tool-use loop and the tool registry.

A scripted fake Anthropic client feeds deterministic responses so the loop,
its stopping conditions, and tool execution can be verified offline.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from app.engine.agent import CommerceAgent
from app.engine.audit import AuditLogger
from app.engine.guardrails import PaymentGuardrailValidator
from app.engine.razorpay_client import RazorpayClient
from app.engine.schemas import ActionType, AgentRunRequest
from app.engine.tools import ToolContext, tool_registry


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
        return self._responses.pop(0)


class FakeAnthropic:
    def __init__(self, responses: List[SimpleNamespace]):
        self.messages = _FakeMessages(responses)


@pytest.fixture()
def agent_deps(razorpay: RazorpayClient, guardrails: PaymentGuardrailValidator, audit_logger: AuditLogger):
    """Provide a context_factory bound to isolated test dependencies."""
    def factory(session_id: str) -> ToolContext:
        return ToolContext(
            session_id=session_id, guardrails=guardrails, razorpay=razorpay, audit=audit_logger
        )

    return factory, audit_logger, guardrails


# --------------------------------------------------------------------------- #
# Tool registry (direct execution)
# --------------------------------------------------------------------------- #
def test_registry_exposes_anthropic_schemas():
    tools = tool_registry.anthropic_tools()
    names = {t["name"] for t in tools}
    assert {"create_razorpay_order", "refund_payment", "finalize"} <= names
    for tool in tools:
        assert "input_schema" in tool and tool["input_schema"]["type"] == "object"


def test_registry_rejects_invalid_arguments(agent_deps):
    factory, _, _ = agent_deps
    ctx = factory("s-val")
    ok, result = tool_registry.execute("create_razorpay_order", {"amount": -5}, ctx)
    assert not ok
    assert result["error"] == "validation_error"


def test_registry_guardrail_blocks_oversized_order(agent_deps):
    factory, _, _ = agent_deps
    ctx = factory("s-guard")
    ok, result = tool_registry.execute(
        "create_razorpay_order", {"amount": 999_999, "currency": "INR", "receipt": "r"}, ctx
    )
    assert not ok
    assert result["error"] == "guardrail_denied"


def test_registry_unknown_tool(agent_deps):
    factory, _, _ = agent_deps
    ok, result = tool_registry.execute("nope", {}, factory("s"))
    assert not ok and result["error"] == "unknown_tool"


# --------------------------------------------------------------------------- #
# Agent loop
# --------------------------------------------------------------------------- #
def test_agent_runs_order_then_finalizes(agent_deps):
    factory, audit, _ = agent_deps
    client = FakeAnthropic([
        _response([
            _text("Creating the order."),
            _tool_use("t1", "create_razorpay_order", {"amount": 5000, "currency": "INR", "receipt": "r1"}),
        ]),
        _response([_tool_use("t2", "finalize", {"summary": "Order created.", "success": True})]),
    ])
    agent = CommerceAgent(client=client, context_factory=factory, audit=audit)
    resp = agent.run(AgentRunRequest(instruction="Create an order for 5000 paise.", session_id="run-1"))

    assert resp.stop_reason == "finalized"
    assert resp.success is True
    assert resp.summary == "Order created."
    assert [c.tool for c in resp.tool_calls] == ["create_razorpay_order", "finalize"]
    assert resp.tool_calls[0].ok is True

    # Audit trail captured intent + guardrail + execution + output steps.
    trail = audit.get_trail("run-1")
    action_types = {r.action_type for r in trail}
    assert ActionType.INTENT in action_types
    assert ActionType.GUARDRAIL in action_types
    assert ActionType.TOOL_EXECUTION in action_types
    assert ActionType.OUTPUT in action_types


def test_agent_stops_on_end_turn(agent_deps):
    factory, audit, _ = agent_deps
    client = FakeAnthropic([_response([_text("Nothing to do here.")], stop_reason="end_turn")])
    agent = CommerceAgent(client=client, context_factory=factory, audit=audit)
    resp = agent.run(AgentRunRequest(instruction="Say hi.", session_id="run-2"))
    assert resp.stop_reason == "end_turn"
    assert resp.turns == 1
    assert resp.tool_calls == []


def test_agent_respects_max_turns(agent_deps, test_settings):
    factory, audit, _ = agent_deps
    test_settings.AGENT_MAX_TURNS = 3
    # Always ask for a (read-only) lookup, never finalize → must hit the ceiling.
    looping = [
        _response([_tool_use(f"t{i}", "lookup_product", {"query": "milk"})])
        for i in range(10)
    ]
    client = FakeAnthropic(looping)
    agent = CommerceAgent(client=client, context_factory=factory, audit=audit, config=test_settings)
    resp = agent.run(AgentRunRequest(instruction="loop forever", session_id="run-3"))
    assert resp.stop_reason == "max_turns"
    assert resp.turns == 3


def test_agent_missing_api_key_raises():
    from app.core.config import Settings

    cfg = Settings(ANTHROPIC_API_KEY="", _env_file=None)
    agent = CommerceAgent(config=cfg)  # no injected client → must try to build one
    with pytest.raises(RuntimeError):
        agent.run(AgentRunRequest(instruction="do something", session_id="run-4"))
