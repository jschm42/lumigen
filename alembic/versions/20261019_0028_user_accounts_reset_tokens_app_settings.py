"""Add user account fields, password reset tokens and app settings.

Revision ID: 20261019_0028
Revises: 20260918_0027
Create Date: 2026-10-19

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20261019_0028"
down_revision = "20260918_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add email/display_name/last_login_at/session_version to users and create new tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "users" in table_names:
        columns = {col["name"] for col in inspector.get_columns("users")}
        with op.batch_alter_table("users", schema=None) as batch_op:
            if "email" not in columns:
                batch_op.add_column(sa.Column("email", sa.String(length=254), nullable=True))
                batch_op.create_unique_constraint("uq_users_email", ["email"])
            if "display_name" not in columns:
                batch_op.add_column(sa.Column("display_name", sa.String(length=80), nullable=True))
            if "last_login_at" not in columns:
                batch_op.add_column(
                    sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True)
                )
            if "session_version" not in columns:
                batch_op.add_column(
                    sa.Column(
                        "session_version",
                        sa.Integer(),
                        nullable=False,
                        server_default="0",
                    )
                )

    if "password_reset_tokens" not in table_names:
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
        op.create_index(
            "ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"]
        )

    if "app_settings" not in table_names:
        op.create_table(
            "app_settings",
            sa.Column("key", sa.String(length=64), nullable=False),
            sa.Column("value_json", sa.JSON(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("key"),
        )


def downgrade() -> None:
    """Drop the new tables and user columns."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "app_settings" in table_names:
        op.drop_table("app_settings")
    if "password_reset_tokens" in table_names:
        op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
        op.drop_table("password_reset_tokens")
    if "users" in table_names:
        columns = {col["name"] for col in inspector.get_columns("users")}
        with op.batch_alter_table("users", schema=None) as batch_op:
            if "email" in columns:
                batch_op.drop_constraint("uq_users_email", type_="unique")
                batch_op.drop_column("email")
            for name in ("display_name", "last_login_at", "session_version"):
                if name in columns:
                    batch_op.drop_column(name)
