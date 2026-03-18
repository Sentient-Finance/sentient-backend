"""add execution_logs table and vault_event indexes

Revision ID: 20260319_0001
Revises: 20260309_0001
Create Date: 2026-03-19

"""

import sqlalchemy as sa

from alembic import op

revision = "20260319_0001"
down_revision = "20260309_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vault_address", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("tx_hash", sa.String(length=80), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("trigger_reason", sa.String(length=200), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execution_logs_vault_address", "execution_logs", ["vault_address"])
    op.create_index("ix_execution_logs_executed_at", "execution_logs", ["executed_at"])
    op.create_index(
        "ix_execution_logs_vault_at", "execution_logs", ["vault_address", "executed_at"]
    )

    # Indexes added to models.py in feat(db) commit — apply them here
    op.create_index(
        "ix_vault_events_chain_vault", "vault_events", ["chain_id", "vault_address"]
    )
    op.create_index(
        "ix_vault_events_vault_block",
        "vault_events",
        ["vault_address", "block_number", "log_index"],
    )


def downgrade() -> None:
    op.drop_index("ix_vault_events_vault_block", table_name="vault_events")
    op.drop_index("ix_vault_events_chain_vault", table_name="vault_events")
    op.drop_index("ix_execution_logs_vault_at", table_name="execution_logs")
    op.drop_index("ix_execution_logs_executed_at", table_name="execution_logs")
    op.drop_index("ix_execution_logs_vault_address", table_name="execution_logs")
    op.drop_table("execution_logs")
