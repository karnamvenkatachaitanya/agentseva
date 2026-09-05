"""Bounded agent core: a deterministic, guardrailed commerce state machine.

The agent drives Claude 3.5 Sonnet through a **bounded** tool-use conversation
(at most :data:`MAX_EXECUTION_STEPS` = 6 model turns) so a single conversation
turn can never run away. Every money-moving tool call is gated by
:class:`~app.agent.guardrails.PaymentGuardrailValidator` *before* execution;
high-risk actions short-circuit into a human-in-the-loop escalation.

State machine
-------------
``INIT → THINKING → (VALIDATING → TOOL_CALL)* → COMPLETE``
with early exits to ``AWAITING_CONFIRMATION`` (risk), ``ESCALATED`` (circuit
breaker / step ceiling), or ``ABORTED`` (fatal error).

The public entrypoint :meth:`CommerceAgentCore.run` returns a structured
:class:`AgentResponse`.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings, settings
from app.agent.guardrails import GuardrailDecision, PaymentGuardrailValidator
from app.tools.razorpay_tools import RazorpayToolRegistry, razorpay_tools

logger = logging.getLogger(__name__)

#: Hard ceiling on model turns per conversation turn (runaway-loop guard).
MAX_EXECUTION_STEPS = 6

#: Tools whose invocation moves money and therefore must pass the guardrail.
MONETARY_TOOLS = {"create_order", "generate_payment_link"}

SYSTEM_PROMPT = (
    "You are the AgentSeva payments agent for an Indian Kirana store, operating under STRICT "
    "financial controls. You act ONLY through the provided tools and must respect these hard "
    "constraints, which are also enforced in code:\n"
    "- Single order/payment amount MUST NOT exceed ₹50,000.\n"
    "- Cumulative amount across this session MUST NOT exceed ₹1,00,000.\n"
    "- Amounts are in INR (rupees) with at most 2 decimal places.\n"
    "- Never invent product prices. To sell products, FIRST call search_product_catalog to get "
    "real product ids and prices, then pass those ids as `items` (e.g. "
    "[{\"product_id\": 1, \"quantity\": 2}]) to create_order / generate_payment_link so the "
    "total is computed from the real catalog. Put the customer's name/phone in `notes` for "
    "create_order, or the dedicated fields for generate_payment_link.\n"
    "- If a tool call is blocked by a guardrail, do NOT retry the same call blindly; either "
    "adjust within limits or explain that the action cannot proceed.\n"
    "- High-value or high-risk transactions may require human confirmation; if a tool result "
    "indicates confirmation is required, stop and tell the user.\n"
    "- You have a strict budget of at most six tool-use steps; be efficient and finish promptly.\n"
    "When the task is done, reply with a short plain-language message and no further tool calls."
)


# --------------------------------------------------------------------------- #
# State + result models
# --------------------------------------------------------------------------- #


class AgentState(str, Enum):
    """States of the bounded execution machine."""

    INIT = "init"
    THINKING = "thinking"
    VALIDATING = "validating"
    TOOL_CALL = "tool_call"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    ESCALATED = "escalated"
    COMPLETE = "complete"
    ABORTED = "aborted"


class ActionStatus(str, Enum):
    """Outcome of a single attempted tool action."""

    EXECUTED = "executed"
    BLOCKED = "blocked"
    FAILED = "failed"
    PENDING_CONFIRMATION = "pending_confirmation"


class Action(BaseModel):
    """A single tool action attempted during the turn."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    status: ActionStatus
    detail: str = ""
    result: Dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Structured response returned by :meth:`CommerceAgentCore.run`."""

    model_config = ConfigDict(extra="forbid")

    reply: str
    actions_taken: List[Action] = Field(default_factory=list)
    is_complete: bool
    requires_escalation: bool
    # Diagnostics — useful for the API layer and audits.
    steps_used: int = 0
    final_state: AgentState = AgentState.INIT


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _block_attr(block: Any, name: str, default: Any = None) -> Any:
    """Read an attribute from an SDK block or a plain dict uniformly."""
    if isinstance(block, dict):
        return block.get(name, default)
    return getattr(block, name, default)


def _normalize_assistant_content(content: List[Any]) -> List[Dict[str, Any]]:
    """Rebuild assistant content as plain dicts to feed back to the API."""
    out: List[Dict[str, Any]] = []
    for block in content:
        btype = _block_attr(block, "type")
        if btype == "text":
            out.append({"type": "text", "text": _block_attr(block, "text", "")})
        elif btype == "tool_use":
            out.append({
                "type": "tool_use",
                "id": _block_attr(block, "id"),
                "name": _block_attr(block, "name"),
                "input": _block_attr(block, "input", {}) or {},
            })
    return out


def _amount_to_paise(raw: Any) -> Optional[int]:
    """Best-effort INR→paise conversion for guardrail pre-checks.

    Returns ``None`` if the value is missing or unparseable — in that case the
    tool's own Pydantic validation will reject it downstream.
    """
    if raw is None:
        return None
    try:
        dec = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    if not dec.is_finite():
        return None
    return int((dec * 100).to_integral_value())


# --------------------------------------------------------------------------- #
# Agent core
# --------------------------------------------------------------------------- #


class CommerceAgentCore:
    """Bounded, guardrailed Claude tool-use agent.

    Parameters
    ----------
    client:
        An Anthropic-compatible client. If ``None`` a real
        ``anthropic.Anthropic()`` is created lazily on first run (requires
        ``ANTHROPIC_API_KEY``). Tests inject a scripted fake.
    guardrails:
        A :class:`PaymentGuardrailValidator`; a fresh one is created by default.
    tools:
        A :class:`RazorpayToolRegistry`; the process default is used otherwise.
    config:
        Settings (model id, token budget). Defaults to the global settings.
    """

    def __init__(
        self,
        client: Optional[Any] = None,
        guardrails: Optional[PaymentGuardrailValidator] = None,
        tools: Optional[RazorpayToolRegistry] = None,
        config: Optional[Settings] = None,
    ):
        self._cfg = config or settings
        self._client = client
        self.guardrails = guardrails or PaymentGuardrailValidator()
        self.tools = tools or razorpay_tools
        self._dispatch: Dict[str, Callable[[Dict[str, Any]], dict]] = {
            "search_product_catalog": lambda a: self.tools.search_product_catalog(**a),
            "create_order": lambda a: self.tools.create_order(**a),
            "generate_payment_link": lambda a: self.tools.generate_payment_link(**a),
            "verify_payment_status": lambda a: self.tools.verify_payment_status(**a),
            "trigger_payment_recovery": lambda a: self.tools.trigger_payment_recovery(**a),
        }

    # ------------------------------------------------------------------ #
    def _client_or_default(self) -> Any:
        if self._client is None:
            if not self._cfg.ANTHROPIC_API_KEY:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not configured; cannot run the agent. "
                    "Set it in the environment or inject a client for testing."
                )
            from anthropic import Anthropic

            client_kwargs: Dict[str, Any] = {"api_key": self._cfg.ANTHROPIC_API_KEY}
            # Identity-linked (org) keys must name the workspace they act in.
            workspace_id = getattr(self._cfg, "ANTHROPIC_WORKSPACE_ID", "")
            if workspace_id:
                client_kwargs["default_headers"] = {"anthropic-workspace-id": workspace_id}
            self._client = Anthropic(**client_kwargs)
        return self._client

    def _call_tool(self, name: str, arguments: Dict[str, Any]) -> dict:
        """Dispatch a validated tool call, converting arity errors to error dicts."""
        handler = self._dispatch.get(name)
        if handler is None:
            return {"status": "error", "error": "unknown_tool", "detail": f"No tool named '{name}'."}
        try:
            return handler(arguments)
        except TypeError as exc:  # unexpected/missing kwargs from the model
            return {"status": "error", "error": "bad_arguments", "detail": str(exc)}

    # ------------------------------------------------------------------ #
    def run(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        """Execute one bounded conversation turn and return a structured result."""
        context = context or {}
        client = self._client_or_default()

        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_message}]
        actions: List[Action] = []
        reply = ""
        state = AgentState.INIT
        steps_used = 0
        requires_escalation = False
        is_complete = False

        for step in range(1, MAX_EXECUTION_STEPS + 1):
            steps_used = step
            state = AgentState.THINKING

            response = client.messages.create(
                model=self._cfg.CLAUDE_MODEL,
                max_tokens=self._cfg.CLAUDE_MAX_TOKENS,
                temperature=0,  # deterministic tool selection / parsing
                system=SYSTEM_PROMPT,
                tools=self.tools.anthropic_tools(),
                messages=messages,
            )

            content = list(_block_attr(response, "content", []) or [])
            text_parts = [
                _block_attr(b, "text", "") for b in content if _block_attr(b, "type") == "text"
            ]
            if any(text_parts):
                reply = " ".join(t for t in text_parts if t).strip()

            tool_uses = [b for b in content if _block_attr(b, "type") == "tool_use"]
            messages.append({"role": "assistant", "content": _normalize_assistant_content(content)})

            # No tool call → the model is done.
            if not tool_uses:
                state = AgentState.COMPLETE
                is_complete = True
                reply = reply or "Task complete."
                break

            tool_results: List[Dict[str, Any]] = []
            halt = False
            for tu in tool_uses:
                name = _block_attr(tu, "name")
                args = dict(_block_attr(tu, "input", {}) or {})
                tool_use_id = _block_attr(tu, "id")

                # --- Guardrail gate for monetary tools ------------------ #
                if name in MONETARY_TOOLS:
                    state = AgentState.VALIDATING
                    amount_field = "amount_in_inr" if name == "create_order" else "amount"
                    amount_paise = _amount_to_paise(args.get(amount_field))
                    if amount_paise is not None:
                        verdict = self.guardrails.validate(amount_paise, context=context.get("risk_context"))
                        if verdict.decision is GuardrailDecision.DENY:
                            actions.append(Action(
                                tool=name, arguments=args, status=ActionStatus.BLOCKED,
                                detail="; ".join(verdict.reasons),
                                result={"risk_score": verdict.risk_score, "checks": verdict.checks},
                            ))
                            tool_results.append(self._tool_result(
                                tool_use_id,
                                {"status": "blocked", "reasons": verdict.reasons, "checks": verdict.checks},
                                is_error=True,
                            ))
                            # If the breaker tripped, escalate immediately.
                            if self.guardrails.circuit_open:
                                state, requires_escalation, halt = AgentState.ESCALATED, True, True
                            continue
                        if verdict.decision is GuardrailDecision.REQUIRE_CONFIRMATION:
                            actions.append(Action(
                                tool=name, arguments=args, status=ActionStatus.PENDING_CONFIRMATION,
                                detail="; ".join(verdict.reasons),
                                result={"risk_score": verdict.risk_score},
                            ))
                            state, requires_escalation, is_complete, halt = (
                                AgentState.AWAITING_CONFIRMATION, True, False, True
                            )
                            reply = reply or (
                                "This transaction requires human confirmation before it can proceed."
                            )
                            break

                # --- Execute ------------------------------------------- #
                state = AgentState.TOOL_CALL
                result = self._call_tool(name, args)
                ok = result.get("status") == "success"
                actions.append(Action(
                    tool=name, arguments=args,
                    status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
                    detail=result.get("error", "") if not ok else "",
                    result=result,
                ))
                tool_results.append(self._tool_result(tool_use_id, result, is_error=not ok))

                # --- Post-execution guardrail bookkeeping -------------- #
                if ok:
                    self.guardrails.record_api_success()
                    if name in MONETARY_TOOLS:
                        paise = _amount_to_paise(args.get(
                            "amount_in_inr" if name == "create_order" else "amount"
                        ))
                        if paise is not None:
                            self.guardrails.register_spend(paise)
                else:
                    self.guardrails.record_api_failure()
                    if self.guardrails.circuit_open:
                        state, requires_escalation, halt = AgentState.ESCALATED, True, True
                        reply = reply or (
                            "Too many consecutive payment failures; escalating to a human operator."
                        )
                        break

            messages.append({"role": "user", "content": tool_results})
            if halt:
                break

        # Loop exhausted without completion → escalate (bounded runaway guard).
        if not is_complete and state not in (
            AgentState.AWAITING_CONFIRMATION, AgentState.ESCALATED, AgentState.ABORTED
        ):
            state = AgentState.ESCALATED
            requires_escalation = True
            reply = reply or (
                f"Reached the {MAX_EXECUTION_STEPS}-step limit without completing; escalating."
            )

        return AgentResponse(
            reply=reply,
            actions_taken=actions,
            is_complete=is_complete,
            requires_escalation=requires_escalation,
            steps_used=steps_used,
            final_state=state,
        )

    @staticmethod
    def _tool_result(tool_use_id: Any, payload: Dict[str, Any], *, is_error: bool) -> Dict[str, Any]:
        """Build a Claude ``tool_result`` content block with deterministic JSON."""
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": json.dumps(payload, default=str, sort_keys=True),
            "is_error": is_error,
        }


#: Process-wide default agent (lazily creates a real client on first run).
commerce_agent_core = CommerceAgentCore()
