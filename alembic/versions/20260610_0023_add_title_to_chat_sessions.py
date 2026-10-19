"""add title to chat_sessions

Revision ID: 20260610_0023
Revises: 20260427_0022
Create Date: 2026-06-10 07:30:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260610_0023"
down_revision = "20260427_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "chat_sessions" not in inspector.get_table_names():
        return

    columns = {item["name"] for item in inspector.get_columns("chat_sessions")}
    if "title" not in columns:
        with op.batch_alter_table("chat_sessions", schema=None) as batch_op:
            batch_op.add_column(sa.Column("title", sa.String(length=200), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "chat_sessions" not in inspector.get_table_names():
        return

    columns = {item["name"] for item in inspector.get_columns("chat_sessions")}
    if "title" in columns:
        with op.batch_alter_table("chat_sessions", schema=None) as batch_op:
            batch_op.drop_column("title")
