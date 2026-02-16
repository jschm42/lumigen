"""limit profile and model config names to 50

Revision ID: 20260216_0011
Revises: 20260216_0010
Create Date: 2026-02-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260216_0011"
down_revision = "20260216_0010"
branch_labels = None
depends_on = None

MAX_NAME_LENGTH = 50


def _normalize_name(raw_name: str | None, row_id: int, used: set[str], prefix: str) -> str:
    base = (raw_name or "").strip()
    if not base:
        base = f"{prefix}-{row_id}"
    base = base[:MAX_NAME_LENGTH].strip()
    if not base:
        base = f"{prefix}-{row_id}"[:MAX_NAME_LENGTH]

    candidate = base
    if candidate not in used:
        return candidate

    suffix = f"-{row_id}"
    room = max(1, MAX_NAME_LENGTH - len(suffix))
    candidate = f"{base[:room]}{suffix}"
    counter = 2
    while candidate in used:
        counter_suffix = f"-{row_id}-{counter}"
        room = max(1, MAX_NAME_LENGTH - len(counter_suffix))
        candidate = f"{base[:room]}{counter_suffix}"
        counter += 1
    return candidate


def _normalize_table_names(bind: sa.Connection, table_name: str, prefix: str) -> None:
    rows = bind.execute(
        sa.text(f"SELECT id, name FROM {table_name} ORDER BY id ASC")
    ).fetchall()
    used: set[str] = set()
    updates: list[tuple[str, int]] = []

    for row_id, name in rows:
        normalized = _normalize_name(name, int(row_id), used, prefix)
        used.add(normalized)
        if normalized != (name or ""):
            updates.append((normalized, int(row_id)))

    for normalized, row_id in updates:
        bind.execute(
            sa.text(f"UPDATE {table_name} SET name = :name WHERE id = :id"),
            {"name": normalized, "id": row_id},
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("profiles"):
        _normalize_table_names(bind, "profiles", "Profile")
        with op.batch_alter_table("profiles", schema=None) as batch_op:
            batch_op.alter_column(
                "name",
                existing_type=sa.String(length=120),
                type_=sa.String(length=50),
                existing_nullable=False,
            )

    if inspector.has_table("model_configs"):
        _normalize_table_names(bind, "model_configs", "Model")
        with op.batch_alter_table("model_configs", schema=None) as batch_op:
            batch_op.alter_column(
                "name",
                existing_type=sa.String(length=120),
                type_=sa.String(length=50),
                existing_nullable=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("profiles"):
        with op.batch_alter_table("profiles", schema=None) as batch_op:
            batch_op.alter_column(
                "name",
                existing_type=sa.String(length=50),
                type_=sa.String(length=120),
                existing_nullable=False,
            )

    if inspector.has_table("model_configs"):
        with op.batch_alter_table("model_configs", schema=None) as batch_op:
            batch_op.alter_column(
                "name",
                existing_type=sa.String(length=50),
                type_=sa.String(length=120),
                existing_nullable=False,
            )
