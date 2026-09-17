"""Add is_default to topaz_upscale_models.

Revision ID: 20260917_0026
Revises: 20260828_0025
Create Date: 2026-09-17 17:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260917_0026"
down_revision = "20260828_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add is_default column to topaz_upscale_models."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "topaz_upscale_models" in table_names:
        columns = {col["name"] for col in inspector.get_columns("topaz_upscale_models")}
        if "is_default" not in columns:
            with op.batch_alter_table("topaz_upscale_models", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "is_default",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.false(),
                    )
                )


def downgrade() -> None:
    """Remove is_default column from topaz_upscale_models."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "topaz_upscale_models" in table_names:
        columns = {col["name"] for col in inspector.get_columns("topaz_upscale_models")}
        if "is_default" in columns:
            with op.batch_alter_table("topaz_upscale_models", schema=None) as batch_op:
                batch_op.drop_column("is_default")
