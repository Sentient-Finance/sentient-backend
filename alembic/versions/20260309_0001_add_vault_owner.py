"""add vault owner

Revision ID: 20260309_0001
Revises: 20260228_0001
Create Date: 2026-03-09

"""

import sqlalchemy as sa

from alembic import op

revision = "20260309_0001"
down_revision = "20260228_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vaults", sa.Column("owner", sa.String(length=64), nullable=True))
    op.create_index("ix_vaults_owner", "vaults", ["owner"])


def downgrade() -> None:
    op.drop_index("ix_vaults_owner", table_name="vaults")
    op.drop_column("vaults", "owner")
