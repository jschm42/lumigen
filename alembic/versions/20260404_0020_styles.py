"""Add styles table for reusable prompt fragments.

Revision ID: 20260404_0020
Revises: 20260313_0019
Create Date: 2026-04-04

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260404_0020"
down_revision: Union[str, None] = "20260313_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "styles" not in table_names:
        op.create_table(
            "styles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=30), nullable=False),
            sa.Column("description", sa.String(length=120), nullable=False),
            sa.Column("prompt", sa.String(length=1000), nullable=False),
            sa.Column("image_path", sa.String(length=1024), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.UniqueConstraint("name", name="uq_styles_name"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "styles" in table_names:
        op.drop_table("styles")
