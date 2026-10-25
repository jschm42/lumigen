"""Tests for video-provider visibility: media-type resolution and discovery APIs."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import admin as admin_api
from app.api import models as models_api
from app.config import get_settings
from app.db import crud
from app.db.models import Base
from app.providers.base import ProviderAdapter
from app.providers.fal_adapter import FalAdapter
from app.providers.registry import ProviderRegistry
from app.providers.seedance_adapter import SeedanceAdapter


@pytest.fixture
def db_session():
    """Provide an isolated in-memory SQLite database session."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )
    with session_factory() as session:
        yield session


def test_base_adapter_media_type_heuristic() -> None:
    assert ProviderAdapter.media_type_for_model("fal-ai/veo3") == "video"
    assert ProviderAdapter.media_type_for_model("fal-ai/kling-video/v1.5/pro") == "video"
    assert ProviderAdapter.media_type_for_model("fal-ai/ltx-video") == "video"
    assert ProviderAdapter.media_type_for_model("fal-ai/flux/schnell") == "image"
    assert ProviderAdapter.media_type_for_model("") == "image"


def test_fal_and_seedance_adapters_report_video_models() -> None:
    assert FalAdapter.media_type_for_model("fal-ai/luma-dream-machine") == "video"
    assert FalAdapter.media_type_for_model("fal-ai/nano-banana-2") == "image"
    # Seedance only ships video models, regardless of the identifier.
    assert SeedanceAdapter.media_type_for_model("seedance-1-0-pro-250528") == "video"


def test_registry_resolves_media_type_and_provider_capabilities() -> None:
    registry = ProviderRegistry(get_settings())

    assert registry.media_type_for("fal", "fal-ai/kling-video/v1.5/pro") == "video"
    assert registry.media_type_for("fal", "fal-ai/veo3/fast") == "video"
    assert registry.media_type_for("fal", "fal-ai/flux/dev") == "image"
    assert registry.media_type_for("seedance", "seedance-2-0-260128") == "video"
    assert registry.media_type_for("openai", "dall-e-3") == "image"
    # Unknown providers never raise; they degrade to image.
    assert registry.media_type_for("does-not-exist", "whatever") == "image"

    media_types = registry.provider_media_types()
    assert media_types["fal"] == ["image", "video"]
    assert media_types["seedance"] == ["video"]
    assert media_types["openai"] == ["image"]


def test_list_active_models_exposes_video_media_type(db_session: Session) -> None:
    crud.create_model_config(
        db_session, name="FAL Kling", provider="fal", model="fal-ai/kling-video/v1.5/pro"
    )
    crud.create_model_config(
        db_session, name="SEEDANCE Pro", provider="seedance", model="seedance-1-0-pro-250528"
    )
    crud.create_model_config(
        db_session, name="FLUX Schnell", provider="fal", model="fal-ai/flux/schnell"
    )

    rows = {row["name"]: row for row in models_api.list_active_models(session=db_session)}

    assert rows["FAL Kling"]["media_type"] == "video"
    assert rows["FAL Kling"]["capabilities"] == ["video"]
    assert rows["FAL Kling"]["supported_resolutions"] == ["720p", "1080p"]
    assert rows["SEEDANCE Pro"]["media_type"] == "video"
    assert rows["FLUX Schnell"]["media_type"] == "image"
    assert rows["FLUX Schnell"]["supported_resolutions"] == ["0.5K", "1K", "2K", "4K"]


async def test_discover_fal_models_lists_video_models(db_session: Session) -> None:
    """FAL.ai discovery must surface its video models, not just the image presets."""
    res = await admin_api.discover_provider_models("fal", session=db_session)

    assert res["count"] == len(res["models"])
    assert "fal-ai/kling-video/v1.5/pro" in res["models"]
    assert res["media_types"]["fal-ai/kling-video/v1.5/pro"] == "video"
    assert res["media_types"]["fal-ai/flux/schnell"] == "image"
    assert any("video" in model or "veo" in model for model in res["video_models"])


async def test_discover_seedance_models_are_all_video(db_session: Session) -> None:
    res = await admin_api.discover_provider_models("seedance", session=db_session)
    assert res["models"]
    assert set(res["media_types"].values()) == {"video"}
    assert len(res["video_models"]) == res["count"]


def test_admin_model_serialization_includes_media_type(db_session: Session) -> None:
    cfg = crud.create_model_config(
        db_session, name="FAL Veo", provider="fal", model="fal-ai/veo3"
    )
    payload = admin_api._serialize_model_config(cfg)
    assert payload["media_type"] == "video"
    assert payload["capabilities"] == ["video"]


def test_admin_providers_endpoint_marks_fal_as_video_provider(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Avoid touching provider key encryption in this test.
    monkeypatch.setattr(
        admin_api.model_config_service, "has_env_api_key", lambda provider: False
    )
    providers = {item["provider"]: item for item in admin_api.get_providers(session=db_session)}

    assert providers["fal"]["supports_video"] is True
    assert providers["fal"]["media_types"] == ["image", "video"]
    assert providers["seedance"]["supports_video"] is True
    assert providers["openai"]["supports_video"] is False
