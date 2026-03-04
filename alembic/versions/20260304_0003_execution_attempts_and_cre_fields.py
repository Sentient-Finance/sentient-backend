"""add execution_attempts table and CRE fields

Revision ID: 20260304_0003
Revises: 20260304_0002
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260304_0003"
down_revision = "20260304_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_requests",
        sa.Column("external_execution_id", sa.String(length=120), nullable=True),
    )

    op.create_table(
        "execution_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("execution_request_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["execution_request_id"], ["execution_requests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("execution_request_id", "attempt_number", name="uq_execution_attempt_number"),
    )
    op.create_index("ix_execution_attempts_execution_request_id", "execution_attempts", ["execution_request_id"])
    op.create_index("ix_execution_attempts_created_at", "execution_attempts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_execution_attempts_created_at", table_name="execution_attempts")
    op.drop_index("ix_execution_attempts_execution_request_id", table_name="execution_attempts")
    op.drop_table("execution_attempts")
    op.drop_column("execution_requests", "external_execution_id")
