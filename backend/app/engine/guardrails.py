"""PaymentGuardrailValidator — the mandatory gate for every monetary action.

Core Rule #2: *every* money-moving action (create order, payment link,
capture, refund) must pass validation here **before** it reaches Razorpay.

The validator is deterministic and stateful within its lifetime: it tracks
the day's cumulative charge total, per-payment captured/refunded balances,
and seen idempotency keys. State mutation happens only through the explicit
``register_*`` methods, which callers invoke *after* a successful execution.
"""

from __future__ import annotations

import datetime as _dt
import threading
from collections import defaultdict
from typing import Dict, Optional, Set

from app.core.config import Settings, settings
from app.engine.schemas import (
    Currency,
    GuardrailDecision,
    GuardrailResult,
    GuardrailViolation,
)


class PaymentGuardrailValidator:
    """Validate monetary actions against hard financial-safety limits.

    Parameters
    ----------
    config:
        Settings supplying the guardrail limits. Defaults to the global
        :data:`app.core.config.settings`; tests inject a custom instance.
    """

    def __init__(self, config: Optional[Settings] = None):
        self._cfg = config or settings
        self._lock = threading.Lock()
        self._daily_charged: Dict[str, int] = defaultdict(int)
        self._captured: Dict[str, int] = defaultdict(int)
        self._refunded: Dict[str, int] = defaultdict(int)
        self._seen_idempotency: Set[str] = set()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _today_key() -> str:
        return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")

    def _deny(self, action: str, reason: str, checks: Dict[str, bool]) -> GuardrailResult:
        return GuardrailResult(
            decision=GuardrailDecision.DENY, action=action, reason=reason, checks=checks
        )

    def _allow(self, action: str, checks: Dict[str, bool]) -> GuardrailResult:
        return GuardrailResult(
            decision=GuardrailDecision.ALLOW,
            action=action,
            reason="all checks passed",
            checks=checks,
        )

    def _check_basic_amount(self, amount: int, currency: Currency, checks: Dict[str, bool]) -> Optional[str]:
        """Run amount/currency checks common to charge-type actions.

        Returns a failure reason string, or ``None`` if all checks pass.
        Mutates ``checks`` in place with the per-check booleans.
        """
        checks["is_positive_integer"] = isinstance(amount, int) and not isinstance(amount, bool) and amount > 0
        if not checks["is_positive_integer"]:
            return "amount must be a positive integer number of paise"

        checks["currency_allowed"] = currency.value in self._cfg.allowed_currencies
        if not checks["currency_allowed"]:
            return f"currency {currency.value} is not in the allowlist"

        checks["above_minimum"] = amount >= self._cfg.MIN_TXN_AMOUNT_PAISE
        if not checks["above_minimum"]:
            return f"amount {amount} is below minimum {self._cfg.MIN_TXN_AMOUNT_PAISE} paise"

        checks["below_maximum"] = amount <= self._cfg.MAX_TXN_AMOUNT_PAISE
        if not checks["below_maximum"]:
            return f"amount {amount} exceeds per-transaction maximum {self._cfg.MAX_TXN_AMOUNT_PAISE} paise"

        return None

    # ------------------------------------------------------------------ #
    # Public validation API — one method per monetary action
    # ------------------------------------------------------------------ #
    def validate_charge(
        self,
        action: str,
        amount: int,
        currency: Currency,
        idempotency_key: Optional[str] = None,
    ) -> GuardrailResult:
        """Validate a charge-type action (order / payment link / capture).

        Enforces amount bounds, currency allowlist, the rolling daily cap,
        and (optionally) idempotency-key uniqueness.
        """
        checks: Dict[str, bool] = {}
        with self._lock:
            failure = self._check_basic_amount(amount, currency, checks)
            if failure:
                return self._deny(action, failure, checks)

            projected = self._daily_charged[self._today_key()] + amount
            checks["within_daily_cap"] = projected <= self._cfg.DAILY_CAP_PAISE
            if not checks["within_daily_cap"]:
                return self._deny(
                    action,
                    f"projected daily total {projected} exceeds cap {self._cfg.DAILY_CAP_PAISE} paise",
                    checks,
                )

            if idempotency_key is not None:
                checks["idempotency_unique"] = idempotency_key not in self._seen_idempotency
                if not checks["idempotency_unique"]:
                    return self._deny(
                        action,
                        f"duplicate idempotency key '{idempotency_key}'",
                        checks,
                    )

            return self._allow(action, checks)

    def validate_refund(self, payment_id: str, amount: int) -> GuardrailResult:
        """Validate a refund: it may never exceed the un-refunded captured balance."""
        action = "refund_payment"
        checks: Dict[str, bool] = {}
        with self._lock:
            checks["is_positive_integer"] = (
                isinstance(amount, int) and not isinstance(amount, bool) and amount > 0
            )
            if not checks["is_positive_integer"]:
                return self._deny(action, "refund amount must be a positive integer", checks)

            captured = self._captured.get(payment_id, 0)
            already_refunded = self._refunded.get(payment_id, 0)
            refundable = captured - already_refunded

            checks["payment_is_captured"] = captured > 0
            if not checks["payment_is_captured"]:
                return self._deny(
                    action, f"payment '{payment_id}' has no captured balance to refund", checks
                )

            checks["within_refundable_balance"] = amount <= refundable
            if not checks["within_refundable_balance"]:
                return self._deny(
                    action,
                    f"refund {amount} exceeds refundable balance {refundable} for '{payment_id}'",
                    checks,
                )

            return self._allow(action, checks)

    # ------------------------------------------------------------------ #
    # Convenience: validate-or-raise
    # ------------------------------------------------------------------ #
    def guard_charge(
        self,
        action: str,
        amount: int,
        currency: Currency,
        idempotency_key: Optional[str] = None,
    ) -> GuardrailResult:
        """Like :meth:`validate_charge` but raise :class:`GuardrailViolation` on deny."""
        result = self.validate_charge(action, amount, currency, idempotency_key)
        if not result.allowed:
            raise GuardrailViolation(result)
        return result

    def guard_refund(self, payment_id: str, amount: int) -> GuardrailResult:
        """Like :meth:`validate_refund` but raise :class:`GuardrailViolation` on deny."""
        result = self.validate_refund(payment_id, amount)
        if not result.allowed:
            raise GuardrailViolation(result)
        return result

    # ------------------------------------------------------------------ #
    # State registration — called after a successful execution
    # ------------------------------------------------------------------ #
    def register_charge(self, amount: int, idempotency_key: Optional[str] = None) -> None:
        """Record a successful charge against the daily total / idempotency set."""
        with self._lock:
            self._daily_charged[self._today_key()] += amount
            if idempotency_key is not None:
                self._seen_idempotency.add(idempotency_key)

    def register_capture(self, payment_id: str, amount: int) -> None:
        """Record that ``amount`` was captured for ``payment_id`` (enables refunds)."""
        with self._lock:
            self._captured[payment_id] += amount

    def register_refund(self, payment_id: str, amount: int) -> None:
        """Record that ``amount`` was refunded for ``payment_id``."""
        with self._lock:
            self._refunded[payment_id] += amount

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    def daily_total(self) -> int:
        """Return today's cumulative charged amount in paise."""
        with self._lock:
            return self._daily_charged[self._today_key()]


#: Process-wide default validator.
payment_guardrails = PaymentGuardrailValidator()
