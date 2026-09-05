"""SQLAlchemy engine / session / declarative base.

A single shared engine + ``SessionLocal`` factory used by the audit trail
(and any future persistence). SQLite is the default; the ``check_same_thread``
flag is disabled so the engine can be used across FastAPI's threadpool.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.SQLALCHEMY_ECHO,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def init_db() -> None:
    """Create all tables, then seed the product catalog if it is empty."""
    from app.engine import audit  # noqa: F401  (registers AuditLog)
    from app.audit import logger as audit_logger  # noqa: F401  (registers TransactionAuditLog)
    from app import models  # noqa: F401  (registers Product, Order)

    Base.metadata.create_all(bind=engine)

    # Seed sample merchant products on first boot.
    from app.services.catalog import seed_catalog_if_empty

    seeded = seed_catalog_if_empty()
    if seeded:
        import logging

        logging.getLogger(__name__).info("Seeded %d sample products into catalog.", seeded)
