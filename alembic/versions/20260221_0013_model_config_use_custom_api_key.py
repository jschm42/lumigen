"""Add use_custom_api_key to model_configs.

Revision ID: 20260221_0013
Revises: 20260220_0012_chat_session_preferences
Create Date: 2026-02-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260221_0013'
down_revision: Union[str, None] = '20260216_0011_profile_and_model_name_length_50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'model_configs',
        sa.Column('use_custom_api_key', sa.Boolean(), nullable=False, server_default='0')
    )


def downgrade() -> None:
    op.drop_column('model_configs', 'use_custom_api_key')
