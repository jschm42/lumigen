"""add default_enhancement_prompt to enhancement_configs

Revision ID: 20260427_0022
Revises: 20260404_0021
Create Date: 2026-04-27 21:32:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260427_0022'
down_revision = '20260404_0021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if column exists before adding it (idempotency)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # Add default_enhancement_prompt to enhancement_configs if missing
    columns = {item["name"] for item in inspector.get_columns("enhancement_configs")}
    if "default_enhancement_prompt" not in columns:
        with op.batch_alter_table("enhancement_configs", schema=None) as batch_op:
            batch_op.add_column(sa.Column("default_enhancement_prompt", sa.Text(), nullable=True))

    # Clean up indices that are no longer in the models
    asset_columns = {item["name"] for item in inspector.get_columns("assets")}
    if "assets" in inspector.get_table_names():
        indices = {item["name"] for item in inspector.get_indexes("assets")}
        if "ix_assets_created_at" in indices:
            op.drop_index("ix_assets_created_at", table_name="assets")

    if "generations" in inspector.get_table_names():
        indices = {item["name"] for item in inspector.get_indexes("generations")}
        if "ix_generations_profile_name" in indices:
            op.drop_index("ix_generations_profile_name", table_name="generations")
        if "ix_generations_provider" in indices:
            op.drop_index("ix_generations_provider", table_name="generations")
        if "ix_generations_status" in indices:
            op.drop_index("ix_generations_status", table_name="generations")


def downgrade() -> None:
    with op.batch_alter_table("enhancement_configs", schema=None) as batch_op:
        batch_op.drop_column("default_enhancement_prompt")
    
    # We don't necessarily want to recreate the indices in downgrade if they were unwanted cleanup
    op.create_index("ix_generations_status", "generations", ["status"], unique=False)
    op.create_index("ix_generations_provider", "generations", ["provider"], unique=False)
    op.create_index("ix_generations_profile_name", "generations", ["profile_name"], unique=False)
    op.create_index("ix_assets_created_at", "assets", ["created_at"], unique=False)
