"""Add reasoning_model_configs table for configurable LLM reasoning models.

Revision ID: 20261026_0030
Revises: 20261019_0029
Create Date: 2026-10-26

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261026_0030"
down_revision: str | None = "20261019_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "reasoning_model_configs" not in table_names:
        op.create_table(
            "reasoning_model_configs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("model", sa.String(length=160), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("api_key_encrypted", sa.String(length=4096), nullable=True),
            sa.Column("use_custom_api_key", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("price_input_per_mtok", sa.Float(), nullable=True),
            sa.Column("price_output_per_mtok", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("name", name="uq_reasoning_model_configs_name"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "reasoning_model_configs" in table_names:
        op.drop_table("reasoning_model_configs")
