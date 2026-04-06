"""Add user_notification_channels table.

Revision ID: 20260406_0001
Revises: 20260319_0001
Create Date: 2026-04-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260406_0001"
down_revision: Union[str, None] = "20260319_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_notification_channels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_wallet", sa.String(64), nullable=False, index=True),
        sa.Column("channel_type", sa.String(32), nullable=False),
        sa.Column("channel_id", sa.String(128), nullable=True),
        sa.Column(
            "connect_token", sa.String(64), nullable=True, unique=True, index=True
        ),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_user_notification_channels_user_wallet",
        "user_notification_channels",
        ["user_wallet"],
    )
    op.create_index(
        "ix_user_notification_channels_connect_token",
        "user_notification_channels",
        ["connect_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("user_notification_channels")
