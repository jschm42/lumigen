"""Add dedicated upscale_model column to profiles.

Revision ID: 20260225_0014
Revises: 20260221_0013
Create Date: 2026-02-25

"""
from __future__ import annotations

import json
from typing import Any, Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260225_0014"
down_revision: Union[str, None] = "20260221_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        if isinstance(parsed, dict):
            return dict(parsed)
    return {}


def upgrade() -> None:
    op.add_column("profiles", sa.Column("upscale_model", sa.String(length=128), nullable=True))

    connection = op.get_bind()
    profiles = sa.table(
        "profiles",
        sa.column("id", sa.Integer),
        sa.column("params_json", sa.JSON),
        sa.column("upscale_model", sa.String(length=128)),
    )

    rows = connection.execute(sa.select(profiles.c.id, profiles.c.params_json)).all()
    for row in rows:
        params = _as_dict(row.params_json)
        raw_model = params.pop("upscale_model", None)
        model_value = str(raw_model or "").strip()
        updates: dict[str, Any] = {}
        if model_value:
            updates["upscale_model"] = model_value
        if "upscale_model" in _as_dict(row.params_json):
            updates["params_json"] = params
        if updates:
            connection.execute(
                sa.update(profiles)
                .where(profiles.c.id == row.id)
                .values(**updates)
            )


def downgrade() -> None:
    connection = op.get_bind()
    profiles = sa.table(
        "profiles",
        sa.column("id", sa.Integer),
        sa.column("params_json", sa.JSON),
        sa.column("upscale_model", sa.String(length=128)),
    )

    rows = connection.execute(
        sa.select(profiles.c.id, profiles.c.params_json, profiles.c.upscale_model)
    ).all()
    for row in rows:
        model_value = str(row.upscale_model or "").strip()
        if not model_value:
            continue
        params = _as_dict(row.params_json)
        params["upscale_model"] = model_value
        connection.execute(
            sa.update(profiles)
            .where(profiles.c.id == row.id)
            .values(params_json=params)
        )

    op.drop_column("profiles", "upscale_model")
