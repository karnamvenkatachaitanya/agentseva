"""One-time import of durable records from a legacy SQLite database."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy import func, insert, select

from app.audit.logger import TransactionAuditLog
from app.db.base import engine
from app.engine.audit import AuditLog
from app.models.order import Order

_TABLES = (
    (Order.__table__, True),
    (TransactionAuditLog.__table__, False),
    (AuditLog.__table__, False),
)


def _coerce_row(table: Any, row: dict[str, Any], preserve_id: bool) -> dict[str, Any]:
    values = dict(row)
    if not preserve_id:
        values.pop("id", None)
    for column in table.columns:
        value = values.get(column.name)
        if value is None:
            continue
        if column.name == "items" and isinstance(value, str):
            values[column.name] = json.loads(value)
        elif column.name in {"created_at", "timestamp"} and isinstance(value, str):
            values[column.name] = dt.datetime.fromisoformat(value)
    return values


def import_durable_records(source_path: Path) -> dict[str, int]:
    """Atomically copy orders and audit rows into the configured database.

    Order IDs are preserved and collisions abort the whole import. Audit IDs are
    regenerated because no application record references them; row order and all
    audit content remain intact.
    """
    if os.getenv("REPLIT_DEPLOYMENT") == "1":
        raise RuntimeError(
            "SQLite import is disabled in deployments; import into development before Publish."
        )
    if engine.dialect.name != "postgresql":
        raise RuntimeError("The import target must be managed PostgreSQL.")
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    imported: dict[str, int] = {}
    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        with engine.begin() as target:
            for table, preserve_id in _TABLES:
                exists = source.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table.name,),
                ).fetchone()
                if not exists:
                    imported[table.name] = 0
                    continue

                rows = [
                    _coerce_row(table, dict(row), preserve_id)
                    for row in source.execute(f'SELECT * FROM "{table.name}" ORDER BY id')
                ]
                if preserve_id and rows:
                    source_ids = [row["id"] for row in rows]
                    collision = target.execute(
                        select(table.c.id).where(table.c.id.in_(source_ids)).limit(1)
                    ).first()
                    if collision:
                        raise RuntimeError(
                            f"Cannot import {table.name}: target ID {collision.id} already exists."
                        )
                if rows:
                    target.execute(insert(table), rows)
                imported[table.name] = len(rows)
            if imported.get("orders"):
                target.execute(
                    select(
                        func.setval(
                            func.pg_get_serial_sequence("orders", "id"),
                            select(func.max(Order.id)).scalar_subquery(),
                            True,
                        )
                    )
                )
    finally:
        source.close()
    return imported


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import legacy SQLite orders and audit history into managed development PostgreSQL."
    )
    parser.add_argument("source", type=Path, help="Read-only snapshot of the legacy app.db")
    parser.add_argument(
        "--confirm-development-import",
        action="store_true",
        help="Required acknowledgement that DATABASE_URL is the workspace development database.",
    )
    args = parser.parse_args()
    if not args.confirm_development_import:
        parser.error("--confirm-development-import is required")

    imported = import_durable_records(args.source.resolve())
    print("SQLite import committed:")
    for table, count in imported.items():
        print(f"  {table}: {count} rows")


if __name__ == "__main__":
    main()