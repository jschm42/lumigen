"""categories replace gallery folders

Revision ID: 20260216_0009
Revises: 20260216_0008
Create Date: 2026-02-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260216_0009"
down_revision = "20260216_0008"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("categories"):
        op.create_table(
            "categories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=120), nullable=False),
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
            sa.UniqueConstraint("name"),
        )

    if not inspector.has_table("profile_categories"):
        op.create_table(
            "profile_categories",
            sa.Column("profile_id", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["profile_id"], ["profiles.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["category_id"], ["categories.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("profile_id", "category_id"),
        )
    inspector = sa.inspect(bind)
    profile_cat_indexes = {
        item["name"] for item in inspector.get_indexes("profile_categories")
    }
    if "ix_profile_categories_category_id" not in profile_cat_indexes:
        op.create_index(
            "ix_profile_categories_category_id",
            "profile_categories",
            ["category_id"],
            unique=False,
        )

    if not inspector.has_table("asset_categories"):
        op.create_table(
            "asset_categories",
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["category_id"], ["categories.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("asset_id", "category_id"),
        )
    inspector = sa.inspect(bind)
    asset_cat_indexes = {item["name"] for item in inspector.get_indexes("asset_categories")}
    if "ix_asset_categories_category_id" not in asset_cat_indexes:
        op.create_index(
            "ix_asset_categories_category_id",
            "asset_categories",
            ["category_id"],
            unique=False,
        )

    if inspector.has_table("gallery_folders") and _has_column(
        inspector, "assets", "gallery_folder_id"
    ):
        op.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO categories (name, created_at, updated_at)
                SELECT DISTINCT path, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                FROM gallery_folders
                WHERE TRIM(COALESCE(path, '')) <> ''
                """
            )
        )
        op.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO asset_categories (asset_id, category_id)
                SELECT assets.id, categories.id
                FROM assets
                JOIN gallery_folders
                    ON gallery_folders.id = assets.gallery_folder_id
                JOIN categories
                    ON categories.name = gallery_folders.path
                WHERE assets.gallery_folder_id IS NOT NULL
                """
            )
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("assets"):
        assets_columns = {item["name"] for item in inspector.get_columns("assets")}
        assets_indexes = {item["name"] for item in inspector.get_indexes("assets")}
        assets_fks = inspector.get_foreign_keys("assets")
        fk_names = {item.get("name") for item in assets_fks}
        fk_gallery = next(
            (
                item.get("name")
                for item in assets_fks
                if item.get("constrained_columns") == ["gallery_folder_id"]
            ),
            None,
        )

        with op.batch_alter_table("assets", schema=None) as batch_op:
            if fk_gallery and fk_gallery in fk_names:
                batch_op.drop_constraint(fk_gallery, type_="foreignkey")
            elif "fk_assets_gallery_folder_id" in fk_names:
                batch_op.drop_constraint("fk_assets_gallery_folder_id", type_="foreignkey")
            if "ix_assets_gallery_folder_id" in assets_indexes:
                batch_op.drop_index("ix_assets_gallery_folder_id")
            if "gallery_folder_id" in assets_columns:
                batch_op.drop_column("gallery_folder_id")

    inspector = sa.inspect(bind)
    if inspector.has_table("gallery_folders"):
        op.drop_table("gallery_folders")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("gallery_folders"):
        op.create_table(
            "gallery_folders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("path", sa.String(length=512), nullable=False),
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
            sa.UniqueConstraint("path"),
        )

    inspector = sa.inspect(bind)
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

    if inspector.has_table("categories"):
        op.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO gallery_folders (path, created_at, updated_at)
                SELECT name, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                FROM categories
                WHERE TRIM(COALESCE(name, '')) <> ''
                """
            )
        )

    if inspector.has_table("asset_categories") and inspector.has_table("categories"):
        op.execute(
            sa.text(
                """
                UPDATE assets
                SET gallery_folder_id = (
                    SELECT gallery_folders.id
                    FROM asset_categories
                    JOIN categories ON categories.id = asset_categories.category_id
                    JOIN gallery_folders ON gallery_folders.path = categories.name
                    WHERE asset_categories.asset_id = assets.id
                    ORDER BY categories.id ASC
                    LIMIT 1
                )
                WHERE EXISTS (
                    SELECT 1
                    FROM asset_categories
                    WHERE asset_categories.asset_id = assets.id
                )
                """
            )
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("asset_categories"):
        op.drop_table("asset_categories")
    if inspector.has_table("profile_categories"):
        op.drop_table("profile_categories")
    if inspector.has_table("categories"):
        op.drop_table("categories")
