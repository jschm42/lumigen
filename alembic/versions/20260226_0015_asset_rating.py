"""Add optional rating field to assets.

Revision ID: 20260226_0015
Revises: 20260225_0014
Create Date: 2026-02-26

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260226_0015"
down_revision: Union[str, None] = "20260225_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("rating", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "rating")
