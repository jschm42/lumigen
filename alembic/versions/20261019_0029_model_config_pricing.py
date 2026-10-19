"""Add optional token/image pricing to model configurations.

Revision ID: 20261019_0029
Revises: 20261019_0028
Create Date: 2026-10-19

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20261019_0029"
down_revision = "20261019_0028"
branch_labels = None
depends_on = None

_COLUMNS = ("price_input_per_mtok", "price_output_per_mtok", "price_per_image")


def upgrade() -> None:
    """Add nullable price columns to model_configs (idempotent)."""
    inspector = sa.inspect(op.get_bind())
    if "model_configs" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("model_configs")}
    with op.batch_alter_table("model_configs", schema=None) as batch_op:
        for name in _COLUMNS:
            if name not in existing:
                batch_op.add_column(sa.Column(name, sa.Float(), nullable=True))


def downgrade() -> None:
    """Drop the price columns."""
    inspector = sa.inspect(op.get_bind())
    if "model_configs" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("model_configs")}
    with op.batch_alter_table("model_configs", schema=None) as batch_op:
        for name in _COLUMNS:
            if name in existing:
                batch_op.drop_column(name)
