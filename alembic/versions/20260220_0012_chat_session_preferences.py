"""chat_session_preferences

Revision ID: 20260220_0012
Revises: 20260216_0011
Create Date: 2026-02-20 08:38:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260220_0012'
down_revision = '20260216_0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chat_session_id', sa.String(length=64), nullable=False),
        sa.Column('last_profile_id', sa.Integer(), nullable=True),
        sa.Column('last_thumb_size', sa.String(length=10), nullable=False, server_default='md'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chat_session_id'),
        sa.ForeignKeyConstraint(['last_profile_id'], ['profiles.id'], ondelete='SET NULL'),
    )
    op.create_index(op.f('ix_chat_sessions_chat_session_id'), 'chat_sessions', ['chat_session_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_sessions_chat_session_id'), table_name='chat_sessions')
    op.drop_table('chat_sessions')
