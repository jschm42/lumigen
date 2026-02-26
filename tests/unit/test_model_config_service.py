from __future__ import annotations

from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from app.config import Settings
from app.services.model_config_service import ModelConfigService


class _SessionCtx:
    def __init__(self, session):  # type: ignore[no-untyped-def]
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False


def test_encrypt_and_decrypt_roundtrip() -> None:
    key = Fernet.generate_key().decode("ascii")
    service = ModelConfigService(Settings(provider_config_key=key))

    encrypted = service.encrypt_api_key("secret-123")
    decrypted = service.decrypt_api_key(encrypted)

    assert encrypted != "secret-123"
    assert decrypted == "secret-123"


def test_encrypt_raises_when_provider_key_missing() -> None:
    service = ModelConfigService(Settings(provider_config_key=None))
    with pytest.raises(ValueError, match="PROVIDER_CONFIG_KEY"):
        service.encrypt_api_key("x")


def test_decrypt_invalid_token_raises_value_error() -> None:
    key = Fernet.generate_key().decode("ascii")
    service = ModelConfigService(Settings(provider_config_key=key))
    with pytest.raises(ValueError, match="Invalid encrypted API key"):
        service.decrypt_api_key("not-a-valid-token")


def test_get_default_api_key_maps_known_provider_names() -> None:
    service = ModelConfigService(
        Settings(
            openai_api_key="oa",
            openrouter_api_key="or",
            google_api_key="gg",
            bfl_api_key="bf",
        )
    )
    assert service.get_default_api_key("openai") == "oa"
    assert service.get_default_api_key("OPENROUTER") == "or"
    assert service.get_default_api_key("google") == "gg"
    assert service.get_default_api_key("bfl") == "bf"
    assert service.get_default_api_key("unknown") is None


def test_get_api_key_reads_custom_config_and_decrypts(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode("ascii")
    service = ModelConfigService(Settings(provider_config_key=key))
    encrypted = service.encrypt_api_key("custom-key")

    model_config = SimpleNamespace(
        use_custom_api_key=True,
        api_key_encrypted=encrypted,
    )
    monkeypatch.setattr("app.services.model_config_service.SessionLocal", lambda: _SessionCtx(SimpleNamespace()))
    monkeypatch.setattr(
        "app.services.model_config_service.crud.get_model_config",
        lambda _session, _id: model_config,
    )

    assert service.get_api_key(7) == "custom-key"


def test_get_api_key_returns_none_for_missing_or_disabled_custom_key(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ModelConfigService(Settings(provider_config_key=Fernet.generate_key().decode("ascii")))
    monkeypatch.setattr("app.services.model_config_service.SessionLocal", lambda: _SessionCtx(SimpleNamespace()))

    monkeypatch.setattr(
        "app.services.model_config_service.crud.get_model_config",
        lambda _session, _id: None,
    )
    assert service.get_api_key(1) is None

    monkeypatch.setattr(
        "app.services.model_config_service.crud.get_model_config",
        lambda _session, _id: SimpleNamespace(use_custom_api_key=False, api_key_encrypted="abc"),
    )
    assert service.get_api_key(1) is None

    monkeypatch.setattr(
        "app.services.model_config_service.crud.get_model_config",
        lambda _session, _id: SimpleNamespace(use_custom_api_key=True, api_key_encrypted=None),
    )
    assert service.get_api_key(1) is None


def test_get_model_config_uses_crud_and_sessionlocal(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ModelConfigService(Settings())
    expected = SimpleNamespace(id=12)

    monkeypatch.setattr("app.services.model_config_service.SessionLocal", lambda: _SessionCtx(SimpleNamespace()))
    monkeypatch.setattr(
        "app.services.model_config_service.crud.get_model_config",
        lambda _session, _id: expected,
    )

    loaded = service.get_model_config(12)
    assert loaded is expected
