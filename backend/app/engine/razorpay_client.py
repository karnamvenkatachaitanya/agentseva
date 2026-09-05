"""Resilient Razorpay REST client.

Two interchangeable back-ends behind one interface:

* **live** – authenticated calls to ``api.razorpay.com`` via :mod:`httpx`.
* **mock** – a deterministic in-process simulator (no network, no keys) so
  the whole engine is runnable and testable offline.

Core Rule #5: every external call is wrapped in a structured ``try/except``
that maps low-level failures onto typed :class:`RazorpayError` categories with
an explicit fallback policy, so callers never see a raw transport exception.
"""

from __future__ import annotations

import base64
import itertools
import json
import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)


class RazorpayError(Exception):
    """Normalised error raised by :class:`RazorpayClient`.

    Attributes
    ----------
    category:
        One of ``"auth"``, ``"network"``, ``"timeout"``, ``"api"``,
        ``"validation"`` — lets callers pick a fallback policy deterministically.
    status_code:
        HTTP status when the failure originated from an API response.
    """

    def __init__(self, message: str, *, category: str, status_code: Optional[int] = None):
        self.category = category
        self.status_code = status_code
        super().__init__(message)


# --------------------------------------------------------------------------- #
# Deterministic in-process simulator
# --------------------------------------------------------------------------- #


class _MockRazorpayBackend:
    """A minimal, deterministic Razorpay simulator.

    Ids are monotonic (``*_mock_1``, ``_2`` …) so behaviour is reproducible in
    tests. A payment id containing ``"fail"`` is treated as a failed payment by
    :meth:`fetch_payment`, which drives recovery-flow testing without network.
    """

    def __init__(self) -> None:
        self._counter = itertools.count(1)
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.payments: Dict[str, Dict[str, Any]] = {}
        self.payment_links: Dict[str, Dict[str, Any]] = {}
        self.refunds: Dict[str, Dict[str, Any]] = {}

    def _next(self, prefix: str) -> str:
        return f"{prefix}_mock_{next(self._counter)}"

    def seed_payment(self, payment_id: str, *, status: str, amount: int, currency: str = "INR") -> None:
        """Pre-load a payment in a known state (used by tests / recovery)."""
        self.payments[payment_id] = {
            "id": payment_id,
            "status": status,
            "amount": amount,
            "currency": currency,
            "captured": status == "captured",
        }

    def create_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        order_id = self._next("order")
        order = {
            "id": order_id,
            "entity": "order",
            "amount": payload["amount"],
            "currency": payload.get("currency", "INR"),
            "receipt": payload.get("receipt"),
            "status": "created",
            "notes": payload.get("notes", {}),
        }
        self.orders[order_id] = order
        return order

    def create_payment_link(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        link_id = self._next("plink")
        link = {
            "id": link_id,
            "entity": "payment_link",
            "amount": payload["amount"],
            "currency": payload.get("currency", "INR"),
            "description": payload.get("description", ""),
            "status": "created",
            "short_url": f"https://rzp.io/i/{link_id}",
            "reference_id": payload.get("reference_id"),
        }
        self.payment_links[link_id] = link
        return link

    def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        if payment_id in self.payments:
            return self.payments[payment_id]
        # Unknown id: derive a deterministic status from the id itself.
        status = "failed" if "fail" in payment_id.lower() else "authorized"
        derived = {
            "id": payment_id,
            "status": status,
            "amount": 0,
            "currency": "INR",
            "captured": False,
        }
        self.payments[payment_id] = derived
        return derived

    def capture_payment(self, payment_id: str, amount: int, currency: str) -> Dict[str, Any]:
        payment = self.payments.get(payment_id) or {
            "id": payment_id,
            "amount": amount,
            "currency": currency,
        }
        payment.update({"status": "captured", "captured": True, "amount": amount, "currency": currency})
        self.payments[payment_id] = payment
        return payment

    def refund_payment(self, payment_id: str, amount: int) -> Dict[str, Any]:
        refund_id = self._next("rfnd")
        refund = {
            "id": refund_id,
            "entity": "refund",
            "payment_id": payment_id,
            "amount": amount,
            "status": "processed",
        }
        self.refunds[refund_id] = refund
        payment = self.payments.get(payment_id)
        if payment is not None:
            payment["status"] = "refunded"
        return refund


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #


class RazorpayClient:
    """Unified Razorpay client (``live`` HTTP or ``mock`` simulator)."""

    def __init__(self, config: Optional[Settings] = None, mock_backend: Optional[_MockRazorpayBackend] = None):
        self._cfg = config or settings
        self.mode = (self._cfg.RAZORPAY_MODE or "mock").lower()
        self._mock = mock_backend or _MockRazorpayBackend()

    @property
    def mock(self) -> _MockRazorpayBackend:
        """Expose the simulator (for seeding payment states in tests)."""
        return self._mock

    # ------------------------------------------------------------------ #
    # Live HTTP transport
    # ------------------------------------------------------------------ #
    def _auth_header(self) -> str:
        raw = f"{self._cfg.RAZORPAY_KEY_ID}:{self._cfg.RAZORPAY_KEY_SECRET}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _request(self, method: str, path: str, *, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute one authenticated HTTP request with structured error mapping.

        Fallback policy: any transport/decoding failure is re-raised as a typed
        :class:`RazorpayError` so upstream callers branch on ``.category`` rather
        than on library-specific exception types.
        """
        if not self._cfg.RAZORPAY_KEY_ID or not self._cfg.RAZORPAY_KEY_SECRET:
            raise RazorpayError("Razorpay credentials are not configured", category="auth")

        url = f"{self._cfg.RAZORPAY_BASE_URL.rstrip('/')}{path}"
        headers = {"Authorization": self._auth_header(), "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=self._cfg.RAZORPAY_TIMEOUT_SECONDS) as client:
                response = client.request(method, url, headers=headers, json=json_body)
            if response.status_code == 401:
                raise RazorpayError("Razorpay authentication failed", category="auth", status_code=401)
            if response.status_code >= 400:
                detail = self._safe_error_detail(response)
                raise RazorpayError(
                    f"Razorpay API error ({response.status_code}): {detail}",
                    category="api",
                    status_code=response.status_code,
                )
            return response.json()
        except httpx.TimeoutException as exc:
            logger.warning("Razorpay request timed out: %s %s", method, url)
            raise RazorpayError(f"Razorpay request timed out: {exc}", category="timeout") from exc
        except httpx.HTTPError as exc:
            logger.warning("Razorpay transport error: %s", exc)
            raise RazorpayError(f"Razorpay transport error: {exc}", category="network") from exc
        except json.JSONDecodeError as exc:
            raise RazorpayError("Razorpay returned a non-JSON response", category="api") from exc

    @staticmethod
    def _safe_error_detail(response: httpx.Response) -> str:
        """Best-effort extraction of Razorpay's error description."""
        try:
            body = response.json()
            return str(body.get("error", {}).get("description", body))
        except Exception:  # noqa: BLE001 — never let error-parsing raise
            return response.text[:200]

    # ------------------------------------------------------------------ #
    # Public API — dispatches to live or mock
    # ------------------------------------------------------------------ #
    def create_order(self, *, amount: int, currency: str, receipt: str, notes: Dict[str, str]) -> Dict[str, Any]:
        """Create an order. Fallback: raises :class:`RazorpayError` on failure."""
        payload = {"amount": amount, "currency": currency, "receipt": receipt, "notes": notes}
        if self.mode == "mock":
            return self._mock.create_order(payload)
        return self._request("POST", "/orders", json_body=payload)

    def create_payment_link(
        self,
        *,
        amount: int,
        currency: str,
        description: str,
        reference_id: str,
        customer_contact: Optional[str] = None,
        customer_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a payment link (used by recovery)."""
        payload: Dict[str, Any] = {
            "amount": amount,
            "currency": currency,
            "description": description,
            "reference_id": reference_id,
        }
        customer: Dict[str, str] = {}
        if customer_contact:
            customer["contact"] = customer_contact
        if customer_email:
            customer["email"] = customer_email
        if customer:
            payload["customer"] = customer
        if self.mode == "mock":
            return self._mock.create_payment_link(payload)
        return self._request("POST", "/payment_links", json_body=payload)

    def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        """Fetch a payment's current state."""
        if self.mode == "mock":
            return self._mock.fetch_payment(payment_id)
        return self._request("GET", f"/payments/{payment_id}")

    def capture_payment(self, *, payment_id: str, amount: int, currency: str) -> Dict[str, Any]:
        """Capture an authorized payment."""
        if self.mode == "mock":
            return self._mock.capture_payment(payment_id, amount, currency)
        return self._request(
            "POST", f"/payments/{payment_id}/capture", json_body={"amount": amount, "currency": currency}
        )

    def refund_payment(self, *, payment_id: str, amount: int) -> Dict[str, Any]:
        """Refund a captured payment."""
        if self.mode == "mock":
            return self._mock.refund_payment(payment_id, amount)
        return self._request("POST", f"/payments/{payment_id}/refund", json_body={"amount": amount})


#: Process-wide default client.
razorpay_client = RazorpayClient()
