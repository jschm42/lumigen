"""Make profile base_prompt nullable.

Revision ID: 20260209_0003_profile_base_prompt_nullable
Revises: 20260207_0002
Create Date: 2026-02-09
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260209_0003_profile_base_prompt_nullable"
down_revision = "20260207_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.alter_column("base_prompt", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE profiles SET base_prompt = '' WHERE base_prompt IS NULL")
    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.alter_column("base_prompt", existing_type=sa.Text(), nullable=False)
