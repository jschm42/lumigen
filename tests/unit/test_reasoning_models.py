from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import Settings
from app.db import crud
from app.db.engine import SessionLocal
from app.services.enhancement_service import EnhancementService


def test_crud_reasoning_models_lifecycle() -> None:
    with SessionLocal() as session:
        # Create model 1
        m1 = crud.create_reasoning_model_config(
            session,
            name="Test Model Alpha",
            provider="openrouter",
            model="openai/gpt-4o-mini",
            description="Alpha description",
            is_default=True,
            is_active=True,
        )
        assert m1.id is not None
        assert m1.is_default is True

        # Create model 2 as default -> model 1 should no longer be default
        m2 = crud.create_reasoning_model_config(
            session,
            name="Test Model Beta",
            provider="openai",
            model="o3-mini",
            description="Beta description",
            is_default=True,
            is_active=True,
        )
        session.refresh(m1)
        assert m2.is_default is True
        assert m1.is_default is False

        # Verify get_default
        default_model = crud.get_default_reasoning_model_config(session)
        assert default_model is not None
        assert default_model.id == m2.id

        # Update model 1
        crud.update_reasoning_model_config(
            session,
            m1,
            description="Updated description",
            is_default=True,
        )
        session.refresh(m2)
        assert m1.is_default is True
        assert m2.is_default is False

        # Cleanup
        crud.delete_reasoning_model_config(session, m1)
        crud.delete_reasoning_model_config(session, m2)


def test_enhancement_service_resolves_db_reasoning_model(monkeypatch: pytest.MonkeyPatch) -> None:
    with SessionLocal() as session:
        m = crud.create_reasoning_model_config(
            session,
            name="Test DeepSeek R1",
            provider="openrouter",
            model="deepseek/deepseek-r1",
            is_default=False,
            is_active=True,
        )
        model_id = m.id

    try:
        secrets = SimpleNamespace(
            get_default_api_key=lambda provider: "openrouter-test-key",
            decrypt_api_key=lambda tok: tok,
        )
        enhancement = EnhancementService(Settings(), secrets)

        # 1. Test listing
        models = enhancement.list_available_llm_models()
        assert any(x["name"] == "Test DeepSeek R1" for x in models)

        # 2. Test resolving by reasoning:<id>
        provider, model, key, _ = enhancement._resolve_llm(f"reasoning:{model_id}")
        assert provider == "openrouter"
        assert model == "deepseek/deepseek-r1"
        assert key == "openrouter-test-key"

        # 3. Test resolving by model identifier
        provider2, model2, key2, _ = enhancement._resolve_llm("deepseek/deepseek-r1")
        assert provider2 == "openrouter"
        assert model2 == "deepseek/deepseek-r1"
        assert key2 == "openrouter-test-key"
    finally:
        with SessionLocal() as session:
            row = crud.get_reasoning_model_config(session, model_id)
            if row:
                crud.delete_reasoning_model_config(session, row)
