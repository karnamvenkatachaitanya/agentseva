"""Production-ready, bounded Razorpay tool registry for the agent.

Exposes four schema-validated tools — ``create_order``,
``generate_payment_link``, ``verify_payment_status`` and
``trigger_payment_recovery`` — behind a :class:`RazorpayToolRegistry`.

Design guarantees
-----------------
* **Strict Pydantic v2 validation** on every input, with sanitised strings and
  hard amount/notes bounds. Tools *never* raise into the caller; validation and
  gateway failures come back as structured ``{"status": "error", ...}`` dicts.
* **HMAC-SHA256 signature verification** for payment and webhook signatures,
  using :func:`hmac.compare_digest` (constant-time).
* **Mock-mode fallback**: when ``RAZORPAY_KEY_ID`` / ``RAZORPAY_KEY_SECRET`` are
  absent the registry runs a deterministic in-process simulator so the agent is
  fully functional offline. The official ``razorpay`` SDK is used when present;
  otherwise a direct ``httpx`` client is used for live calls.

All money crosses the Razorpay boundary as integer **paise**; the public tool
surface accepts INR (rupees) as a float and converts safely via
:class:`decimal.Decimal` to avoid binary-float rounding.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import itertools
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Dict, List, Optional

import httpx
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, settings
from app.core.security_utils import is_https_url
from app.db.base import SessionLocal
from app.services import orders as orders_service
from app.services.catalog import price_order_items, search_products

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constants / bounds
# --------------------------------------------------------------------------- #

#: Absolute safety ceiling independent of per-deployment config (₹1 crore).
ABSOLUTE_MAX_INR = Decimal("10000000")
#: Razorpay caps order ``notes`` at 15 key/value pairs.
MAX_NOTES = 15
MAX_NOTE_LEN = 256
#: Secret used for HMAC in mock mode so signatures are reproducible in tests.
MOCK_SECRET = "mock_razorpay_secret"  # noqa: S105 - not a real credential
VALID_RETRY_CHANNELS = ("sms", "email", "whatsapp", "upi")
_PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class RazorpayToolError(Exception):
    """Raised internally by the gateway; always converted to an error dict."""

    def __init__(self, message: str, *, category: str = "gateway", status_code: Optional[int] = None):
        self.category = category
        self.status_code = status_code
        super().__init__(message)


# --------------------------------------------------------------------------- #
# Sanitising helpers
# --------------------------------------------------------------------------- #


def _sanitize_text(value: Any) -> str:
    """Strip control characters and surrounding whitespace from a string.

    Raises ``ValueError`` (→ Pydantic ``ValidationError``) if the value is not a
    non-empty string after cleaning.
    """
    if not isinstance(value, str):
        raise ValueError("must be a string")
    cleaned = _CONTROL_RE.sub("", value).strip()
    if not cleaned:
        raise ValueError("must not be empty after sanitisation")
    return cleaned


SanitizedText = Annotated[str, BeforeValidator(_sanitize_text)]


def _to_paise(amount_inr: float) -> int:
    """Convert an INR float to integer paise, rejecting sub-paise precision."""
    try:
        dec = Decimal(str(amount_inr))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("amount is not a valid number") from exc
    if not dec.is_finite():
        raise ValueError("amount must be a finite number")
    if -dec.as_tuple().exponent > 2:
        raise ValueError("amount cannot have more than 2 decimal places")
    return int((dec * 100).to_integral_value())


# --------------------------------------------------------------------------- #
# Pydantic v2 input schemas
# --------------------------------------------------------------------------- #


class _StrictInput(BaseModel):
    """Base input model: forbids unknown keys, strips string whitespace."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OrderLineInput(_StrictInput):
    """A single cart line referencing a catalog product by id."""

    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, gt=0, le=999)


class SearchCatalogInput(_StrictInput):
    """Arguments for :meth:`RazorpayToolRegistry.search_product_catalog`."""

    query: Annotated[str, Field(min_length=1, max_length=120)]
    category: Optional[str] = Field(default=None, max_length=100)


class CreateOrderInput(_StrictInput):
    """Validated arguments for :meth:`RazorpayToolRegistry.create_order`.

    Supply either ``amount_in_inr`` (explicit) or ``items`` (priced from the
    real catalog in SQLite) — at least one is required.
    """

    amount_in_inr: Optional[float] = Field(default=None, gt=0, le=float(ABSOLUTE_MAX_INR))
    currency: Annotated[str, Field(min_length=3, max_length=3)] = "INR"
    receipt_id: Annotated[SanitizedText, Field(max_length=40)]
    notes: Dict[str, str] = Field(default_factory=dict)
    items: Optional[List[OrderLineInput]] = None

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _require_amount_or_items(self) -> "CreateOrderInput":
        if self.amount_in_inr is None and not self.items:
            raise ValueError("provide either amount_in_inr or items")
        return self

    @field_validator("notes")
    @classmethod
    def _validate_notes(cls, v: Dict[str, str]) -> Dict[str, str]:
        if len(v) > MAX_NOTES:
            raise ValueError(f"notes cannot exceed {MAX_NOTES} entries")
        clean: Dict[str, str] = {}
        for key, val in v.items():
            if not isinstance(key, str) or not isinstance(val, str):
                raise ValueError("note keys and values must be strings")
            k = _CONTROL_RE.sub("", key).strip()[:MAX_NOTE_LEN]
            value = _CONTROL_RE.sub("", val).strip()[:MAX_NOTE_LEN]
            if k:
                clean[k] = value
        return clean

    @property
    def paise(self) -> int:
        """Order amount as integer paise."""
        return _to_paise(self.amount_in_inr)


class PaymentLinkInput(_StrictInput):
    """Validated arguments for :meth:`RazorpayToolRegistry.generate_payment_link`.

    Supply either ``amount`` (explicit) or ``items`` (priced from the catalog).
    """

    amount: Optional[float] = Field(default=None, gt=0, le=float(ABSOLUTE_MAX_INR))
    customer_name: Annotated[SanitizedText, Field(max_length=120)]
    customer_phone: SanitizedText
    description: Annotated[SanitizedText, Field(max_length=255)]
    items: Optional[List[OrderLineInput]] = None

    @field_validator("customer_phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        compact = v.replace(" ", "").replace("-", "")
        if not _PHONE_RE.match(compact):
            raise ValueError("customer_phone must be a valid E.164-style number")
        return compact

    @model_validator(mode="after")
    def _require_amount_or_items(self) -> "PaymentLinkInput":
        if self.amount is None and not self.items:
            raise ValueError("provide either amount or items")
        return self

    @property
    def paise(self) -> int:
        """Payment-link amount as integer paise."""
        return _to_paise(self.amount)


class VerifyPaymentInput(_StrictInput):
    """Validated arguments for :meth:`RazorpayToolRegistry.verify_payment_status`."""

    payment_id: Annotated[SanitizedText, Field(max_length=64)]
    order_id: Annotated[SanitizedText, Field(max_length=64)]
    signature: Optional[str] = Field(
        default=None, description="Razorpay HMAC-SHA256 signature to verify."
    )


class PaymentRecoveryInput(_StrictInput):
    """Validated arguments for :meth:`RazorpayToolRegistry.trigger_payment_recovery`."""

    order_id: Annotated[SanitizedText, Field(max_length=64)]
    failure_reason: Annotated[SanitizedText, Field(max_length=255)]
    retry_channel: str

    @field_validator("retry_channel")
    @classmethod
    def _validate_channel(cls, v: str) -> str:
        channel = v.strip().lower()
        if channel not in VALID_RETRY_CHANNELS:
            raise ValueError(f"retry_channel must be one of {VALID_RETRY_CHANNELS}")
        return channel


# --------------------------------------------------------------------------- #
# Signature verification (HMAC-SHA256)
# --------------------------------------------------------------------------- #


def compute_payment_signature(order_id: str, payment_id: str, secret: str) -> str:
    """Return the Razorpay HMAC-SHA256 hex signature for ``order_id|payment_id``."""
    message = f"{order_id}|{payment_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_payment_signature(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    """Constant-time verification of a Razorpay payment signature."""
    if not signature or not secret:
        return False
    expected = compute_payment_signature(order_id, payment_id, secret)
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """Constant-time verification of a Razorpay webhook payload signature."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# --------------------------------------------------------------------------- #
# Gateway (live SDK / httpx + deterministic mock)
# --------------------------------------------------------------------------- #


class _RazorpayGateway:
    """Thin transport layer: official SDK or httpx when live, simulator when mock."""

    def __init__(self, config: Settings):
        self._cfg = config
        self.key_id = config.RAZORPAY_KEY_ID
        self.key_secret = config.RAZORPAY_KEY_SECRET
        self.mock = not (self.key_id and self.key_secret)
        # In mock mode expose a reproducible secret so signatures are testable.
        self.effective_secret = self.key_secret if not self.mock else MOCK_SECRET

        self._counter = itertools.count(1)
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._payments: Dict[str, Dict[str, Any]] = {}
        self._sdk = self._init_sdk() if not self.mock else None

    # -- live SDK ------------------------------------------------------- #
    def _init_sdk(self) -> Optional[Any]:
        try:
            import razorpay  # type: ignore

            return razorpay.Client(auth=(self.key_id, self.key_secret))
        except ImportError:
            logger.info("razorpay SDK not installed; using direct httpx client for live calls.")
            return None

    def _http(self, method: str, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._cfg.RAZORPAY_BASE_URL.rstrip('/')}{path}"
        raw = f"{self.key_id}:{self.key_secret}".encode("utf-8")
        headers = {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}
        try:
            with httpx.Client(timeout=self._cfg.RAZORPAY_TIMEOUT_SECONDS) as client:
                resp = client.request(method, url, headers=headers, json=body)
            if resp.status_code == 401:
                raise RazorpayToolError("authentication failed", category="auth", status_code=401)
            if resp.status_code >= 400:
                raise RazorpayToolError(
                    f"Razorpay API error {resp.status_code}: {resp.text[:200]}",
                    category="api",
                    status_code=resp.status_code,
                )
            return resp.json()
        except httpx.TimeoutException as exc:
            raise RazorpayToolError(f"request timed out: {exc}", category="timeout") from exc
        except httpx.HTTPError as exc:
            raise RazorpayToolError(f"transport error: {exc}", category="network") from exc

    def _next(self, prefix: str) -> str:
        return f"{prefix}_mock_{next(self._counter)}"

    # -- public operations ---------------------------------------------- #
    def create_order(self, *, paise: int, currency: str, receipt: str, notes: Dict[str, str]) -> Dict[str, Any]:
        payload = {"amount": paise, "currency": currency, "receipt": receipt, "notes": notes}
        if self.mock:
            order = {"id": self._next("order"), "status": "created", **payload}
            self._orders[order["id"]] = order
            return order
        if self._sdk is not None:
            return self._sdk.order.create(data=payload)
        return self._http("POST", "/orders", payload)

    def create_payment_link(self, *, paise: int, name: str, phone: str, description: str) -> Dict[str, Any]:
        payload = {
            "amount": paise,
            "currency": "INR",
            "description": description,
            "customer": {"name": name, "contact": phone},
            "notify": {"sms": True, "email": False},
        }
        if self.mock:
            link_id = self._next("plink")
            return {"id": link_id, "status": "created", "short_url": f"https://rzp.io/i/{link_id}", **payload}
        if self._sdk is not None:
            return self._sdk.payment_link.create(payload)
        return self._http("POST", "/payment_links", payload)

    def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        if self.mock:
            if payment_id in self._payments:
                return self._payments[payment_id]
            status = "failed" if "fail" in payment_id.lower() else "captured"
            payment = {"id": payment_id, "status": status, "amount": 0, "currency": "INR"}
            self._payments[payment_id] = payment
            return payment
        if self._sdk is not None:
            return self._sdk.payment.fetch(payment_id)
        return self._http("GET", f"/payments/{payment_id}", {})

    def fetch_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        if self.mock:
            return self._orders.get(order_id)
        try:
            if self._sdk is not None:
                return self._sdk.order.fetch(order_id)
            return self._http("GET", f"/orders/{order_id}", {})
        except RazorpayToolError:
            return None

    def seed_payment(self, payment_id: str, *, status: str, amount: int = 0) -> None:
        """Test helper: pre-load a payment state in mock mode."""
        self._payments[payment_id] = {
            "id": payment_id, "status": status, "amount": amount, "currency": "INR"
        }


# --------------------------------------------------------------------------- #
# Tool registry
# --------------------------------------------------------------------------- #


def _error(code: str, detail: Any, **extra: Any) -> Dict[str, Any]:
    return {"status": "error", "error": code, "detail": detail, **extra}


class RazorpayToolRegistry:
    """Bounded, schema-validated Razorpay tools for agent tool-use.

    Parameters
    ----------
    config:
        Settings supplying credentials and amount bounds. Defaults to the global
        :data:`app.core.config.settings`; tests inject their own.
    """

    def __init__(self, config: Optional[Settings] = None, session_factory: Optional[sessionmaker] = None):
        self._cfg = config or settings
        self.gateway = _RazorpayGateway(self._cfg)
        # Session factory for catalog lookups / order persistence (app DB by default).
        self._session_factory = session_factory or SessionLocal

    # ------------------------------------------------------------------ #
    @property
    def mode(self) -> str:
        """``"mock"`` or ``"live"`` depending on credential presence."""
        return "mock" if self.gateway.mock else "live"

    def _price_items(self, items: List[OrderLineInput]) -> Dict[str, Any]:
        """Price catalog line items via the DB; returns the pricing result dict."""
        with self._session_factory() as session:
            return price_order_items(session, [it.model_dump() for it in items])

    # ------------------------------------------------------------------ #
    # Tool 0: search_product_catalog (read-only)
    # ------------------------------------------------------------------ #
    def search_product_catalog(self, query: str, category: Optional[str] = None) -> dict:
        """Search the real product catalog in SQLite by name/description + category."""
        try:
            data = SearchCatalogInput(query=query, category=category)
        except ValidationError as exc:
            return _error("validation_error", exc.errors(include_url=False))
        with self._session_factory() as session:
            products = [p.to_dict() for p in search_products(session, data.query, data.category)]
        return {"status": "success", "count": len(products), "products": products}

    def _check_amount_bounds(self, paise: int) -> Optional[Dict[str, Any]]:
        """Enforce configured min/max transaction bounds (in paise)."""
        if paise < self._cfg.MIN_TXN_AMOUNT_PAISE:
            return _error(
                "amount_below_minimum",
                f"amount {paise} paise is below minimum {self._cfg.MIN_TXN_AMOUNT_PAISE} paise",
            )
        if paise > self._cfg.MAX_TXN_AMOUNT_PAISE:
            return _error(
                "amount_above_maximum",
                f"amount {paise} paise exceeds maximum {self._cfg.MAX_TXN_AMOUNT_PAISE} paise",
            )
        return None

    # ------------------------------------------------------------------ #
    # Tool 1: create_order
    # ------------------------------------------------------------------ #
    def create_order(
        self,
        amount_in_inr: Optional[float] = None,
        currency: str = "INR",
        receipt_id: str = "",
        notes: Optional[dict] = None,
        items: Optional[list] = None,
    ) -> dict:
        """Create a Razorpay order, pricing ``items`` from the real catalog if given."""
        try:
            data = CreateOrderInput(
                amount_in_inr=amount_in_inr, currency=currency, receipt_id=receipt_id,
                notes=notes or {}, items=items,
            )
        except ValidationError as exc:
            return _error("validation_error", exc.errors(include_url=False))

        if currency.upper() not in self._cfg.allowed_currencies:
            return _error("currency_not_allowed", f"currency {currency.upper()} is not permitted")

        # Resolve the amount from the catalog when items are supplied.
        line_items: Optional[List[Dict[str, Any]]] = None
        if data.items:
            priced = self._price_items(data.items)
            if not priced["ok"]:
                return _error("catalog_pricing_failed", priced["errors"], line_items=priced["line_items"])
            amount_value = priced["total_inr"]
            line_items = priced["line_items"]
        else:
            amount_value = data.amount_in_inr

        try:
            paise = _to_paise(amount_value)
        except ValueError as exc:
            return _error("validation_error", str(exc))

        bounds_error = self._check_amount_bounds(paise)
        if bounds_error:
            return bounds_error

        try:
            order = self.gateway.create_order(
                paise=paise, currency=data.currency, receipt=data.receipt_id, notes=data.notes
            )
        except RazorpayToolError as exc:
            return _error("gateway_error", str(exc), category=exc.category)

        db_order_id = self._persist_order(
            data.notes, line_items, amount_value, razorpay_order_id=order.get("id")
        ) if line_items else None

        return {
            "status": "success",
            "mode": self.mode,
            "order_id": order.get("id"),
            "amount_in_paise": paise,
            "amount_in_inr": float(amount_value),
            "currency": data.currency,
            "receipt_id": data.receipt_id,
            "line_items": line_items,
            "db_order_id": db_order_id,
            "order": order,
        }

    def _persist_order(
        self,
        notes: Dict[str, str],
        line_items: Optional[List[Dict[str, Any]]],
        amount_inr: float,
        *,
        razorpay_order_id: Optional[str] = None,
        razorpay_payment_link_id: Optional[str] = None,
        payment_link: Optional[str] = None,
    ) -> Optional[int]:
        """Best-effort persistence of an Order row (never raises into the tool)."""
        try:
            record = orders_service.create_order(
                customer_name=notes.get("customer_name", "Guest"),
                customer_phone=notes.get("customer_phone", ""),
                items=line_items or [],
                total_amount=amount_inr,
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_link_id=razorpay_payment_link_id,
                payment_link=payment_link,
                status="pending",
                session_factory=self._session_factory,
            )
            return record.get("id")
        except Exception:  # noqa: BLE001 - persistence must not break the tool
            logger.exception("Failed to persist order row")
            return None

    # ------------------------------------------------------------------ #
    # Tool 2: generate_payment_link
    # ------------------------------------------------------------------ #
    def generate_payment_link(
        self,
        amount: Optional[float] = None,
        customer_name: str = "",
        customer_phone: str = "",
        description: str = "",
        items: Optional[list] = None,
    ) -> dict:
        """Generate a Razorpay payment link, pricing ``items`` from the catalog if given."""
        try:
            data = PaymentLinkInput(
                amount=amount, customer_name=customer_name, customer_phone=customer_phone,
                description=description, items=items,
            )
        except ValidationError as exc:
            return _error("validation_error", exc.errors(include_url=False))

        line_items: Optional[List[Dict[str, Any]]] = None
        if data.items:
            priced = self._price_items(data.items)
            if not priced["ok"]:
                return _error("catalog_pricing_failed", priced["errors"], line_items=priced["line_items"])
            amount_value = priced["total_inr"]
            line_items = priced["line_items"]
        else:
            amount_value = data.amount

        try:
            paise = _to_paise(amount_value)
        except ValueError as exc:
            return _error("validation_error", str(exc))

        bounds_error = self._check_amount_bounds(paise)
        if bounds_error:
            return bounds_error

        try:
            link = self.gateway.create_payment_link(
                paise=paise, name=data.customer_name, phone=data.customer_phone, description=data.description
            )
        except RazorpayToolError as exc:
            return _error("gateway_error", str(exc), category=exc.category)

        # HTTPS compliance: never hand a non-secure redirect URL to a customer.
        short_url = link.get("short_url")
        if short_url and not is_https_url(short_url):
            return _error("insecure_payment_link", f"payment link is not https: {short_url!r}")

        db_order_id = None
        if line_items:
            db_order_id = self._persist_order(
                {"customer_name": data.customer_name, "customer_phone": data.customer_phone},
                line_items, amount_value,
                razorpay_payment_link_id=link.get("id"), payment_link=short_url,
            )

        return {
            "status": "success",
            "mode": self.mode,
            "payment_link_id": link.get("id"),
            "short_url": short_url,
            "amount_in_paise": paise,
            "customer_phone": data.customer_phone,
            "line_items": line_items,
            "db_order_id": db_order_id,
            "order": {"id": db_order_id, "amount_in_inr": float(amount_value)},
            "link": link,
        }

    # ------------------------------------------------------------------ #
    # Tool 3: verify_payment_status
    # ------------------------------------------------------------------ #
    def verify_payment_status(self, payment_id: str, order_id: str, signature: Optional[str] = None) -> dict:
        """Fetch a payment's status and, if a signature is supplied, verify it.

        HMAC-SHA256 verification uses ``order_id|payment_id`` and the account
        secret (a reproducible mock secret in mock mode).
        """
        try:
            data = VerifyPaymentInput(payment_id=payment_id, order_id=order_id, signature=signature)
        except ValidationError as exc:
            return _error("validation_error", exc.errors(include_url=False))

        signature_valid: Optional[bool] = None
        if data.signature is not None:
            signature_valid = verify_payment_signature(
                data.order_id, data.payment_id, data.signature, self.gateway.effective_secret
            )

        try:
            payment = self.gateway.fetch_payment(data.payment_id)
        except RazorpayToolError as exc:
            return _error("gateway_error", str(exc), category=exc.category)

        status = str(payment.get("status", "unknown"))
        return {
            "status": "success",
            "mode": self.mode,
            "payment_id": data.payment_id,
            "order_id": data.order_id,
            "payment_status": status,
            "is_paid": status in ("captured", "authorized"),
            "signature_valid": signature_valid,
            "payment": payment,
        }

    # ------------------------------------------------------------------ #
    # Tool 4: trigger_payment_recovery
    # ------------------------------------------------------------------ #
    def trigger_payment_recovery(self, order_id: str, failure_reason: str, retry_channel: str) -> dict:
        """Plan and initiate recovery for a failed order over the chosen channel.

        Selects a strategy from ``failure_reason`` and, when the original order
        amount is known, regenerates a payment link the customer can retry with.
        """
        try:
            data = PaymentRecoveryInput(
                order_id=order_id, failure_reason=failure_reason, retry_channel=retry_channel
            )
        except ValidationError as exc:
            return _error("validation_error", exc.errors(include_url=False))

        strategy = self._recovery_strategy(data.failure_reason)
        order = self.gateway.fetch_order(data.order_id)

        payment_link: Optional[str] = None
        note = ""
        if order and isinstance(order.get("amount"), int) and order["amount"] > 0:
            try:
                link = self.gateway.create_payment_link(
                    paise=order["amount"],
                    name="Valued Customer",
                    phone="+910000000000",
                    description=f"Retry payment for order {data.order_id}",
                )
                payment_link = link.get("short_url")
            except RazorpayToolError as exc:
                note = f"payment link generation failed: {exc}"
        else:
            note = "original order amount unavailable; recovery scheduled without a fresh link"

        return {
            "status": "success",
            "mode": self.mode,
            "order_id": data.order_id,
            "failure_reason": data.failure_reason,
            "retry_channel": data.retry_channel,
            "strategy": strategy,
            "payment_link": payment_link,
            "next_action": f"notify_customer_via_{data.retry_channel}",
            "note": note,
        }

    @staticmethod
    def _recovery_strategy(failure_reason: str) -> str:
        """Map a failure reason to a deterministic recovery strategy label."""
        reason = failure_reason.lower()
        if any(w in reason for w in ("insufficient", "balance", "limit")):
            return "suggest_alternate_instrument"
        if any(w in reason for w in ("timeout", "network", "gateway")):
            return "immediate_retry_same_channel"
        if any(w in reason for w in ("cancel", "abandon", "dropped")):
            return "dunning_reminder_sequence"
        return "reissue_payment_link"

    # ------------------------------------------------------------------ #
    # Introspection for Claude tool-use
    # ------------------------------------------------------------------ #
    def anthropic_tools(self) -> List[Dict[str, Any]]:
        """Return the tools as Anthropic tool-use schema dicts."""
        return [
            {"name": "search_product_catalog",
             "description": "Search the merchant's real product catalog by name/description and "
                            "optional category. Returns products with id, price_inr and stock. "
                            "Use the returned product ids as `items` when creating orders/links.",
             "input_schema": SearchCatalogInput.model_json_schema()},
            {"name": "create_order", "description": CreateOrderInput.__doc__ or "Create a Razorpay order.",
             "input_schema": CreateOrderInput.model_json_schema()},
            {"name": "generate_payment_link",
             "description": PaymentLinkInput.__doc__ or "Generate a Razorpay payment link.",
             "input_schema": PaymentLinkInput.model_json_schema()},
            {"name": "verify_payment_status",
             "description": VerifyPaymentInput.__doc__ or "Verify a payment's status/signature.",
             "input_schema": VerifyPaymentInput.model_json_schema()},
            {"name": "trigger_payment_recovery",
             "description": PaymentRecoveryInput.__doc__ or "Trigger payment recovery.",
             "input_schema": PaymentRecoveryInput.model_json_schema()},
        ]


#: Process-wide default registry (mock unless Razorpay credentials are set).
razorpay_tools = RazorpayToolRegistry()
