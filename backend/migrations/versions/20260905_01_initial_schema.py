"""Create AgentSeva commerce and append-only audit tables.

Revision ID: 20260905_01
Revises:
"""

from __future__ import annotations

from typing import Optional

from alembic import op
import sqlalchemy as sa

revision: str = "20260905_01"
down_revision: Optional[str] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_session_id", "audit_log", ["session_id"])

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price_inr", sa.Float(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("stock_quantity", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_name", "products", ["name"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_name", sa.String(length=120), nullable=False),
        sa.Column("customer_phone", sa.String(length=20), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("razorpay_order_id", sa.String(length=64), nullable=True),
        sa.Column("razorpay_payment_id", sa.String(length=64), nullable=True),
        sa.Column("razorpay_payment_link_id", sa.String(length=64), nullable=True),
        sa.Column("payment_link", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_razorpay_order_id", "orders", ["razorpay_order_id"])
    op.create_index(
        "ix_orders_razorpay_payment_link_id", "orders", ["razorpay_payment_link_id"]
    )
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "transaction_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("user_intent", sa.Text(), nullable=False),
        sa.Column("agent_reasoning", sa.Text(), nullable=False),
        sa.Column("tool_called", sa.String(length=128), nullable=False),
        sa.Column("payload_sent", sa.Text(), nullable=True),
        sa.Column("api_response", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transaction_audit_logs_session_id",
        "transaction_audit_logs",
        ["session_id"],
    )
    op.create_index(
        "ix_transaction_audit_logs_trace_id",
        "transaction_audit_logs",
        ["trace_id"],
    )


def downgrade() -> None:
    raise RuntimeError(
        "AgentSeva schema downgrades are disabled to protect orders and audit history"
    )