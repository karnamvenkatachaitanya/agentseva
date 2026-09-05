"""PostgreSQL integration checks for the database-level audit guard.

The test is opt-in because the default suite deliberately uses SQLite and
should not mutate a developer's managed database.  Run it against a disposable
PostgreSQL database with AUDIT_IMMUTABILITY_TEST_DATABASE_URL set.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

DATABASE_URL = os.environ.get("AUDIT_IMMUTABILITY_TEST_DATABASE_URL")


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parents[1]
    return Config(str(root / "alembic.ini"))


def _insert_audit_rows(connection, session_id: str) -> None:
    connection.execute(
        text(
            f"""
            INSERT INTO audit_log
                (session_id, sequence, action_type, actor, summary, payload_json, created_at)
            VALUES
                ('{session_id}', 1, 'intent', 'test', 'original', '{{}}', CURRENT_TIMESTAMP)
            """
        )
    )
    connection.execute(
        text(
            f"""
            INSERT INTO transaction_audit_logs
                (trace_id, session_id, timestamp, user_intent, agent_reasoning,
                 tool_called, payload_sent, api_response, status, latency_ms)
            VALUES
                ('{session_id}', '{session_id}', CURRENT_TIMESTAMP,
                 'original', 'original', 'test', '{{}}', NULL, 'initiated', NULL)
            """
        )
    )


def _assert_rejected(engine, statement: str) -> None:
    with engine.begin() as connection:
        with pytest.raises(DBAPIError, match="append-only"):
            connection.execute(text(statement))


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="set AUDIT_IMMUTABILITY_TEST_DATABASE_URL for PostgreSQL integration tests",
)
def test_postgresql_guards_reject_rewrites_but_allow_append_and_read():
    """Both tables remain writable through INSERT and readable after guarding."""
    from app.core.config import settings

    # The shared test fixtures intentionally configure SQLite. Point the
    # already-loaded Alembic settings at this explicitly supplied database.
    settings.DATABASE_URL = DATABASE_URL
    engine = create_engine(DATABASE_URL)
    test_session_id = f"immutability-{uuid4().hex}"
    try:
        command.upgrade(_alembic_config(), "head")
        with engine.begin() as connection:
            _insert_audit_rows(connection, test_session_id)

        _assert_rejected(
            engine,
            f"UPDATE audit_log SET summary = 'rewritten' "
            f"WHERE session_id = '{test_session_id}'",
        )
        _assert_rejected(
            engine,
            f"DELETE FROM audit_log WHERE session_id = '{test_session_id}'",
        )
        _assert_rejected(
            engine,
            f"UPDATE transaction_audit_logs SET status = 'success' "
            f"WHERE session_id = '{test_session_id}'",
        )
        _assert_rejected(
            engine,
            f"DELETE FROM transaction_audit_logs WHERE session_id = '{test_session_id}'",
        )
        _assert_rejected(engine, "TRUNCATE audit_log")
        _assert_rejected(engine, "TRUNCATE transaction_audit_logs")

        with engine.connect() as connection:
            assert connection.execute(
                text(f"SELECT count(*) FROM audit_log WHERE session_id = '{test_session_id}'")
            ).scalar_one() == 1
            assert connection.execute(
                text(
                    "SELECT count(*) FROM transaction_audit_logs "
                    f"WHERE session_id = '{test_session_id}'"
                )
            ).scalar_one() == 1
    finally:
        engine.dispose()


def test_audit_immutability_migration_cannot_be_downgraded():
    """A normal Alembic rollback cannot silently remove the history guard."""
    from importlib.util import module_from_spec, spec_from_file_location

    path = Path(__file__).resolve().parents[1] / "migrations/versions/20260905_02_audit_immutability.py"
    spec = spec_from_file_location("audit_immutability_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    with pytest.raises(RuntimeError, match="forward-only"):
        migration.downgrade()