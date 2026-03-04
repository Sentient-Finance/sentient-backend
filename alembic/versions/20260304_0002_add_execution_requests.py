"""add execution_requests table

Revision ID: 20260304_0002
Revises: 20260228_0001
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260304_0002"
down_revision = "20260228_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("vault_address", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("tx_hash", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_execution_requests_chain_id", "execution_requests", ["chain_id"])
    op.create_index("ix_execution_requests_vault_address", "execution_requests", ["vault_address"])
    op.create_index("ix_execution_requests_action", "execution_requests", ["action"])
    op.create_index("ix_execution_requests_status", "execution_requests", ["status"])
    op.create_index("ix_execution_requests_created_at", "execution_requests", ["created_at"])
    op.create_unique_constraint("uq_execution_idempotency_key", "execution_requests", ["idempotency_key"])


def downgrade() -> None:
    op.drop_constraint("uq_execution_idempotency_key", "execution_requests", type_="unique")
    op.drop_index("ix_execution_requests_created_at", table_name="execution_requests")
    op.drop_index("ix_execution_requests_status", table_name="execution_requests")
    op.drop_index("ix_execution_requests_action", table_name="execution_requests")
    op.drop_index("ix_execution_requests_vault_address", table_name="execution_requests")
    op.drop_index("ix_execution_requests_chain_id", table_name="execution_requests")
    op.drop_table("execution_requests")
