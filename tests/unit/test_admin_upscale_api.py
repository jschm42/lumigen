"""Unit tests for admin upscale models API and asset upscale endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import admin as admin_api
from app.api import assets as assets_api
from app.db import crud
from app.db.models import Asset, Base, Generation
from app.services.model_config_service import ModelConfigService


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


@pytest.mark.asyncio
async def test_discover_upscale_models_returns_presets(monkeypatch: pytest.MonkeyPatch):
    """Test discovering upscale models returns curated presets fallback."""
    with patch(
        "app.providers.fal_upscale_adapter.FalUpscaleService.discover_upscale_models",
        new_callable=AsyncMock,
        return_value=[
            {
                "endpoint_id": "fal-ai/clarity-upscaler",
                "label": "Clarity Upscaler",
                "description": "High-fidelity restoration",
                "scale_factor": 2.0,
                "is_recommended": True,
            }
        ],
    ):
        res = await admin_api.discover_upscale_models()
        assert res["count"] == 1
        assert res["models"][0]["endpoint_id"] == "fal-ai/clarity-upscaler"


def test_upscale_models_crud(db_session: Session):
    """Test listing, creating, updating, toggling, and deleting upscale models."""
    # Initially empty
    models = admin_api.list_admin_upscale_models(session=db_session)
    assert len(models) == 0

    # Create model
    created = admin_api.create_admin_upscale_model(
        {
            "name": "Clarity 2x",
            "model_identifier": "fal-ai/clarity-upscaler",
            "params_json": {"scale": 2.0},
            "is_default": True,
        },
        session=db_session,
    )
    assert created["id"] is not None
    assert created["name"] == "Clarity 2x"
    assert created["is_default"] is True
    assert created["is_enabled"] is True

    # List
    models = admin_api.list_admin_upscale_models(session=db_session)
    assert len(models) == 1

    # Toggle active
    toggled = admin_api.toggle_admin_upscale_model(created["id"], session=db_session)
    assert toggled["is_enabled"] is False

    # Update
    updated = admin_api.update_admin_upscale_model(
        created["id"],
        {"name": "Clarity Upscaler Pro", "params_json": {"scale": 4.0}},
        session=db_session,
    )
    assert updated["name"] == "Clarity Upscaler Pro"
    assert updated["params_json"] == {"scale": 4.0}

    # Set default
    set_def = admin_api.set_default_admin_upscale_model(created["id"], session=db_session)
    assert set_def["is_default"] is True

    # Delete
    del_res = admin_api.delete_admin_upscale_model(created["id"], session=db_session)
    assert del_res == {"success": True}
    assert len(admin_api.list_admin_upscale_models(session=db_session)) == 0


def test_create_upscale_model_validation(db_session: Session):
    """Test validation errors for upscale model creation."""
    with pytest.raises(HTTPException) as exc:
        admin_api.create_admin_upscale_model(
            {"name": "", "model_identifier": "fal-ai/clarity"},
            session=db_session,
        )
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        admin_api.create_admin_upscale_model(
            {"name": "Clarity", "model_identifier": ""},
            session=db_session,
        )
    assert exc.value.status_code == 400


def _create_dummy_asset(db_session: Session) -> Asset:
    gen = Generation(
        profile_name="Test Profile",
        prompt_user="A cat",
        prompt_final="A cat",
        provider="fal",
        model="fal-ai/nano-banana-2",
        status="completed",
        profile_snapshot_json={},
        storage_template_snapshot_json={},
        request_snapshot_json={},
    )
    db_session.add(gen)
    db_session.commit()
    db_session.refresh(gen)

    asset = Asset(
        generation_id=gen.id,
        file_path="/tmp/test.png",
        sidecar_path="/tmp/test.json",
        thumbnail_path="/tmp/test_thumb.webp",
        width=1024,
        height=1024,
        mime="image/png",
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


@pytest.mark.asyncio
async def test_asset_upscale_no_model_configured_raises_400(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Test that upscale raises HTTP 400 with a clear message if no model is configured."""
    asset = _create_dummy_asset(db_session)
    from fastapi import BackgroundTasks

    # No model configured in DB
    with pytest.raises(HTTPException) as exc:
        assets_api.upscale_asset(
            asset_id=asset.id,
            background_tasks=BackgroundTasks(),
            payload=None,
            session=db_session,
        )
    assert exc.value.status_code == 400
    assert "No upscale model configured" in exc.value.detail


@pytest.mark.asyncio
async def test_asset_upscale_no_fal_key_raises_400(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Test that upscale raises HTTP 400 with a clear message if FAL API key is missing."""
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(assets_api.settings, "provider_config_key", key)
    assets_api.model_config_service = ModelConfigService(assets_api.settings)
    from fastapi import BackgroundTasks

    asset = _create_dummy_asset(db_session)

    # Create configured model
    crud.create_topaz_upscale_model(
        db_session,
        name="Clarity",
        model_identifier="fal-ai/clarity-upscaler",
        is_default=True,
    )

    # Missing FAL key
    with pytest.raises(HTTPException) as exc:
        assets_api.upscale_asset(
            asset_id=asset.id,
            background_tasks=BackgroundTasks(),
            payload=None,
            session=db_session,
        )
    assert exc.value.status_code == 400
    assert "FAL.ai API key is not configured" in exc.value.detail


@pytest.mark.asyncio
async def test_asset_upscale_models_exist_but_no_default_raises_400(
    db_session: Session,
):
    """Test that upscale raises HTTP 400 if models exist but none is marked as default."""
    from fastapi import BackgroundTasks

    asset = _create_dummy_asset(db_session)

    # Create a model with is_default=False
    crud.create_topaz_upscale_model(
        db_session,
        name="Clarity Non-Default",
        model_identifier="fal-ai/clarity-upscaler",
        is_default=False,
    )

    with pytest.raises(HTTPException) as exc:
        assets_api.upscale_asset(
            asset_id=asset.id,
            background_tasks=BackgroundTasks(),
            payload=None,
            session=db_session,
        )
    assert exc.value.status_code == 400
    assert "No upscale model configured" in exc.value.detail
