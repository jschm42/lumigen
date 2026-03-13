"""Add upscale_provider column to profiles.

Revision ID: 20260313_0018
Revises: 20260312_0017
Create Date: 2026-03-13

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260313_0018"
down_revision: Union[str, None] = "20260312_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("profiles")]
    if "upscale_provider" in columns:
        return

    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("upscale_provider", sa.String(length=32), nullable=True)
        )

    # Back-fill: any profile that already has an upscale_model set is using local provider.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE profiles SET upscale_provider = 'local'"
            " WHERE upscale_model IS NOT NULL AND upscale_model != ''"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("profiles")]
    if "upscale_provider" not in columns:
        return

    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.drop_column("upscale_provider")
