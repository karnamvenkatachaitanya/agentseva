"""Tool registry for Claude tool-use.

Each tool exposes a rigid JSON schema (derived from a Pydantic v2 model) to the
model, and a Python executor that:

1. **Validates** the model-supplied arguments against the Pydantic schema
   (Core Rule #3 — no raw/hallucinated JSON reaches business logic).
2. For monetary tools, runs :class:`PaymentGuardrailValidator` **before**
   touching Razorpay (Core Rule #2) and records the verdict to the audit trail.
3. Executes the Razorpay call inside a structured ``try/except`` (Core Rule #5).
4. Writes intent / execution / error steps to the append-only audit trail
   (Core Rule #4).

Executors return ``(ok: bool, result: dict)`` — they never raise into the agent
loop, so the model always receives a well-formed ``tool_result``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple, Type

from pydantic import BaseModel, ValidationError

from app.db.seed_products import SEED_PRODUCTS
from app.engine.audit import AuditLogger, audit_logger
from app.engine.guardrails import (
    GuardrailViolation,
    PaymentGuardrailValidator,
    payment_guardrails,
)
from app.engine.razorpay_client import RazorpayClient, RazorpayError, razorpay_client
from app.engine.schemas import (
    ActionType,
    CapturePaymentArgs,
    CreateOrderArgs,
    CreatePaymentLinkArgs,
    FetchPaymentArgs,
    FinalizeArgs,
    LookupProductArgs,
    RefundPaymentArgs,
)

logger = logging.getLogger(__name__)

#: Terminal tool name — its invocation deterministically stops the agent loop.
FINALIZE_TOOL = "finalize"


@dataclass
class ToolContext:
    """Per-run dependencies handed to every tool executor."""

    session_id: str
    guardrails: PaymentGuardrailValidator
    razorpay: RazorpayClient
    audit: AuditLogger


@dataclass
class Tool:
    """A single registered tool: schema + validated executor."""

    name: str
    description: str
    args_model: Type[BaseModel]
    executor: Callable[[BaseModel, ToolContext], Tuple[bool, Dict[str, Any]]]
    is_terminal: bool = False

    def anthropic_schema(self) -> Dict[str, Any]:
        """Return the Anthropic tool-definition dict for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.args_model.model_json_schema(),
        }


# --------------------------------------------------------------------------- #
# Executors
# --------------------------------------------------------------------------- #


def _exec_create_order(args: CreateOrderArgs, ctx: ToolContext) -> Tuple[bool, Dict[str, Any]]:
    ctx.audit.record(
        ctx.session_id, ActionType.INTENT, "create_razorpay_order requested",
        {"amount": args.amount, "currency": args.currency.value, "receipt": args.receipt},
    )
    verdict = ctx.guardrails.validate_charge("create_order", args.amount, args.currency, args.receipt)
    ctx.audit.record(
        ctx.session_id, ActionType.GUARDRAIL, f"create_order -> {verdict.decision.value}",
        verdict.model_dump(),
    )
    if not verdict.allowed:
        return False, {"error": "guardrail_denied", "reason": verdict.reason, "checks": verdict.checks}
    try:
        order = ctx.razorpay.create_order(
            amount=args.amount, currency=args.currency.value, receipt=args.receipt, notes=args.notes
        )
    except RazorpayError as exc:
        ctx.audit.record(ctx.session_id, ActionType.ERROR, "create_order failed",
                         {"category": exc.category, "message": str(exc)})
        return False, {"error": "razorpay_error", "category": exc.category, "message": str(exc)}
    ctx.audit.record(ctx.session_id, ActionType.TOOL_EXECUTION, "order created", order)
    return True, order


def _exec_create_payment_link(args: CreatePaymentLinkArgs, ctx: ToolContext) -> Tuple[bool, Dict[str, Any]]:
    ctx.audit.record(
        ctx.session_id, ActionType.INTENT, "create_payment_link requested",
        {"amount": args.amount, "reference_id": args.reference_id},
    )
    verdict = ctx.guardrails.validate_charge(
        "create_payment_link", args.amount, args.currency, args.reference_id
    )
    ctx.audit.record(
        ctx.session_id, ActionType.GUARDRAIL, f"create_payment_link -> {verdict.decision.value}",
        verdict.model_dump(),
    )
    if not verdict.allowed:
        return False, {"error": "guardrail_denied", "reason": verdict.reason, "checks": verdict.checks}
    try:
        link = ctx.razorpay.create_payment_link(
            amount=args.amount,
            currency=args.currency.value,
            description=args.description,
            reference_id=args.reference_id,
            customer_contact=args.customer_contact,
            customer_email=args.customer_email,
        )
    except RazorpayError as exc:
        ctx.audit.record(ctx.session_id, ActionType.ERROR, "create_payment_link failed",
                         {"category": exc.category, "message": str(exc)})
        return False, {"error": "razorpay_error", "category": exc.category, "message": str(exc)}
    ctx.guardrails.register_charge(args.amount, args.reference_id)
    ctx.audit.record(ctx.session_id, ActionType.TOOL_EXECUTION, "payment link created", link)
    return True, link


def _exec_capture_payment(args: CapturePaymentArgs, ctx: ToolContext) -> Tuple[bool, Dict[str, Any]]:
    ctx.audit.record(
        ctx.session_id, ActionType.INTENT, "capture_payment requested",
        {"payment_id": args.payment_id, "amount": args.amount},
    )
    verdict = ctx.guardrails.validate_charge("capture_payment", args.amount, args.currency)
    ctx.audit.record(
        ctx.session_id, ActionType.GUARDRAIL, f"capture_payment -> {verdict.decision.value}",
        verdict.model_dump(),
    )
    if not verdict.allowed:
        return False, {"error": "guardrail_denied", "reason": verdict.reason, "checks": verdict.checks}
    try:
        payment = ctx.razorpay.capture_payment(
            payment_id=args.payment_id, amount=args.amount, currency=args.currency.value
        )
    except RazorpayError as exc:
        ctx.audit.record(ctx.session_id, ActionType.ERROR, "capture_payment failed",
                         {"category": exc.category, "message": str(exc)})
        return False, {"error": "razorpay_error", "category": exc.category, "message": str(exc)}
    ctx.guardrails.register_charge(args.amount)
    ctx.guardrails.register_capture(args.payment_id, args.amount)
    ctx.audit.record(ctx.session_id, ActionType.TOOL_EXECUTION, "payment captured", payment)
    return True, payment


def _exec_refund_payment(args: RefundPaymentArgs, ctx: ToolContext) -> Tuple[bool, Dict[str, Any]]:
    ctx.audit.record(
        ctx.session_id, ActionType.INTENT, "refund_payment requested",
        {"payment_id": args.payment_id, "amount": args.amount, "reason": args.reason},
    )
    verdict = ctx.guardrails.validate_refund(args.payment_id, args.amount)
    ctx.audit.record(
        ctx.session_id, ActionType.GUARDRAIL, f"refund_payment -> {verdict.decision.value}",
        verdict.model_dump(),
    )
    if not verdict.allowed:
        return False, {"error": "guardrail_denied", "reason": verdict.reason, "checks": verdict.checks}
    try:
        refund = ctx.razorpay.refund_payment(payment_id=args.payment_id, amount=args.amount)
    except RazorpayError as exc:
        ctx.audit.record(ctx.session_id, ActionType.ERROR, "refund_payment failed",
                         {"category": exc.category, "message": str(exc)})
        return False, {"error": "razorpay_error", "category": exc.category, "message": str(exc)}
    ctx.guardrails.register_refund(args.payment_id, args.amount)
    ctx.audit.record(ctx.session_id, ActionType.TOOL_EXECUTION, "refund processed", refund)
    return True, refund


def _exec_fetch_payment(args: FetchPaymentArgs, ctx: ToolContext) -> Tuple[bool, Dict[str, Any]]:
    try:
        payment = ctx.razorpay.fetch_payment(args.payment_id)
    except RazorpayError as exc:
        ctx.audit.record(ctx.session_id, ActionType.ERROR, "fetch_payment failed",
                         {"category": exc.category, "message": str(exc)})
        return False, {"error": "razorpay_error", "category": exc.category, "message": str(exc)}
    ctx.audit.record(ctx.session_id, ActionType.TOOL_EXECUTION, "payment fetched", payment)
    return True, payment


def _exec_lookup_product(args: LookupProductArgs, ctx: ToolContext) -> Tuple[bool, Dict[str, Any]]:
    query = args.query.lower()
    matches = [p for p in SEED_PRODUCTS if query in p["name"].lower() or query in p["category"].lower()]
    result = {"query": args.query, "count": len(matches), "products": matches[:10]}
    ctx.audit.record(ctx.session_id, ActionType.TOOL_EXECUTION, "product lookup", result)
    return True, result


def _exec_finalize(args: FinalizeArgs, ctx: ToolContext) -> Tuple[bool, Dict[str, Any]]:
    ctx.audit.record(
        ctx.session_id, ActionType.OUTPUT, "agent finalized",
        {"summary": args.summary, "success": args.success},
    )
    return True, {"summary": args.summary, "success": args.success}


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


class ToolRegistry:
    """Holds all tools and dispatches validated execution."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(Tool(
            "create_razorpay_order",
            "Create a Razorpay order for a given amount in paise. Use before collecting a payment.",
            CreateOrderArgs, _exec_create_order,
        ))
        self.register(Tool(
            "create_payment_link",
            "Issue a Razorpay payment link so a customer can pay a specific amount. "
            "Preferred recovery action for a failed payment.",
            CreatePaymentLinkArgs, _exec_create_payment_link,
        ))
        self.register(Tool(
            "capture_payment",
            "Capture an authorized payment for the exact authorized amount (paise).",
            CapturePaymentArgs, _exec_capture_payment,
        ))
        self.register(Tool(
            "refund_payment",
            "Refund part or all of a captured payment. Amount may not exceed the captured balance.",
            RefundPaymentArgs, _exec_refund_payment,
        ))
        self.register(Tool(
            "fetch_payment",
            "Fetch the current status of a payment by id. Read-only, no money moves.",
            FetchPaymentArgs, _exec_fetch_payment,
        ))
        self.register(Tool(
            "lookup_product",
            "Search the Kirana catalog by name or category. Read-only.",
            LookupProductArgs, _exec_lookup_product,
        ))
        self.register(Tool(
            FINALIZE_TOOL,
            "Finish the task. Call this exactly once with a summary when the goal is met "
            "or cannot proceed. This ends the session.",
            FinalizeArgs, _exec_finalize, is_terminal=True,
        ))

    def register(self, tool: Tool) -> None:
        """Add or replace a tool in the registry."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        """Return a tool by name, raising ``KeyError`` if unknown."""
        return self._tools[name]

    def anthropic_tools(self) -> List[Dict[str, Any]]:
        """Return all tool definitions in Anthropic's tool-use format."""
        return [tool.anthropic_schema() for tool in self._tools.values()]

    def execute(self, name: str, raw_args: Dict[str, Any], ctx: ToolContext) -> Tuple[bool, Dict[str, Any]]:
        """Validate args and run the named tool, never raising into the caller."""
        tool = self._tools.get(name)
        if tool is None:
            return False, {"error": "unknown_tool", "message": f"No tool named '{name}'."}
        try:
            args = tool.args_model.model_validate(raw_args)
        except ValidationError as exc:
            ctx.audit.record(
                ctx.session_id, ActionType.ERROR, f"invalid arguments for {name}",
                {"errors": exc.errors(include_url=False)},
            )
            return False, {"error": "validation_error", "message": exc.errors(include_url=False)}
        try:
            return tool.executor(args, ctx)
        except GuardrailViolation as exc:  # defensive: executors normally return, not raise
            return False, {"error": "guardrail_denied", "reason": exc.result.reason}
        except Exception as exc:  # noqa: BLE001 — isolate tool failures from the loop
            logger.exception("Tool %s crashed", name)
            ctx.audit.record(ctx.session_id, ActionType.ERROR, f"{name} crashed", {"message": str(exc)})
            return False, {"error": "tool_crash", "message": str(exc)}


def build_context(session_id: str) -> ToolContext:
    """Construct a :class:`ToolContext` bound to the process-wide singletons."""
    return ToolContext(
        session_id=session_id,
        guardrails=payment_guardrails,
        razorpay=razorpay_client,
        audit=audit_logger,
    )


#: Process-wide default registry.
tool_registry = ToolRegistry()
