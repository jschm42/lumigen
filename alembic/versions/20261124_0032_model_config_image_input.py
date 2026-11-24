"""Add the optional image-input capability override to model configurations.

Revision ID: 20261124_0032
Revises: 20261118_0031
Create Date: 2026-11-24

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20261124_0032"
down_revision = "20261118_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable supports_image_input to model_configs (idempotent)."""
    inspector = sa.inspect(op.get_bind())
    if "model_configs" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("model_configs")}
    if "supports_image_input" in existing:
        return
    with op.batch_alter_table("model_configs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("supports_image_input", sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Drop supports_image_input from model_configs."""
    inspector = sa.inspect(op.get_bind())
    if "model_configs" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("model_configs")}
    if "supports_image_input" not in existing:
        return
    with op.batch_alter_table("model_configs", schema=None) as batch_op:
        batch_op.drop_column("supports_image_input")
