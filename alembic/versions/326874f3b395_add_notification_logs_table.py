"""add notification logs table

Revision ID: 326874f3b395
Revises: 20260406_0001
Create Date: 2026-04-12 20:10:08.766009

"""

from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "326874f3b395"
down_revision: Union[str, None] = "20260406_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_wallet", sa.String(length=64), nullable=False),
        sa.Column("channel_type", sa.String(length=32), nullable=False),
        sa.Column("channel_id", sa.String(length=128), nullable=True),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_logs_user_wallet",
        "notification_logs",
        ["user_wallet"],
        unique=False,
    )
    op.create_index(
        "ix_notification_logs_sent_at", "notification_logs", ["sent_at"], unique=False
    )
    op.create_index(
        "ix_notification_logs_wallet_at",
        "notification_logs",
        ["user_wallet", "sent_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("notification_logs")
