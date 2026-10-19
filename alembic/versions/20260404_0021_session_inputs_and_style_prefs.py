"""Add session style prefs and session input images.

Revision ID: 20260404_0021
Revises: 20260404_0020
Create Date: 2026-04-04

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260404_0021"
down_revision: Union[str, None] = "20260404_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    chat_session_columns = {col["name"] for col in inspector.get_columns("chat_sessions")}
    if "selected_style_ids" not in chat_session_columns:
        with op.batch_alter_table("chat_sessions", schema=None) as batch_op:
            batch_op.add_column(sa.Column("selected_style_ids", sa.String(length=1024), nullable=True))

    table_names = set(inspector.get_table_names())
    if "session_input_images" not in table_names:
        op.create_table(
            "session_input_images",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("chat_session_id", sa.String(length=64), nullable=False),
            sa.Column("source_type", sa.String(length=16), nullable=False),
            sa.Column("sort_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("asset_id", sa.Integer(), nullable=True),
            sa.Column("original_file_path", sa.String(length=1024), nullable=True),
            sa.Column("thumbnail_file_path", sa.String(length=1024), nullable=True),
            sa.Column("file_name", sa.String(length=256), nullable=True),
            sa.Column("mime_type", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["chat_session_id"], ["chat_sessions.chat_session_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        )
        op.create_index(
            "ix_session_input_images_chat_session_id",
            "session_input_images",
            ["chat_session_id"],
            unique=False,
        )
        op.create_index(
            "ix_session_input_images_asset_id",
            "session_input_images",
            ["asset_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())
    if "session_input_images" in table_names:
        op.drop_index("ix_session_input_images_asset_id", table_name="session_input_images")
        op.drop_index("ix_session_input_images_chat_session_id", table_name="session_input_images")
        op.drop_table("session_input_images")

    chat_session_columns = {col["name"] for col in inspector.get_columns("chat_sessions")}
    if "selected_style_ids" in chat_session_columns:
        with op.batch_alter_table("chat_sessions", schema=None) as batch_op:
            batch_op.drop_column("selected_style_ids")
