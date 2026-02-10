"""model enhancement prompt and enhancement config

Revision ID: 20260210_0006
Revises: 20260210_0005
Create Date: 2026-02-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260210_0006"
down_revision = "20260210_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    model_columns = {item["name"] for item in inspector.get_columns("model_configs")}
    with op.batch_alter_table("model_configs", schema=None) as batch_op:
        if "enhancement_prompt" not in model_columns:
            batch_op.add_column(
                sa.Column("enhancement_prompt", sa.Text(), nullable=True)
            )

    if not inspector.has_table("enhancement_configs"):
        op.create_table(
            "enhancement_configs",
            sa.Column("id", sa.Integer(), primary_key=True),
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
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("enhancement_configs"):
        op.drop_table("enhancement_configs")

    with op.batch_alter_table("model_configs", schema=None) as batch_op:
        batch_op.drop_column("enhancement_prompt")
