"""expand prediction model_source length

Revision ID: 20260407_0005
Revises: 20260407_0004
Create Date: 2026-04-07 19:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260407_0005"
down_revision = "20260407_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "predictions",
        "model_source",
        schema="monitoring",
        existing_type=sa.String(length=120),
        type_=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "predictions",
        "model_source",
        schema="monitoring",
        existing_type=sa.String(length=255),
        type_=sa.String(length=120),
        existing_nullable=False,
    )
