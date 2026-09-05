"""Pydantic v2 schemas for the Agentic Commerce & Recovery Engine.

Every tool call and API payload flows through a rigid, strictly-typed model.
Monetary values are always integer **paise** (1 INR = 100 paise) so there is
no floating-point drift on financial data.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class Currency(str, Enum):
    """Supported ISO-4217 currency codes."""

    INR = "INR"


class PaymentMethod(str, Enum):
    """Payment instruments the engine may request."""

    UPI = "upi"
    CARD = "card"
    NETBANKING = "netbanking"
    WALLET = "wallet"


class PaymentStatus(str, Enum):
    """Normalised lifecycle status of a Razorpay payment."""

    CREATED = "created"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    REFUNDED = "refunded"
    FAILED = "failed"


class ActionType(str, Enum):
    """Kinds of steps recorded in the audit trail."""

    INTENT = "intent"
    REASONING = "reasoning"
    GUARDRAIL = "guardrail"
    TOOL_EXECUTION = "tool_execution"
    OUTPUT = "output"
    ERROR = "error"
    RECOVERY = "recovery"


class GuardrailDecision(str, Enum):
    """Outcome of a :class:`PaymentGuardrailValidator` check."""

    ALLOW = "allow"
    DENY = "deny"


class RecoveryOutcome(str, Enum):
    """Result of a payment-recovery attempt."""

    RECOVERED = "recovered"
    RETRY_SCHEDULED = "retry_scheduled"
    LINK_ISSUED = "link_issued"
    ESCALATED = "escalated"
    ABANDONED = "abandoned"


# --------------------------------------------------------------------------- #
# Reusable constrained types
# --------------------------------------------------------------------------- #

#: A positive amount, expressed in paise.
AmountPaise = Annotated[int, Field(gt=0, description="Amount in paise (1 INR = 100 paise).")]
#: A non-empty, length-bounded receipt / reference identifier.
ReferenceId = Annotated[str, Field(min_length=1, max_length=64)]


class _StrictModel(BaseModel):
    """Base model that forbids unknown fields — no silent hallucinated keys."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------------- #
# Tool-call argument schemas (LLM -> engine)
# --------------------------------------------------------------------------- #


class CreateOrderArgs(_StrictModel):
    """Arguments for creating a Razorpay order."""

    amount: AmountPaise
    currency: Currency = Currency.INR
    receipt: ReferenceId = Field(description="Merchant-side unique receipt id.")
    notes: Dict[str, str] = Field(default_factory=dict)


class CreatePaymentLinkArgs(_StrictModel):
    """Arguments for issuing a Razorpay payment link (used in recovery)."""

    amount: AmountPaise
    currency: Currency = Currency.INR
    description: str = Field(min_length=1, max_length=255)
    customer_contact: Optional[str] = Field(
        default=None, description="E.164 phone, e.g. +919876543210."
    )
    customer_email: Optional[str] = None
    reference_id: ReferenceId


class CapturePaymentArgs(_StrictModel):
    """Arguments for capturing an authorized payment."""

    payment_id: ReferenceId
    amount: AmountPaise
    currency: Currency = Currency.INR


class RefundPaymentArgs(_StrictModel):
    """Arguments for refunding a captured payment."""

    payment_id: ReferenceId
    amount: AmountPaise
    reason: str = Field(min_length=1, max_length=255)


class FetchPaymentArgs(_StrictModel):
    """Arguments for fetching the current state of a payment."""

    payment_id: ReferenceId


class LookupProductArgs(_StrictModel):
    """Arguments for looking up a catalog product (read-only, no money)."""

    query: str = Field(min_length=1, max_length=120)


class FinalizeArgs(_StrictModel):
    """Terminal tool — the agent calls this exactly once to stop the loop."""

    summary: str = Field(min_length=1, max_length=1000)
    success: bool = True


# --------------------------------------------------------------------------- #
# Guardrail result
# --------------------------------------------------------------------------- #


class GuardrailResult(_StrictModel):
    """Structured verdict returned by :class:`PaymentGuardrailValidator`."""

    decision: GuardrailDecision
    action: str
    reason: str
    checks: Dict[str, bool] = Field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        """``True`` when the monetary action may proceed."""
        return self.decision is GuardrailDecision.ALLOW


class GuardrailViolation(Exception):
    """Raised when a monetary action fails guardrail validation."""

    def __init__(self, result: GuardrailResult):
        self.result = result
        super().__init__(f"[{result.action}] guardrail denied: {result.reason}")


# --------------------------------------------------------------------------- #
# API request / response models (HTTP boundary)
# --------------------------------------------------------------------------- #


class AgentRunRequest(_StrictModel):
    """Request body for POST /engine/agent/run."""

    instruction: str = Field(min_length=1, max_length=2000)
    context: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[ReferenceId] = None


class ToolCallTrace(_StrictModel):
    """One executed tool call, surfaced to the API caller for transparency."""

    tool: str
    arguments: Dict[str, Any]
    ok: bool
    result: Dict[str, Any] = Field(default_factory=dict)


class AgentRunResponse(_StrictModel):
    """Response for POST /engine/agent/run."""

    session_id: str
    success: bool
    summary: str
    stop_reason: str
    turns: int
    tool_calls: List[ToolCallTrace] = Field(default_factory=list)


class RecoveryRequest(_StrictModel):
    """Request body for POST /engine/recovery/run."""

    payment_id: ReferenceId
    amount: AmountPaise
    currency: Currency = Currency.INR
    customer_contact: Optional[str] = None
    customer_email: Optional[str] = None
    max_retries: int = Field(default=1, ge=0, le=5)


class RecoveryResponse(_StrictModel):
    """Response for POST /engine/recovery/run."""

    payment_id: str
    outcome: RecoveryOutcome
    detail: str
    steps: List[str] = Field(default_factory=list)
    payment_link: Optional[str] = None


class AuditRecordOut(_StrictModel):
    """Serialised audit-trail record for read APIs."""

    id: int
    session_id: str
    sequence: int
    action_type: ActionType
    actor: str
    summary: str
    payload: Dict[str, Any]
    created_at: str

    @field_validator("payload", mode="before")
    @classmethod
    def _coerce_payload(cls, value: Any) -> Dict[str, Any]:
        """Guarantee payload is always a dict, even if stored as ``None``."""
        return value or {}
