"""Protect both audit tables from UPDATE, DELETE, and TRUNCATE.

The application only appends to these tables, but database-level protection is
needed to keep an accidental administrator query from rewriting the financial
history.  PostgreSQL triggers are used instead of application hooks so the
guard applies to every connection that can reach the tables.
"""

from __future__ import annotations

from typing import Optional

from alembic import op
import sqlalchemy as sa

revision: str = "20260905_02"
down_revision: Optional[str] = "20260905_01"
branch_labels = None
depends_on = None

_AUDIT_TABLES = ("audit_log", "transaction_audit_logs")
_MUTATION_FUNCTION = "agentseva_reject_audit_mutation"


def _postgresql_only() -> bool:
    """Return whether the current migration target supports these triggers."""
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    """Install immutable-audit guards on PostgreSQL databases."""
    if not _postgresql_only():
        # SQLite remains useful for the unit-test fixtures.  The production
        # schema is PostgreSQL, where this migration installs the real guard.
        return

    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {_MUTATION_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            SECURITY DEFINER
            SET search_path = pg_catalog
            AS $$
            BEGIN
                RAISE EXCEPTION
                    'audit history is append-only: % on % is not permitted',
                    TG_OP, TG_TABLE_NAME
                    USING ERRCODE = 'restrict_violation';
            END;
            $$;
            """
        )
    )

    for table_name in _AUDIT_TABLES:
        op.execute(
            sa.text(
                f"""
                REVOKE UPDATE, DELETE, TRUNCATE ON TABLE {table_name} FROM PUBLIC;

                CREATE TRIGGER {table_name}_append_only
                BEFORE UPDATE OR DELETE ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION {_MUTATION_FUNCTION}();

                CREATE TRIGGER {table_name}_no_truncate
                BEFORE TRUNCATE ON {table_name}
                FOR EACH STATEMENT
                EXECUTE FUNCTION {_MUTATION_FUNCTION}();

                ALTER TABLE {table_name}
                    ENABLE ALWAYS TRIGGER {table_name}_append_only;
                ALTER TABLE {table_name}
                    ENABLE ALWAYS TRIGGER {table_name}_no_truncate;
                """
            )
        )


def downgrade() -> None:
    """Refuse to remove audit protections through a normal schema rollback.

    Audit history must not become mutable merely because application code is
    rolled back.  A database restore to an isolated environment is the
    supported recovery path; see README.md.
    """
    raise RuntimeError(
        "Audit immutability is forward-only; restore a database backup in an "
        "isolated environment instead of removing the protection"
    )