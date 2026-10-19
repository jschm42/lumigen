"""add last_llm_model to chat_sessions

Revision ID: 20260828_0024
Revises: 20260610_0023
Create Date: 2026-08-28 08:16:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260828_0024"
down_revision = "20260610_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add last_llm_model column to chat_sessions table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "chat_sessions" not in inspector.get_table_names():
        return

    columns = {item["name"] for item in inspector.get_columns("chat_sessions")}
    if "last_llm_model" not in columns:
        with op.batch_alter_table("chat_sessions", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("last_llm_model", sa.String(length=128), nullable=True)
            )


def downgrade() -> None:
    """Drop last_llm_model column from chat_sessions table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "chat_sessions" not in inspector.get_table_names():
        return

    columns = {item["name"] for item in inspector.get_columns("chat_sessions")}
    if "last_llm_model" in columns:
        with op.batch_alter_table("chat_sessions", schema=None) as batch_op:
            batch_op.drop_column("last_llm_model")
