"""create vault read tables

Revision ID: 20260228_0001
Revises:
Create Date: 2026-02-28 08:40:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260228_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vaults",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("address", sa.String(length=64), nullable=False),
        sa.Column("created_block_number", sa.BigInteger(), nullable=True),
        sa.Column("created_tx_hash", sa.String(length=80), nullable=True),
        sa.Column("created_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("chain_id", "address", name="uq_vault_chain_address"),
    )
    op.create_index("ix_vaults_chain_id", "vaults", ["chain_id"])
    op.create_index("ix_vaults_address", "vaults", ["address"])

    op.create_table(
        "vault_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("vault_address", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("block_number", sa.BigInteger(), nullable=False),
        sa.Column("tx_hash", sa.String(length=80), nullable=False),
        sa.Column("log_index", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("chain_id", "tx_hash", "log_index", name="uq_chain_tx_log"),
    )
    op.create_index("ix_vault_events_chain_id", "vault_events", ["chain_id"])
    op.create_index("ix_vault_events_vault_address", "vault_events", ["vault_address"])
    op.create_index("ix_vault_events_event_type", "vault_events", ["event_type"])
    op.create_index("ix_vault_events_block_number", "vault_events", ["block_number"])
    op.create_index("ix_vault_events_tx_hash", "vault_events", ["tx_hash"])
    op.create_index("ix_vault_events_log_index", "vault_events", ["log_index"])
    op.create_index("ix_vault_events_timestamp", "vault_events", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_vault_events_timestamp", table_name="vault_events")
    op.drop_index("ix_vault_events_log_index", table_name="vault_events")
    op.drop_index("ix_vault_events_tx_hash", table_name="vault_events")
    op.drop_index("ix_vault_events_block_number", table_name="vault_events")
    op.drop_index("ix_vault_events_event_type", table_name="vault_events")
    op.drop_index("ix_vault_events_vault_address", table_name="vault_events")
    op.drop_index("ix_vault_events_chain_id", table_name="vault_events")
    op.drop_table("vault_events")

    op.drop_index("ix_vaults_address", table_name="vaults")
    op.drop_index("ix_vaults_chain_id", table_name="vaults")
    op.drop_table("vaults")
