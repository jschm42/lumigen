"""model configs

Revision ID: 20260210_0005
Revises: 20260210_0004
Create Date: 2026-02-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260210_0005"
down_revision = "20260210_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("model_configs"):
        op.create_table(
            "model_configs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("model", sa.String(length=128), nullable=False),
            sa.Column("api_key_encrypted", sa.String(length=4096), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.UniqueConstraint("name"),
        )

    profiles_columns = {item["name"] for item in inspector.get_columns("profiles")}
    profiles_fks = {item.get("name") for item in inspector.get_foreign_keys("profiles")}

    with op.batch_alter_table("profiles", schema=None) as batch_op:
        if "model_config_id" not in profiles_columns:
            batch_op.add_column(
                sa.Column("model_config_id", sa.Integer(), nullable=True)
            )
        if "fk_profiles_model_config_id" not in profiles_fks:
            batch_op.create_foreign_key(
                "fk_profiles_model_config_id",
                "model_configs",
                ["model_config_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if inspector.has_table("provider_configs"):
        op.drop_table("provider_configs")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("provider_configs"):
        op.create_table(
            "provider_configs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("models_json", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("api_key_encrypted", sa.String(length=4096), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.UniqueConstraint("provider"),
        )

    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.drop_constraint("fk_profiles_model_config_id", type_="foreignkey")
        batch_op.drop_column("model_config_id")

    if inspector.has_table("model_configs"):
        op.drop_table("model_configs")
