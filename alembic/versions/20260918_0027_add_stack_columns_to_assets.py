"""Add stack_id and stack_order to assets.

Revision ID: 20260918_0027
Revises: 20260917_0026
Create Date: 2026-09-18 17:10:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260918_0027"
down_revision = "20260917_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add stack_id and stack_order columns to assets table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "assets" in table_names:
        columns = {col["name"] for col in inspector.get_columns("assets")}
        with op.batch_alter_table("assets", schema=None) as batch_op:
            if "stack_id" not in columns:
                batch_op.add_column(
                    sa.Column(
                        "stack_id",
                        sa.String(64),
                        nullable=True,
                    )
                )
                batch_op.create_index(
                    "ix_assets_stack_id",
                    ["stack_id"],
                    unique=False,
                )
            if "stack_order" not in columns:
                batch_op.add_column(
                    sa.Column(
                        "stack_order",
                        sa.Integer(),
                        nullable=False,
                        server_default="0",
                    )
                )


def downgrade() -> None:
    """Remove stack_id and stack_order columns from assets table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "assets" in table_names:
        columns = {col["name"] for col in inspector.get_columns("assets")}
        indexes = {idx["name"] for idx in inspector.get_indexes("assets")}
        with op.batch_alter_table("assets", schema=None) as batch_op:
            if "ix_assets_stack_id" in indexes:
                batch_op.drop_index("ix_assets_stack_id")
            if "stack_order" in columns:
                batch_op.drop_column("stack_order")
            if "stack_id" in columns:
                batch_op.drop_column("stack_id")
