"""Monetary guardrail engine for the commerce agent.

:class:`PaymentGuardrailValidator` is the single authority that every
money-moving step must clear before execution. It combines three independent
defences:

1. **Hard transaction limits** — a per-order cap (default ₹50,000) and a
   per-session cumulative cap (default ₹1,00,000), both in paise.
2. **A circuit breaker** — after 3 sequential API/tool failures the breaker
   opens and all further monetary actions are denied until it is reset,
   preventing repetitive failed-retry storms.
3. **Risk-based human-in-the-loop** — a deterministic :class:`RiskScorer`
   produces a 0–1 score; anything above the configured threshold returns a
   ``REQUIRE_CONFIRMATION`` verdict instead of ``ALLOW``.

All amounts are integer **paise** to keep the arithmetic exact.
"""

from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# Defaults expressed in paise (1 INR = 100 paise).
DEFAULT_SINGLE_ORDER_CAP_PAISE = 50_000_00      # ₹50,000
DEFAULT_SESSION_CAP_PAISE = 1_00_000_00         # ₹1,00,000
DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_RISK_THRESHOLD = 0.70


class GuardrailDecision(str, Enum):
    """The three possible verdicts for a proposed monetary action."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_CONFIRMATION = "require_confirmation"


class CircuitState(str, Enum):
    """Circuit-breaker state."""

    CLOSED = "closed"   # healthy — traffic flows
    OPEN = "open"       # tripped — monetary actions blocked


class GuardrailVerdict(BaseModel):
    """Structured result of a guardrail evaluation."""

    model_config = ConfigDict(extra="forbid")

    decision: GuardrailDecision
    risk_score: float = Field(ge=0.0, le=1.0)
    reasons: List[str] = Field(default_factory=list)
    checks: Dict[str, bool] = Field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        """``True`` only when the action may execute without confirmation."""
        return self.decision is GuardrailDecision.ALLOW

    @property
    def requires_confirmation(self) -> bool:
        """``True`` when a human must approve before proceeding."""
        return self.decision is GuardrailDecision.REQUIRE_CONFIRMATION


class CircuitBreaker:
    """Trips open after ``failure_threshold`` *sequential* failures.

    A single success resets the failure counter and closes the breaker.
    """

    def __init__(self, failure_threshold: int = DEFAULT_FAILURE_THRESHOLD):
        self.failure_threshold = failure_threshold
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._state is CircuitState.OPEN

    @property
    def sequential_failures(self) -> int:
        with self._lock:
            return self._failures

    def record_success(self) -> None:
        """Reset the breaker after a successful call."""
        with self._lock:
            self._failures = 0
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Register a failure; open the breaker at the threshold."""
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning("Circuit breaker OPEN after %d sequential failures", self._failures)

    def reset(self) -> None:
        """Manually close the breaker (e.g. after human intervention)."""
        with self._lock:
            self._failures = 0
            self._state = CircuitState.CLOSED


class RiskScorer:
    """Deterministic 0–1 risk score for a proposed transaction.

    The score rises with the amount's proximity to the single-order cap and
    with contextual red flags (new customer, prior failure, off-hours, etc.).
    Fully deterministic so behaviour is reproducible and testable.
    """

    def score(self, amount_paise: int, single_cap_paise: int, context: Optional[Dict[str, Any]] = None) -> float:
        context = context or {}
        ratio = amount_paise / single_cap_paise if single_cap_paise > 0 else 1.0
        risk = min(ratio, 1.0) * 0.5

        if ratio >= 0.8:
            risk += 0.20
        if context.get("new_customer"):
            risk += 0.20
        if context.get("prior_failure"):
            risk += 0.20
        if context.get("high_risk_channel"):
            risk += 0.15

        return round(min(risk, 1.0), 4)


class PaymentGuardrailValidator:
    """Stateful monetary guardrail — the mandatory gate before any money moves.

    Parameters
    ----------
    single_order_cap_paise, session_cap_paise:
        Hard limits in paise.
    risk_threshold:
        Scores strictly greater than this require human confirmation.
    breaker:
        Injectable :class:`CircuitBreaker` (a fresh one is created by default).
    scorer:
        Injectable :class:`RiskScorer`.
    """

    def __init__(
        self,
        single_order_cap_paise: int = DEFAULT_SINGLE_ORDER_CAP_PAISE,
        session_cap_paise: int = DEFAULT_SESSION_CAP_PAISE,
        risk_threshold: float = DEFAULT_RISK_THRESHOLD,
        breaker: Optional[CircuitBreaker] = None,
        scorer: Optional[RiskScorer] = None,
    ):
        self.single_order_cap_paise = single_order_cap_paise
        self.session_cap_paise = session_cap_paise
        self.risk_threshold = risk_threshold
        self.breaker = breaker or CircuitBreaker()
        self.scorer = scorer or RiskScorer()
        self._session_spent_paise = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    @property
    def session_spent_paise(self) -> int:
        with self._lock:
            return self._session_spent_paise

    @property
    def session_remaining_paise(self) -> int:
        with self._lock:
            return max(0, self.session_cap_paise - self._session_spent_paise)

    # ------------------------------------------------------------------ #
    # Core validation
    # ------------------------------------------------------------------ #
    def validate(
        self,
        amount_paise: int,
        risk_score: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> GuardrailVerdict:
        """Evaluate a proposed monetary action and return a verdict.

        Order of precedence: circuit breaker → structural amount checks →
        hard caps → risk-based confirmation.
        """
        checks: Dict[str, bool] = {}
        reasons: List[str] = []

        # 1) Circuit breaker takes precedence over everything else.
        breaker_ok = not self.breaker.is_open
        checks["circuit_closed"] = breaker_ok
        if not breaker_ok:
            reasons.append("circuit breaker is OPEN after repeated failures")

        # 2) Structural validity.
        positive = isinstance(amount_paise, int) and not isinstance(amount_paise, bool) and amount_paise > 0
        checks["amount_positive_integer"] = positive
        if not positive:
            reasons.append("amount must be a positive integer number of paise")

        # 3) Hard caps (only meaningful for a valid amount).
        if positive:
            within_order = amount_paise <= self.single_order_cap_paise
            checks["within_single_order_cap"] = within_order
            if not within_order:
                reasons.append(
                    f"amount {amount_paise} exceeds single-order cap {self.single_order_cap_paise} paise"
                )

            projected = self.session_spent_paise + amount_paise
            within_session = projected <= self.session_cap_paise
            checks["within_session_cap"] = within_session
            if not within_session:
                reasons.append(
                    f"projected session spend {projected} exceeds session cap {self.session_cap_paise} paise"
                )

        # 4) Risk score (computed only when structurally valid).
        score = 0.0
        if positive:
            score = risk_score if risk_score is not None else self.scorer.score(
                amount_paise, self.single_order_cap_paise, context
            )
            score = round(min(max(score, 0.0), 1.0), 4)

        # Any failed hard check → DENY.
        if not all(checks.values()):
            return GuardrailVerdict(
                decision=GuardrailDecision.DENY, risk_score=score, reasons=reasons, checks=checks
            )

        # High risk → human-in-the-loop.
        if score > self.risk_threshold:
            checks["risk_within_threshold"] = False
            reasons.append(
                f"risk score {score} exceeds threshold {self.risk_threshold}; human confirmation required"
            )
            return GuardrailVerdict(
                decision=GuardrailDecision.REQUIRE_CONFIRMATION,
                risk_score=score, reasons=reasons, checks=checks,
            )

        checks["risk_within_threshold"] = True
        return GuardrailVerdict(
            decision=GuardrailDecision.ALLOW, risk_score=score,
            reasons=["all guardrail checks passed"], checks=checks,
        )

    # ------------------------------------------------------------------ #
    # State mutation — called by the agent after execution
    # ------------------------------------------------------------------ #
    def register_spend(self, amount_paise: int) -> None:
        """Add a successfully-charged amount to the session total."""
        with self._lock:
            self._session_spent_paise += amount_paise

    def record_api_success(self) -> None:
        """Signal a successful tool/API call (closes the breaker)."""
        self.breaker.record_success()

    def record_api_failure(self) -> None:
        """Signal a failed tool/API call (may open the breaker)."""
        self.breaker.record_failure()

    @property
    def circuit_open(self) -> bool:
        """Convenience flag: is the breaker currently tripped?"""
        return self.breaker.is_open
