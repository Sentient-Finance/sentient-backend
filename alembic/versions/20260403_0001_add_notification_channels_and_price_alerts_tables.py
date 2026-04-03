"""add notification_channels and price_alerts tables

Revision ID: 20260403_0001
Revises: 20260319_0001
Create Date: 2026-04-03

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260403_0001"
down_revision = "20260319_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # notification_channels table
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_wallet", sa.String(length=64), nullable=False),
        sa.Column("channel_type", sa.String(length=16), nullable=False),
        sa.Column("channel_id", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_channels_user_wallet",
        "notification_channels",
        ["user_wallet"],
    )

    # price_alerts table
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recipient_id", sa.String(length=64), nullable=False),
        sa.Column("channel_type", sa.String(length=16), nullable=False),
        sa.Column("vault_address", sa.String(length=64), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False, server_default="84532"),
        sa.Column("alert_type", sa.String(length=16), nullable=False),
        sa.Column("threshold_price", sa.Float(), nullable=False),
        sa.Column("action_type", sa.String(length=16), nullable=False, server_default="none"),
        sa.Column("action_config", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_price_alerts_recipient",
        "price_alerts",
        ["recipient_id", "channel_type"],
    )
    op.create_index(
        "ix_price_alerts_vault_active",
        "price_alerts",
        ["vault_address", "is_active"],
    )
    op.create_index(
        "ix_price_alerts_recipient_id",
        "price_alerts",
        ["recipient_id"],
    )
    op.create_index(
        "ix_price_alerts_vault_address",
        "price_alerts",
        ["vault_address"],
    )


def downgrade() -> None:
    op.drop_index("ix_price_alerts_vault_address", table_name="price_alerts")
    op.drop_index("ix_price_alerts_recipient_id", table_name="price_alerts")
    op.drop_index("ix_price_alerts_vault_active", table_name="price_alerts")
    op.drop_index("ix_price_alerts_recipient", table_name="price_alerts")
    op.drop_table("price_alerts")

    op.drop_index("ix_notification_channels_user_wallet", table_name="notification_channels")
    op.drop_table("notification_channels")
