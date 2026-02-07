"""initial schema

Revision ID: 20260207_0001
Revises:
Create Date: 2026-02-07 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260207_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "storage_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_dir", sa.String(length=1024), nullable=False),
        sa.Column("template", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("base_prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("aspect_ratio", sa.String(length=32), nullable=True),
        sa.Column("n_images", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("output_format", sa.String(length=16), nullable=False, server_default="png"),
        sa.Column("params_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("storage_template_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["storage_template_id"], ["storage_templates.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "generations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), nullable=True),
        sa.Column("profile_name", sa.String(length=120), nullable=False),
        sa.Column("prompt_user", sa.Text(), nullable=False),
        sa.Column("prompt_final", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("profile_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("storage_template_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("request_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("failure_sidecar_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_generations_profile_name", "generations", ["profile_name"])
    op.create_index("ix_generations_provider", "generations", ["provider"])
    op.create_index("ix_generations_status", "generations", ["status"])

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("generation_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("sidecar_path", sa.String(length=1024), nullable=False),
        sa.Column("thumbnail_path", sa.String(length=1024), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("mime", sa.String(length=64), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["generation_id"], ["generations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("file_path"),
    )
    op.create_index("ix_assets_created_at", "assets", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_assets_created_at", table_name="assets")
    op.drop_table("assets")

    op.drop_index("ix_generations_status", table_name="generations")
    op.drop_index("ix_generations_provider", table_name="generations")
    op.drop_index("ix_generations_profile_name", table_name="generations")
    op.drop_table("generations")

    op.drop_table("profiles")
    op.drop_table("storage_templates")
