"""limit category name length to 30

Revision ID: 20260216_0010
Revises: 20260216_0009
Create Date: 2026-02-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260216_0010"
down_revision = "20260216_0009"
branch_labels = None
depends_on = None

MAX_CATEGORY_NAME_LENGTH = 30


def _normalize_name(raw_name: str | None, row_id: int, used: set[str]) -> str:
    base = (raw_name or "").strip()
    if not base:
        base = f"Category-{row_id}"
    base = base[:MAX_CATEGORY_NAME_LENGTH].strip()
    if not base:
        base = f"Category-{row_id}"[:MAX_CATEGORY_NAME_LENGTH]

    candidate = base
    if candidate not in used:
        return candidate

    suffix = f"-{row_id}"
    room = max(1, MAX_CATEGORY_NAME_LENGTH - len(suffix))
    candidate = f"{base[:room]}{suffix}"
    counter = 2
    while candidate in used:
        counter_suffix = f"-{row_id}-{counter}"
        room = max(1, MAX_CATEGORY_NAME_LENGTH - len(counter_suffix))
        candidate = f"{base[:room]}{counter_suffix}"
        counter += 1
    return candidate


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("categories"):
        return

    rows = bind.execute(
        sa.text("SELECT id, name FROM categories ORDER BY id ASC")
    ).fetchall()
    used: set[str] = set()
    updates: list[tuple[str, int]] = []

    for row_id, name in rows:
        normalized = _normalize_name(name, int(row_id), used)
        used.add(normalized)
        if normalized != (name or ""):
            updates.append((normalized, int(row_id)))

    for normalized, row_id in updates:
        bind.execute(
            sa.text("UPDATE categories SET name = :name WHERE id = :id"),
            {"name": normalized, "id": row_id},
        )

    with op.batch_alter_table("categories", schema=None) as batch_op:
        batch_op.alter_column(
            "name",
            existing_type=sa.String(length=120),
            type_=sa.String(length=30),
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("categories"):
        return

    with op.batch_alter_table("categories", schema=None) as batch_op:
        batch_op.alter_column(
            "name",
            existing_type=sa.String(length=30),
            type_=sa.String(length=120),
            existing_nullable=False,
        )
