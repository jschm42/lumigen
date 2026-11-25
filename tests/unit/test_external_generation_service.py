"""Unit tests for resolving external references in ExternalGenerationService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.services.external_generation_service import (
    ExternalGenerationError,
    ExternalGenerationService,
    ExternalImageRequest,
)


@pytest.fixture
def db(app_module):
    """Yield a session on the reloaded test database (the app lifespan creates the schema)."""
    with TestClient(app_module.app), app_module.SessionLocal() as session:
        yield session


@pytest.fixture
def service():
    return ExternalGenerationService(MagicMock())


def _add_model(db, name: str, model: str, provider: str = "stub"):
    from app.db.models import ModelConfig

    cfg = ModelConfig(name=name, provider=provider, model=model)
    db.add(cfg)
    db.commit()
    return cfg


def test_resolve_model_by_id_name_and_identifier(db, service):
    cfg = _add_model(db, "Fast", "vendor/fast-1")
    assert service.resolve_model(db, cfg.id).id == cfg.id
    assert service.resolve_model(db, str(cfg.id)).id == cfg.id
    assert service.resolve_model(db, "FAST").id == cfg.id
    assert service.resolve_model(db, "vendor/fast-1").id == cfg.id


def test_resolve_model_rejects_ambiguous_identifier(db, service):
    _add_model(db, "Fast A", "vendor/fast-1")
    _add_model(db, "Fast B", "vendor/fast-1", provider="openrouter")
    with pytest.raises(ExternalGenerationError, match="ambiguous"):
        service.resolve_model(db, "vendor/fast-1")


def test_resolve_model_rejects_unknown(db, service):
    with pytest.raises(ExternalGenerationError, match="Unknown model"):
        service.resolve_model(db, "missing")


def test_resolve_categories_creates_missing_names_once(db, service):
    from app.db import crud

    existing = crud.create_category(db, name="Scenes")
    result = service.resolve_categories(
        db, ["scenes", "Portraits", "portraits", existing.id], create_missing=True
    )
    assert [cat.name for cat in result] == ["Scenes", "Portraits"]


def test_resolve_categories_without_create(db, service):
    with pytest.raises(ExternalGenerationError, match="Unknown category"):
        service.resolve_categories(db, ["Nope"], create_missing=False)


def test_resolve_categories_rejects_unknown_id_and_long_name(db, service):
    with pytest.raises(ExternalGenerationError, match="Unknown category '999'"):
        service.resolve_categories(db, [999], create_missing=True)
    with pytest.raises(ExternalGenerationError, match="longer than"):
        service.resolve_categories(db, ["x" * 31], create_missing=True)


def test_create_job_uses_profile_by_name_and_model_override(db, service):
    from app.db import crud

    cfg = _add_model(db, "Override", "stub-override")
    template = crud.list_storage_templates(db)[0]
    profile = crud.create_profile(
        db, name="Story Scenes", aspect_ratio="16:9", storage_template_id=template.id
    )
    service.generation_service.create_generation_from_profile.return_value = MagicMock(id=7)

    service.create_job(
        db,
        ExternalImageRequest(prompt="A dragon", model="Override", profile="story scenes", n_images=20),
    )

    args, kwargs = service.generation_service.create_generation_from_profile.call_args
    assert args[1].id == profile.id
    assert args[2] == "A dragon"
    overrides = kwargs["overrides"]
    assert overrides["model_config_id"] == cfg.id
    assert overrides["aspect_ratio"] == "16:9"
    assert overrides["n_images"] == 8
    assert overrides["chat_session_id"].startswith("session:")


def test_create_job_requires_prompt(db, service):
    with pytest.raises(ExternalGenerationError, match="Prompt is required"):
        service.create_job(db, ExternalImageRequest(prompt="   "))


def test_resolve_session_creates_and_reuses_by_name(db, service):
    from app.db import crud

    template = crud.list_storage_templates(db)[0]
    profile = crud.create_profile(db, name="P", storage_template_id=template.id)
    created = service.resolve_session(db, "My Story", prompt="x", profile=profile, model_cfg=None)
    reused = service.resolve_session(db, " my story ", prompt="y", profile=profile, model_cfg=None)
    assert reused.chat_session_id == created.chat_session_id
    unnamed = service.resolve_session(db, None, prompt="A long prompt", profile=profile, model_cfg=None)
    assert unnamed.chat_session_id != created.chat_session_id
    assert unnamed.title == "A long prompt"
    with pytest.raises(ExternalGenerationError, match="longer than 200"):
        service.resolve_session(db, "x" * 201, prompt="x", profile=profile, model_cfg=None)
