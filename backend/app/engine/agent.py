"""Deterministic open-source tool-use agent loop.

Drives a Hugging Face-hosted model through a bounded tool-use conversation. Stopping is fully
deterministic (Core Rule #3): the loop halts on the FIRST of —

* the model calling the terminal ``finalize`` tool,
* the model replying with no tool call (``end_turn``), or
* the hard ``AGENT_MAX_TURNS`` ceiling.

The provider-compatible client is injectable so the loop is unit-testable without any
network access or API key.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Protocol

from app.core.config import Settings, settings
from app.engine.audit import AuditLogger, audit_logger
from app.engine.schemas import (
    ActionType,
    AgentRunRequest,
    AgentRunResponse,
    ToolCallTrace,
)
from app.engine.tools import (
    FINALIZE_TOOL,
    ToolContext,
    ToolRegistry,
    build_context,
    tool_registry,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are the Razorpay Agentic Commerce & Recovery agent for Agent Seva, an Indian "
    "Kirana store. You accomplish commerce and payment-recovery tasks strictly through the "
    "provided tools. Rules you must follow:\n"
    "- All monetary amounts are integers in paise (100 paise = 1 INR).\n"
    "- Never invent payment ids, order ids, or amounts; obtain them via tools or the task input.\n"
    "- To recover a failed payment, prefer fetch_payment first, then create_payment_link.\n"
    "- When the task is complete OR cannot proceed, call the 'finalize' tool exactly once "
    "with a concise summary. Do not continue after finalizing."
)


class LLMClient(Protocol):
    """Minimal structural type for a tool-calling client."""

    class messages:  # noqa: N801 - mirrors SDK attribute shape
        @staticmethod
        def create(**kwargs: Any) -> Any: ...


def _get_default_client(config: Settings) -> Any:
    """Instantiate the Hugging Face client, or raise a clear error if unusable."""
    if not config.HUGGINGFACE_API_KEY:
        raise RuntimeError(
            "HUGGINGFACE_API_KEY is not configured; cannot run the commerce agent. "
            "Set it in the environment or inject a client for testing."
        )
    from app.agent.huggingface_client import HuggingFaceToolClient

    return HuggingFaceToolClient(
        api_key=config.HUGGINGFACE_API_KEY,
        base_url=config.HF_ROUTER_BASE_URL,
        timeout=config.HF_TIMEOUT_SECONDS,
    )


def _block_attr(block: Any, name: str, default: Any = None) -> Any:
    """Read a field from an SDK block or a plain dict uniformly."""
    if isinstance(block, dict):
        return block.get(name, default)
    return getattr(block, name, default)


def _normalize_assistant_content(content: List[Any]) -> List[Dict[str, Any]]:
    """Rebuild assistant content as plain dicts to feed back into the API."""
    normalized: List[Dict[str, Any]] = []
    for block in content:
        btype = _block_attr(block, "type")
        if btype == "text":
            normalized.append({"type": "text", "text": _block_attr(block, "text", "")})
        elif btype == "tool_use":
            normalized.append({
                "type": "tool_use",
                "id": _block_attr(block, "id"),
                "name": _block_attr(block, "name"),
                "input": _block_attr(block, "input", {}) or {},
            })
    return normalized


class CommerceAgent:
    """Runs a bounded, auditable open-source tool-use session."""

    def __init__(
        self,
        client: Optional[Any] = None,
        registry: Optional[ToolRegistry] = None,
        audit: Optional[AuditLogger] = None,
        config: Optional[Settings] = None,
        context_factory: Optional[Callable[[str], ToolContext]] = None,
    ):
        self._cfg = config or settings
        self._client = client  # lazily created on first run if None
        self._registry = registry or tool_registry
        self._audit = audit or audit_logger
        self._context_factory = context_factory or build_context

    def _client_or_default(self) -> Any:
        if self._client is None:
            self._client = _get_default_client(self._cfg)
        return self._client

    def run(self, request: AgentRunRequest) -> AgentRunResponse:
        """Execute the agent loop for a single instruction and return the outcome."""
        session_id = request.session_id or f"sess_{uuid.uuid4().hex[:16]}"
        ctx = self._context_factory(session_id)
        client = self._client_or_default()

        self._audit.record(
            session_id, ActionType.INTENT, "agent run started",
            {"instruction": request.instruction, "context": request.context},
        )

        user_text = request.instruction
        if request.context:
            user_text += f"\n\nContext:\n{json.dumps(request.context, default=str)}"
        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_text}]

        tool_calls: List[ToolCallTrace] = []
        summary = ""
        success = False
        stop_reason = "max_turns"
        turns = 0

        for turn in range(1, self._cfg.AGENT_MAX_TURNS + 1):
            turns = turn
            response = client.messages.create(
                model=self._cfg.HF_LLM_MODEL,
                max_tokens=self._cfg.HF_MAX_TOKENS,
                temperature=0,
                system=SYSTEM_PROMPT,
                tools=self._registry.anthropic_tools(),
                messages=messages,
            )

            content = list(_block_attr(response, "content", []) or [])
            text_parts = [_block_attr(b, "text", "") for b in content if _block_attr(b, "type") == "text"]
            if any(text_parts):
                self._audit.record(
                    session_id, ActionType.REASONING, "assistant reasoning",
                    {"text": " ".join(t for t in text_parts if t)},
                )

            tool_uses = [b for b in content if _block_attr(b, "type") == "tool_use"]
            messages.append({"role": "assistant", "content": _normalize_assistant_content(content)})

            if not tool_uses:
                stop_reason = "end_turn"
                summary = " ".join(t for t in text_parts if t).strip() or "No action taken."
                success = True
                break

            tool_results: List[Dict[str, Any]] = []
            terminal_hit = False
            for tu in tool_uses:
                name = _block_attr(tu, "name")
                raw_args = _block_attr(tu, "input", {}) or {}
                ok, result = self._registry.execute(name, raw_args, ctx)
                tool_calls.append(ToolCallTrace(tool=name, arguments=raw_args, ok=ok, result=result))
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": _block_attr(tu, "id"),
                    "content": json.dumps(result, default=str),
                    "is_error": not ok,
                })
                if name == FINALIZE_TOOL and ok:
                    terminal_hit = True
                    stop_reason = "finalized"
                    summary = result.get("summary", "")
                    success = bool(result.get("success", False))

            messages.append({"role": "user", "content": tool_results})
            if terminal_hit:
                break

        if stop_reason == "max_turns":
            summary = summary or "Reached maximum tool-use turns without finalizing."
            self._audit.record(session_id, ActionType.OUTPUT, "agent hit max turns", {"turns": turns})

        self._audit.record(
            session_id, ActionType.OUTPUT, "agent run finished",
            {"stop_reason": stop_reason, "success": success, "turns": turns},
        )

        return AgentRunResponse(
            session_id=session_id,
            success=success,
            summary=summary,
            stop_reason=stop_reason,
            turns=turns,
            tool_calls=tool_calls,
        )


#: Process-wide default agent (lazily creates a real client on first run).
commerce_agent = CommerceAgent()
