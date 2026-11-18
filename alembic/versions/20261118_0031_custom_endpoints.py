"""Add custom provider endpoints (OpenAI-compatible APIs, ComfyUI) and link model configs.

Revision ID: 20261118_0031
Revises: 20261026_0030
Create Date: 2026-11-18

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20261118_0031"
down_revision = "20261026_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create custom_endpoints and add endpoint_id/provider_options to model_configs (idempotent)."""
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()

    if "custom_endpoints" not in tables:
        op.create_table(
            "custom_endpoints",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=80), nullable=False, unique=True),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("base_url", sa.String(length=512), nullable=False),
            sa.Column("api_key_encrypted", sa.String(length=4096), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "model_configs" not in tables:
        return
    existing = {col["name"] for col in inspector.get_columns("model_configs")}
    with op.batch_alter_table("model_configs", schema=None) as batch_op:
        if "endpoint_id" not in existing:
            batch_op.add_column(sa.Column("endpoint_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_model_configs_endpoint_id", ["endpoint_id"])
            batch_op.create_foreign_key(
                "fk_model_configs_endpoint_id",
                "custom_endpoints",
                ["endpoint_id"],
                ["id"],
                ondelete="RESTRICT",
            )
        if "provider_options" not in existing:
            batch_op.add_column(sa.Column("provider_options", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Drop the endpoint link columns and the custom_endpoints table."""
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()
    if "model_configs" in tables:
        existing = {col["name"] for col in inspector.get_columns("model_configs")}
        with op.batch_alter_table("model_configs", schema=None) as batch_op:
            if "endpoint_id" in existing:
                batch_op.drop_constraint("fk_model_configs_endpoint_id", type_="foreignkey")
                batch_op.drop_index("ix_model_configs_endpoint_id")
                batch_op.drop_column("endpoint_id")
            if "provider_options" in existing:
                batch_op.drop_column("provider_options")
    if "custom_endpoints" in tables:
        op.drop_table("custom_endpoints")
