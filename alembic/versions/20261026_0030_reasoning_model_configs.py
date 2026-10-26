"""Add reasoning_model_configs table for configurable LLM reasoning models.

Revision ID: 20261026_0030
Revises: 20261019_0029
Create Date: 2026-10-26

"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261026_0030"
down_revision: str | None = "20261019_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INITIAL_MODELS = [
    {
        "name": "Claude 3.7 Sonnet (Reasoning)",
        "provider": "openrouter",
        "model": "anthropic/claude-3.7-sonnet",
        "description": "Anthropic hybrid reasoning model via OpenRouter",
        "is_default": True,
        "is_active": True,
    },
    {
        "name": "OpenAI o3-mini (Reasoning)",
        "provider": "openrouter",
        "model": "openai/o3-mini",
        "description": "OpenAI fast reasoning model via OpenRouter",
        "is_default": False,
        "is_active": True,
    },
    {
        "name": "DeepSeek R1 (Reasoning)",
        "provider": "openrouter",
        "model": "deepseek/deepseek-r1",
        "description": "DeepSeek R1 open-weights reasoning model",
        "is_default": False,
        "is_active": True,
    },
    {
        "name": "OpenRouter GPT-4o Mini",
        "provider": "openrouter",
        "model": "openai/gpt-4o-mini",
        "description": "Fast and economical planning model",
        "is_default": False,
        "is_active": True,
    },
    {
        "name": "OpenAI GPT-4o Mini (Direct)",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "description": "Fast direct OpenAI planning model",
        "is_default": False,
        "is_active": True,
    },
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "reasoning_model_configs" not in table_names:
        table = op.create_table(
            "reasoning_model_configs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("model", sa.String(length=160), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("api_key_encrypted", sa.String(length=4096), nullable=True),
            sa.Column("use_custom_api_key", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("price_input_per_mtok", sa.Float(), nullable=True),
            sa.Column("price_output_per_mtok", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("name", name="uq_reasoning_model_configs_name"),
        )
        now = datetime.now(UTC)
        seed_data = [
            {
                **m,
                "api_key_encrypted": None,
                "use_custom_api_key": False,
                "price_input_per_mtok": None,
                "price_output_per_mtok": None,
                "created_at": now,
                "updated_at": now,
            }
            for m in INITIAL_MODELS
        ]
        op.bulk_insert(table, seed_data)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "reasoning_model_configs" in table_names:
        op.drop_table("reasoning_model_configs")
