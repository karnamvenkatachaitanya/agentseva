"""Shared SQLAlchemy engine, sessions, and runtime database helpers."""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.SQLALCHEMY_ECHO,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _register_models() -> None:
    """Import every model so it is represented in ``Base.metadata``."""
    from app.engine import audit  # noqa: F401
    from app.audit import logger as audit_logger  # noqa: F401
    from app import models  # noqa: F401

def seed_catalog() -> int:
    """Idempotently seed the merchant catalog and return the inserted count."""
    from app.services.catalog import seed_catalog_if_empty

    return seed_catalog_if_empty()


def init_db() -> None:
    """Verify connectivity and seed catalog data without running schema DDL."""
    _register_models()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    seeded = seed_catalog()
    if seeded:
        import logging

        logging.getLogger(__name__).info("Seeded %d sample products into catalog.", seeded)
