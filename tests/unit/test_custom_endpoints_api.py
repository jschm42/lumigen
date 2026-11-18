"""Unit tests for the custom endpoint admin API and endpoint-aware model configs."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import admin as admin_api
from app.db import crud
from app.db.models import Base
from app.providers.base import EndpointConfig, ProviderConfigError, ProviderError
from app.providers.comfyui_workflow import DEFAULT_WORKFLOW
from app.services.model_config_service import ModelConfigService


@pytest.fixture
def db_session():
    """Provide an isolated in-memory SQLite database session."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch: pytest.MonkeyPatch):
    """Configure a Fernet key so endpoint API keys can be encrypted."""
    monkeypatch.setattr(admin_api.settings, "provider_config_key", Fernet.generate_key().decode("ascii"))
    monkeypatch.setattr(admin_api, "model_config_service", ModelConfigService(admin_api.settings))


def _create(session: Session, **overrides) -> dict:
    payload = {"name": "LocalAI", "kind": "openai_compatible", "base_url": "http://localhost:8080/v1/"}
    payload.update(overrides)
    return admin_api.create_endpoint(payload, session=session)


def test_create_endpoint_normalizes_url_and_encrypts_optional_key(db_session: Session) -> None:
    created = _create(db_session, api_key="sk-local")

    assert created["base_url"] == "http://localhost:8080/v1"
    assert created["has_api_key"] is True
    assert created["kind_label"] == "OpenAI-compatible API"
    stored = crud.get_custom_endpoint(db_session, created["id"])
    assert stored.api_key_encrypted != "sk-local"
    assert admin_api.model_config_service.decrypt_api_key(stored.api_key_encrypted) == "sk-local"

    without_key = _create(db_session, name="ComfyUI", kind="comfyui", base_url="http://gpu:8188")
    assert without_key["has_api_key"] is False


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        ({"name": ""}, 400),
        ({"kind": "midjourney"}, 400),
        ({"base_url": "localhost:8080"}, 400),
    ],
)
def test_create_endpoint_validation(db_session: Session, overrides: dict, status: int) -> None:
    with pytest.raises(HTTPException) as exc:
        _create(db_session, **overrides)
    assert exc.value.status_code == status


def test_duplicate_endpoint_name_conflicts(db_session: Session) -> None:
    _create(db_session)
    with pytest.raises(HTTPException) as exc:
        _create(db_session)
    assert exc.value.status_code == 409


def test_update_endpoint_keeps_or_clears_key(db_session: Session) -> None:
    created = _create(db_session, api_key="sk-1")

    kept = admin_api.update_endpoint(created["id"], {"name": "Renamed"}, session=db_session)
    assert kept["name"] == "Renamed" and kept["has_api_key"] is True

    cleared = admin_api.update_endpoint(created["id"], {"clear_api_key": True}, session=db_session)
    assert cleared["has_api_key"] is False


def test_endpoint_in_use_cannot_be_deleted_or_change_kind(db_session: Session) -> None:
    endpoint = _create(db_session, name="GPU", kind="comfyui", base_url="http://gpu:8188")
    admin_api.create_model_config(
        {"name": "SDXL", "provider": "comfyui", "model_identifier": "sdxl.safetensors", "endpoint_id": endpoint["id"]},
        session=db_session,
    )

    with pytest.raises(HTTPException) as exc:
        admin_api.delete_endpoint(endpoint["id"], session=db_session)
    assert exc.value.status_code == 409 and "SDXL" in exc.value.detail

    with pytest.raises(HTTPException) as exc:
        admin_api.update_endpoint(endpoint["id"], {"kind": "openai_compatible"}, session=db_session)
    assert exc.value.status_code == 409

    assert admin_api.list_endpoints(session=db_session)[0]["model_count"] == 1


def test_endpoint_model_requires_matching_endpoint(db_session: Session) -> None:
    oai = _create(db_session)
    base = {"name": "Flux", "provider": "comfyui", "model_identifier": "flux.safetensors"}

    with pytest.raises(HTTPException, match="Select the endpoint"):
        admin_api.create_model_config(dict(base), session=db_session)
    with pytest.raises(HTTPException) as exc:
        admin_api.create_model_config({**base, "endpoint_id": oai["id"]}, session=db_session)
    assert "not a comfyui endpoint" in exc.value.detail


def test_comfyui_model_validates_and_stores_workflow(db_session: Session) -> None:
    endpoint = _create(db_session, name="GPU", kind="comfyui", base_url="http://gpu:8188")
    payload = {
        "name": "SDXL custom",
        "provider": "comfyui",
        "model_identifier": "sdxl",
        "endpoint_id": endpoint["id"],
        "provider_options": {"workflow": '{"nodes": [], "links": []}'},
    }
    with pytest.raises(HTTPException) as exc:
        admin_api.create_model_config(payload, session=db_session)
    assert "API" in exc.value.detail

    import json

    payload["provider_options"] = {"workflow": json.dumps(DEFAULT_WORKFLOW)}
    created = admin_api.create_model_config(payload, session=db_session)
    assert created["endpoint_name"] == "GPU"
    assert created["provider_options"]["workflow"] == DEFAULT_WORKFLOW


def test_builtin_provider_model_drops_endpoint_fields(db_session: Session) -> None:
    endpoint = _create(db_session)
    created = admin_api.create_model_config(
        {
            "name": "Gpt",
            "provider": "openai",
            "model_identifier": "gpt-image-1",
            "endpoint_id": endpoint["id"],
            "provider_options": {"workflow": "x"},
        },
        session=db_session,
    )
    assert created["endpoint_id"] is None and created["provider_options"] == {}


def test_provider_catalog_hides_endpoint_kinds() -> None:
    names = [name for name, _ in admin_api._provider_catalog()]
    assert "comfyui" not in names and "openai_compatible" not in names
    assert "openai" in names


@pytest.mark.asyncio
async def test_test_endpoint_reuses_stored_key_and_reports_failures(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import generation as generation_api

    created = _create(db_session, api_key="sk-stored")
    seen: list[EndpointConfig] = []

    async def fake_list(endpoint: EndpointConfig) -> list[str]:
        seen.append(endpoint)
        return ["model-a"]

    monkeypatch.setattr(generation_api.provider_registry, "list_endpoint_models", fake_list)
    result = await admin_api.test_endpoint(
        {"id": created["id"], "kind": "openai_compatible", "base_url": "http://localhost:8080/v1"},
        session=db_session,
    )
    assert result == {"success": True, "message": "Connected. 1 model available.", "models": ["model-a"]}
    assert seen[0].api_key == "sk-stored"

    async def failing(endpoint: EndpointConfig) -> list[str]:
        raise ProviderError("connection refused")

    monkeypatch.setattr(generation_api.provider_registry, "list_endpoint_models", failing)
    result = await admin_api.test_endpoint({"kind": "comfyui", "base_url": "http://gpu:8188"}, session=db_session)
    assert result["success"] is False and "connection refused" in result["message"]


def test_endpoint_config_for_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """ModelConfigService resolves endpoint + options and rejects inactive endpoints."""
    from app.db.engine import SessionLocal
    from app.db.models import CustomEndpoint, ModelConfig

    service = admin_api.model_config_service
    with SessionLocal() as session:
        endpoint = CustomEndpoint(
            name="Svc test GPU",
            kind="comfyui",
            base_url="http://gpu:8188",
            api_key_encrypted=service.encrypt_api_key("k"),
        )
        session.add(endpoint)
        session.commit()
        model = ModelConfig(
            name="Svc test model",
            provider="comfyui",
            model="sdxl",
            endpoint_id=endpoint.id,
            provider_options={"workflow": DEFAULT_WORKFLOW},
        )
        session.add(model)
        session.commit()
        endpoint_id = endpoint.id
        model_id = model.id

    try:
        config = service.endpoint_config_for(service.get_model_config(model_id))
        assert config is not None
        assert (config.kind, config.base_url, config.api_key) == ("comfyui", "http://gpu:8188", "k")
        assert config.options["workflow"] == DEFAULT_WORKFLOW

        with SessionLocal() as session:
            session.get(CustomEndpoint, endpoint_id).is_active = False
            session.commit()
        with pytest.raises(ProviderConfigError, match="deactivated"):
            service.endpoint_config_for(service.get_model_config(model_id))

        builtin = ModelConfig(name="x", provider="openai", model="gpt-image-1")
        assert service.endpoint_config_for(builtin) is None
    finally:
        with SessionLocal() as session:
            session.delete(session.get(ModelConfig, model_id))
            session.delete(session.get(CustomEndpoint, endpoint_id))
            session.commit()
