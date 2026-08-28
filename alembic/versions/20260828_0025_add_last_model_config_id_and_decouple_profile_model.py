"""add last_model_config_id to chat_sessions and decouple profile model

Revision ID: 20260828_0025
Revises: 20260828_0024
Create Date: 2026-08-28 10:10:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260828_0025"
down_revision = "20260828_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add last_model_config_id to chat_sessions and make profile provider/model nullable."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "chat_sessions" in inspector.get_table_names():
        columns = {item["name"] for item in inspector.get_columns("chat_sessions")}
        if "last_model_config_id" not in columns:
            with op.batch_alter_table("chat_sessions", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "last_model_config_id",
                        sa.Integer(),
                        nullable=True,
                    )
                )
                batch_op.create_foreign_key(
                    "fk_chat_sessions_last_model_config_id",
                    "model_configs",
                    ["last_model_config_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

    if "profiles" in inspector.get_table_names():
        with op.batch_alter_table("profiles", schema=None) as batch_op:
            batch_op.alter_column(
                "provider",
                existing_type=sa.String(length=64),
                nullable=True,
            )
            batch_op.alter_column(
                "model",
                existing_type=sa.String(length=128),
                nullable=True,
            )


def downgrade() -> None:
    """Revert last_model_config_id and restore profile provider/model nullability."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "chat_sessions" in inspector.get_table_names():
        columns = {item["name"] for item in inspector.get_columns("chat_sessions")}
        if "last_model_config_id" in columns:
            with op.batch_alter_table("chat_sessions", schema=None) as batch_op:
                batch_op.drop_column("last_model_config_id")

    if "profiles" in inspector.get_table_names():
        with op.batch_alter_table("profiles", schema=None) as batch_op:
            batch_op.alter_column(
                "provider",
                existing_type=sa.String(length=64),
                nullable=False,
            )
            batch_op.alter_column(
                "model",
                existing_type=sa.String(length=128),
                nullable=False,
            )
