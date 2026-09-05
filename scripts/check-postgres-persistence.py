#!/usr/bin/env python3
"""Smoke-test the managed PostgreSQL schema and restart persistence.

The check never uses the merchant schema directly.  It creates a uniquely
named PostgreSQL schema, applies the real Alembic migrations with that schema
first on ``search_path``, exercises the normal application startup, and drops
the schema in a ``finally`` block.  The explicit opt-in prevents an accidental
run against a deployment database.

Run against the managed development database with:

    AGENTSEVA_POSTGRES_SMOKE=1 python scripts/check-postgres-persistence.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
_DDL_STATEMENT = re.compile(
    r"^\s*(?:CREATE|ALTER|DROP|TRUNCATE|REINDEX|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def _database_url() -> URL:
    raw_url = os.environ.get("DATABASE_URL", "")
    if not raw_url:
        raise SystemExit("DATABASE_URL is required")
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        raise SystemExit("This check requires a PostgreSQL DATABASE_URL")
    if url.drivername == "postgresql":
        # Match Settings.use_psycopg_driver without importing the application
        # before the disposable schema has been created.
        url = url.set(drivername="postgresql+psycopg")
    if os.environ.get("REPLIT_DEPLOYMENT") == "1":
        raise SystemExit("Refusing to run the smoke check from a deployment")
    if os.environ.get("AGENTSEVA_POSTGRES_SMOKE") != "1":
        raise SystemExit(
            "Refusing to run against a managed database without explicit opt-in. "
            "Set AGENTSEVA_POSTGRES_SMOKE=1."
        )
    return url


def _isolated_url(url: URL, schema: str) -> URL:
    """Put the disposable schema before public for every app connection."""
    return url.set(query={**url.query, "options": f"-csearch_path={schema},public"})


def _create_schema(url: URL, schema: str) -> None:
    with create_engine(url, poolclass=NullPool).begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))


def _drop_schema(url: URL, schema: str) -> None:
    # The generated schema name is restricted to lowercase ASCII and is never
    # derived from user input.  CASCADE also removes the test-only triggers and
    # function created by the immutability migration.
    with create_engine(url, poolclass=NullPool).begin() as connection:
        connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def _apply_migrations() -> None:
    sys.path.insert(0, str(BACKEND))
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(config, "head")


def _registered_tables() -> set[str]:
    from app.db.base import Base, _register_models

    _register_models()
    return set(Base.metadata.tables)


def _assert_registered_tables(expected: Iterable[str]) -> None:
    from app.db.base import engine

    actual = set(inspect(engine).get_table_names())
    missing = set(expected) - actual
    if missing:
        raise AssertionError(f"registered tables missing from PostgreSQL: {sorted(missing)}")


def _run_startup_without_ddl() -> None:
    """Run normal startup and fail if it attempts any schema mutation."""
    from app.db.base import engine, init_db

    ddl_statements: list[str] = []

    def reject_ddl(_conn, _cursor, statement, _parameters, _context, _executemany):
        if _DDL_STATEMENT.match(statement):
            ddl_statements.append(statement)

    event.listen(engine, "before_cursor_execute", reject_ddl)
    try:
        init_db()
    finally:
        event.remove(engine, "before_cursor_execute", reject_ddl)

    if ddl_statements:
        raise AssertionError(
            "runtime startup executed DDL: "
            + "; ".join(statement.strip().splitlines()[0] for statement in ddl_statements)
        )


def _assert_catalog_seed_is_idempotent() -> None:
    from app.db.base import SessionLocal
    from app.models.product import Product
    from app.services.catalog import SEED_CATALOG, seed_catalog_if_empty

    with SessionLocal() as session:
        count_before = session.query(Product).count()
    if count_before != len(SEED_CATALOG):
        raise AssertionError(
            "normal startup did not seed the isolated catalog: "
            f"found {count_before}, expected {len(SEED_CATALOG)}"
        )

    first_inserted = seed_catalog_if_empty()
    second_inserted = seed_catalog_if_empty()
    with SessionLocal() as session:
        count_after = session.query(Product).count()

    if first_inserted != 0 or second_inserted != 0:
        raise AssertionError(
            "catalog seeding was not idempotent: "
            f"first={first_inserted}, second={second_inserted}"
        )
    if count_after != len(SEED_CATALOG):
        raise AssertionError(f"catalog row count is {count_after}, expected {len(SEED_CATALOG)}")


def _write_test_records(marker: str) -> int:
    from app.audit.logger import AuditLogger as TransactionAuditLogger
    from app.db.base import SessionLocal
    from app.engine.audit import AuditLog, AuditLogger
    from app.engine.schemas import ActionType
    from app.models.order import Order

    order_marker = f"{marker}-order"
    with SessionLocal() as session:
        order = Order(
            customer_name=marker,
            customer_phone="+919999999999",
            items=[{"product_id": 1, "name": "smoke-test", "quantity": 1}],
            total_amount=123.45,
            razorpay_order_id=order_marker,
            status="pending",
        )
        session.add(order)
        session.commit()
        session.refresh(order)
        order_id = order.id

    AuditLogger().record(
        marker,
        ActionType.INTENT,
        "PostgreSQL persistence smoke test",
        payload={"marker": marker},
    )
    TransactionAuditLogger().record(
        marker,
        "postgres_persistence_smoke",
        "success",
        trace_id=f"{marker}-trace",
        user_intent=marker,
        agent_reasoning="Verify transaction audit persistence after restart",
        payload_sent={"marker": marker},
        api_response={"ok": True},
    )
    return order_id


def _verify_persisted_records(marker: str, order_id: int) -> None:
    from app.db.base import SessionLocal
    from app.engine.audit import AuditLog
    from app.audit.logger import TransactionAuditLog
    from app.models.order import Order

    with SessionLocal() as session:
        order = session.get(Order, order_id)
        engine_audit = session.scalars(
            select(AuditLog).where(AuditLog.session_id == marker)
        ).all()
        transaction_audit = session.scalars(
            select(TransactionAuditLog).where(TransactionAuditLog.session_id == marker)
        ).all()

    if order is None or order.customer_name != marker:
        raise AssertionError("order did not survive the application process restart")
    if len(engine_audit) != 1 or engine_audit[0].payload_json != json.dumps({"marker": marker}):
        raise AssertionError("engine audit record did not survive the application process restart")
    if len(transaction_audit) != 1 or transaction_audit[0].trace_id != f"{marker}-trace":
        raise AssertionError(
            "transaction audit record did not survive the application process restart"
        )


async def _verify_after_restart(marker: str, order_id: int) -> None:
    # Entering the real FastAPI lifespan proves the new process runs normal
    # startup, rather than merely opening a SQLAlchemy connection.
    sys.path.insert(0, str(BACKEND))
    from app.main import app

    async with app.router.lifespan_context(app):
        _verify_persisted_records(marker, order_id)


def _run_after_restart(marker: str, order_id: int) -> None:
    asyncio.run(_verify_after_restart(marker, order_id))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-after-restart", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("marker", nargs="?")
    parser.add_argument("order_id", nargs="?", type=int)
    args = parser.parse_args()
    if args.verify_after_restart and (not args.marker or args.order_id is None):
        parser.error("restart verification requires a marker and order id")
    if not args.verify_after_restart and (args.marker or args.order_id is not None):
        parser.error("marker and order id are only valid for restart verification")
    return args


def main() -> None:
    args = _parse_args()
    if args.verify_after_restart:
        _database_url()
        _run_after_restart(args.marker, args.order_id)
        print("PostgreSQL restart verification passed.")
        return

    original_url = _database_url()
    schema = f"agentseva_smoke_{uuid.uuid4().hex[:16]}"
    isolated_url = _isolated_url(original_url, schema)
    os.environ["DATABASE_URL"] = isolated_url.render_as_string(hide_password=False)
    schema_created = False

    try:
        _create_schema(original_url, schema)
        schema_created = True
        _apply_migrations()

        expected_tables = _registered_tables()
        _assert_registered_tables(expected_tables)
        _run_startup_without_ddl()
        _assert_registered_tables(expected_tables)
        _assert_catalog_seed_is_idempotent()

        marker = f"postgres-smoke-{uuid.uuid4().hex[:16]}"
        order_id = _write_test_records(marker)
        child_env = os.environ.copy()
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__)),
                "--verify-after-restart",
                marker,
                str(order_id),
            ],
            cwd=ROOT,
            env=child_env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(
                "restart verification failed:\n"
                f"{result.stdout.strip()}\n{result.stderr.strip()}".strip()
            )
        print(
            "PostgreSQL persistence smoke check passed: "
            f"{len(expected_tables)} tables, idempotent catalog seed, no runtime DDL, "
            "and order plus both audit records survived restart."
        )
    finally:
        if schema_created:
            from app.db.base import engine

            engine.dispose()
            _drop_schema(original_url, schema)


if __name__ == "__main__":
    main()