"""gallery folders and asset folder assignments

Revision ID: 20260207_0002
Revises: 20260207_0001
Create Date: 2026-02-07 20:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260207_0002"
down_revision = "20260207_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("gallery_folders"):
        op.create_table(
            "gallery_folders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("path", sa.String(length=512), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.UniqueConstraint("path"),
        )

    assets_columns = {item["name"] for item in inspector.get_columns("assets")}
    assets_indexes = {item["name"] for item in inspector.get_indexes("assets")}
    assets_fks = {item.get("name") for item in inspector.get_foreign_keys("assets")}

    with op.batch_alter_table("assets", schema=None) as batch_op:
        if "gallery_folder_id" not in assets_columns:
            batch_op.add_column(sa.Column("gallery_folder_id", sa.Integer(), nullable=True))
        if "ix_assets_gallery_folder_id" not in assets_indexes:
            batch_op.create_index("ix_assets_gallery_folder_id", ["gallery_folder_id"], unique=False)
        if "fk_assets_gallery_folder_id" not in assets_fks:
            batch_op.create_foreign_key(
                "fk_assets_gallery_folder_id",
                "gallery_folders",
                ["gallery_folder_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.drop_constraint("fk_assets_gallery_folder_id", type_="foreignkey")
        batch_op.drop_index("ix_assets_gallery_folder_id")
        batch_op.drop_column("gallery_folder_id")

    op.drop_table("gallery_folders")
