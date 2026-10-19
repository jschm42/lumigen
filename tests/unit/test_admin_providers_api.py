"""Unit tests for admin provider API endpoints."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import admin as admin_api
from app.db import crud
from app.db.models import Base
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


def test_update_provider_key_success(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Test saving an encrypted provider API key via admin API."""
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(admin_api.settings, "provider_config_key", key)
    admin_api.model_config_service = ModelConfigService(admin_api.settings)

    res = admin_api.update_provider_key("fal", {"api_key": "fal-test-key-1234"}, session=db_session)
    assert res == {"success": True}

    stored = crud.get_provider_api_key(db_session, "fal")
    assert stored is not None
    assert stored.provider == "fal"
    assert stored.api_key_encrypted != "fal-test-key-1234"

    # Decrypt and check
    decrypted = admin_api.model_config_service.decrypt_api_key(stored.api_key_encrypted)
    assert decrypted == "fal-test-key-1234"


def test_update_provider_key_empty_raises_400(db_session: Session):
    """Test that empty API key raises HTTP 400."""
    with pytest.raises(HTTPException) as exc:
        admin_api.update_provider_key("fal", {"api_key": "   "}, session=db_session)
    assert exc.value.status_code == 400
    assert "API key is required" in exc.value.detail


def test_update_provider_key_without_encryption_key_raises_400(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Test that missing PROVIDER_CONFIG_KEY produces a 400 error instead of 500."""
    monkeypatch.setattr(admin_api.settings, "provider_config_key", None)
    admin_api.model_config_service = ModelConfigService(admin_api.settings)

    with pytest.raises(HTTPException) as exc:
        admin_api.update_provider_key("fal", {"api_key": "fal-test-key"}, session=db_session)
    assert exc.value.status_code == 400
    assert "PROVIDER_CONFIG_KEY is not set" in exc.value.detail


def test_delete_provider_key(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Test deleting a provider API key."""
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(admin_api.settings, "provider_config_key", key)
    admin_api.model_config_service = ModelConfigService(admin_api.settings)

    admin_api.update_provider_key("fal", {"api_key": "fal-test-key"}, session=db_session)
    assert crud.get_provider_api_key(db_session, "fal") is not None

    del_res = admin_api.delete_provider_key("fal", session=db_session)
    assert del_res == {"success": True}
    assert crud.get_provider_api_key(db_session, "fal") is None


def test_get_providers_status(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Test listing provider status reflecting stored DB keys."""
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(admin_api.settings, "provider_config_key", key)
    admin_api.model_config_service = ModelConfigService(admin_api.settings)

    providers_before = admin_api.get_providers(session=db_session)
    fal_status = next(p for p in providers_before if p["provider"] == "fal")
    assert fal_status["has_key"] is False

    admin_api.update_provider_key("fal", {"api_key": "fal-test-key"}, session=db_session)

    providers_after = admin_api.get_providers(session=db_session)
    fal_status_after = next(p for p in providers_after if p["provider"] == "fal")
    assert fal_status_after["has_key"] is True


@pytest.mark.asyncio
async def test_test_provider_connection(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Test provider connection test endpoint."""
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(admin_api.settings, "provider_config_key", key)
    admin_api.model_config_service = ModelConfigService(admin_api.settings)

    # Without key -> raises 400
    with pytest.raises(HTTPException) as exc:
        await admin_api.test_provider_connection("fal", session=db_session)
    assert exc.value.status_code == 400
    assert "No API key configured" in exc.value.detail

    # With key -> success
    admin_api.update_provider_key("fal", {"api_key": "fal-test-key"}, session=db_session)
    res = await admin_api.test_provider_connection("fal", session=db_session)
    assert res["success"] is True
