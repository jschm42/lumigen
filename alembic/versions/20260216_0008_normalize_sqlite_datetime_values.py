"""normalize sqlite datetime values

Revision ID: 20260216_0008
Revises: 20260211_0007
Create Date: 2026-02-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260216_0008"
down_revision = "20260211_0007"
branch_labels = None
depends_on = None


_DATETIME_COLUMNS: tuple[tuple[str, str], ...] = (
    ("storage_templates", "created_at"),
    ("storage_templates", "updated_at"),
    ("profiles", "created_at"),
    ("profiles", "updated_at"),
    ("generations", "created_at"),
    ("generations", "finished_at"),
    ("assets", "created_at"),
    ("gallery_folders", "created_at"),
    ("gallery_folders", "updated_at"),
    ("model_configs", "created_at"),
    ("model_configs", "updated_at"),
    ("enhancement_configs", "created_at"),
    ("enhancement_configs", "updated_at"),
    ("dimension_presets", "created_at"),
    ("dimension_presets", "updated_at"),
)


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return

    inspector = sa.inspect(bind)

    for table_name, column_name in _DATETIME_COLUMNS:
        if not inspector.has_table(table_name):
            continue
        if not _has_column(inspector, table_name, column_name):
            continue

        op.execute(
            sa.text(
                f"""
                UPDATE "{table_name}"
                SET "{column_name}" = CASE
                    WHEN ABS(CAST("{column_name}" AS REAL)) >= 100000000000 THEN
                        strftime('%Y-%m-%d %H:%M:%f', CAST("{column_name}" AS REAL) / 1000.0, 'unixepoch')
                    ELSE
                        strftime('%Y-%m-%d %H:%M:%f', CAST("{column_name}" AS REAL), 'unixepoch')
                END
                WHERE "{column_name}" IS NOT NULL
                  AND typeof("{column_name}") IN ('integer', 'real')
                """
            )
        )


def downgrade() -> None:
    # Data normalization is not reversible.
    pass
