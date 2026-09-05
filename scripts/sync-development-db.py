"""Apply versioned AgentSeva migrations and seed catalog to development only."""

from __future__ import annotations

import os
import sys
from pathlib import Path


INITIAL_REVISION = "20260905_01"


def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    if os.environ.get("REPLIT_DEPLOYMENT") == "1":
        raise SystemExit("Refusing to mutate schema from a production deployment")

    root = Path(__file__).resolve().parents[1]
    backend = root / "backend"
    sys.path.insert(0, str(backend))

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect
    from app import models  # noqa: F401
    from app.audit import logger as transaction_audit  # noqa: F401
    from app.db.base import Base, engine
    from app.engine import audit as engine_audit  # noqa: F401
    from app.services.catalog import seed_catalog_if_empty

    config = Config(str(backend / "alembic.ini"))
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    managed_tables = set(Base.metadata.tables)
    if "alembic_version" not in existing_tables and existing_tables & managed_tables:
        missing_tables = managed_tables - existing_tables
        mismatched_columns = []
        for table_name in managed_tables & existing_tables:
            expected = {column.name for column in Base.metadata.tables[table_name].columns}
            actual = {column["name"] for column in inspector.get_columns(table_name)}
            if expected != actual:
                mismatched_columns.append(table_name)
        if missing_tables or mismatched_columns:
            raise SystemExit(
                "Refusing to baseline a partial or mismatched schema. "
                f"Missing tables: {sorted(missing_tables)}; "
                f"column mismatches: {sorted(mismatched_columns)}"
            )
        # Baseline only the schema that already exists, then let Alembic run
        # every later migration (including audit protections) normally.
        command.stamp(config, INITIAL_REVISION)
        print("Adopted matching pre-Alembic development schema at the initial revision.")
    command.upgrade(config, "head")
    seed_catalog_if_empty()
    print("Development database schema and catalog are ready.")


if __name__ == "__main__":
    main()