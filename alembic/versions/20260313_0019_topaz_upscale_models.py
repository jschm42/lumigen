"""Add Topaz upscale model configurations.

Revision ID: 20260313_0019
Revises: 20260313_0018
Create Date: 2026-03-13

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260313_0019"
down_revision: Union[str, None] = "20260313_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "topaz_upscale_models" not in table_names:
        op.create_table(
            "topaz_upscale_models",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("model_identifier", sa.String(length=160), nullable=False),
            sa.Column("params_json", sa.JSON(), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("name", name="uq_topaz_upscale_models_name"),
        )

    profile_columns = {col["name"] for col in inspector.get_columns("profiles")}
    if "upscale_topaz_model_id" not in profile_columns:
        with op.batch_alter_table("profiles", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "upscale_topaz_model_id",
                    sa.Integer(),
                    nullable=True,
                )
            )
            batch_op.create_foreign_key(
                "fk_profiles_upscale_topaz_model_id_topaz_upscale_models",
                "topaz_upscale_models",
                ["upscale_topaz_model_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    profile_columns = {col["name"] for col in inspector.get_columns("profiles")}
    if "upscale_topaz_model_id" in profile_columns:
        with op.batch_alter_table("profiles", schema=None) as batch_op:
            batch_op.drop_constraint(
                "fk_profiles_upscale_topaz_model_id_topaz_upscale_models",
                type_="foreignkey",
            )
            batch_op.drop_column("upscale_topaz_model_id")

    table_names = set(inspector.get_table_names())
    if "topaz_upscale_models" in table_names:
        op.drop_table("topaz_upscale_models")
