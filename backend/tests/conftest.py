"""Shared pytest fixtures for the engine test-suite.

Everything is wired to isolated, in-process resources: an in-memory SQLite
audit trail, a fresh guardrail validator with test limits, and the Razorpay
mock backend. No network, no API keys, fully deterministic.
"""

from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# Force a hermetic, offline test session BEFORE any app import. Real
# environment variables take precedence over the .env file in pydantic-settings,
# so this neutralises a live `.env` (real Razorpay/Anthropic keys) and keeps the
# whole suite deterministic and network-free.
# ---------------------------------------------------------------------------
os.environ["RAZORPAY_MODE"] = "mock"
os.environ["RAZORPAY_KEY_ID"] = ""
os.environ["RAZORPAY_KEY_SECRET"] = ""
os.environ["RAZORPAY_WEBHOOK_SECRET"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["SQLALCHEMY_ECHO"] = "False"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure the backend package root is importable when pytest is run from anywhere.
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.core.config import Settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.engine.audit import AuditLogger  # noqa: E402
from app.engine.guardrails import PaymentGuardrailValidator  # noqa: E402
from app.engine.razorpay_client import RazorpayClient  # noqa: E402


@pytest.fixture()
def test_settings() -> Settings:
    """Settings with small, predictable financial limits for testing."""
    return Settings(
        MIN_TXN_AMOUNT_PAISE=100,
        MAX_TXN_AMOUNT_PAISE=100_000,      # ₹1,000
        DAILY_CAP_PAISE=150_000,           # ₹1,500
        ALLOWED_CURRENCIES="INR",
        RAZORPAY_MODE="mock",
        _env_file=None,
    )


@pytest.fixture()
def audit_logger() -> AuditLogger:
    """An AuditLogger backed by a shared in-memory SQLite database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return AuditLogger(session_factory=factory)


@pytest.fixture()
def guardrails(test_settings: Settings) -> PaymentGuardrailValidator:
    """A fresh guardrail validator using the test limits."""
    return PaymentGuardrailValidator(config=test_settings)


@pytest.fixture()
def razorpay(test_settings: Settings) -> RazorpayClient:
    """A Razorpay client in deterministic mock mode."""
    return RazorpayClient(config=test_settings)
