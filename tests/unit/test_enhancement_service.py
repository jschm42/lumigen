from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.config import Settings
from app.services.enhancement_service import EnhancementService


class _SessionCtx:
    def __init__(self, session):  # type: ignore[no-untyped-def]
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False


def _json_response(method: str, url: str, status: int, payload: dict) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(status, json=payload, request=request)


def test_get_config_returns_none_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    secrets = SimpleNamespace(
        decrypt_api_key=lambda token: "never",
        get_default_api_key=lambda provider: None,
    )
    service = EnhancementService(Settings(), secrets)

    monkeypatch.setattr("app.services.enhancement_service.SessionLocal", lambda: _SessionCtx(SimpleNamespace()))
    monkeypatch.setattr("app.services.enhancement_service.crud.get_enhancement_config", lambda _session: None)
    assert service._get_config() is None

    monkeypatch.setattr(
        "app.services.enhancement_service.crud.get_enhancement_config",
        lambda _session: SimpleNamespace(provider="openai", model="gpt", api_key_encrypted=None),
    )
    assert service._get_config() is None


def test_get_config_falls_back_to_provider_key(monkeypatch: pytest.MonkeyPatch) -> None:
    secrets = SimpleNamespace(
        decrypt_api_key=lambda token: "never",
        get_default_api_key=lambda provider: "provider-key" if provider == "openai" else None,
    )
    service = EnhancementService(Settings(), secrets)

    monkeypatch.setattr("app.services.enhancement_service.SessionLocal", lambda: _SessionCtx(SimpleNamespace()))
    monkeypatch.setattr(
        "app.services.enhancement_service.crud.get_enhancement_config",
        lambda _session: SimpleNamespace(provider="openai", model="gpt", api_key_encrypted=None),
    )
    config = service._get_config()
    assert config is not None
    assert config["api_key"] == "provider-key"
    assert config["provider"] == "openai"
    assert config["model"] == "gpt"


def test_get_config_decrypts_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    secrets = SimpleNamespace(decrypt_api_key=lambda token: f"dec:{token}")
    service = EnhancementService(Settings(), secrets)

    monkeypatch.setattr("app.services.enhancement_service.SessionLocal", lambda: _SessionCtx(SimpleNamespace()))
    monkeypatch.setattr(
        "app.services.enhancement_service.crud.get_enhancement_config",
        lambda _session: SimpleNamespace(provider="openrouter", model="m", api_key_encrypted="enc"),
    )

    config = service._get_config()
    assert config == {"provider": "openrouter", "model": "m", "api_key": "dec:enc"}


@pytest.mark.asyncio
async def test_enhance_openai_builds_expected_request(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            calls.append({"url": url, "headers": headers or {}, "json": json})
            return _json_response(
                "POST",
                url,
                200,
                {"choices": [{"message": {"content": "  improved prompt  "}}]},
            )

    monkeypatch.setattr("app.services.enhancement_service.httpx.AsyncClient", FakeAsyncClient)

    key_used = {"token": None}

    def decrypt(token: str) -> str:
        key_used["token"] = token
        return "openai-secret"

    service = EnhancementService(
        Settings(openai_base_url="https://openai.test/v1"),
        SimpleNamespace(decrypt_api_key=decrypt),
    )
    monkeypatch.setattr("app.services.enhancement_service.SessionLocal", lambda: _SessionCtx(SimpleNamespace()))
    monkeypatch.setattr(
        "app.services.enhancement_service.crud.get_enhancement_config",
        lambda _session: SimpleNamespace(provider="openai", model="gpt-4.1-mini", api_key_encrypted="enc-openai"),
    )

    output = await service.enhance("short prompt", "system instruction")

    assert output == "improved prompt"
    assert key_used["token"] == "enc-openai"
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://openai.test/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer openai-secret"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["json"]["model"] == "gpt-4.1-mini"
    assert call["json"]["temperature"] == 0.7
    assert call["json"]["messages"][0] == {"role": "system", "content": "system instruction"}
    assert call["json"]["messages"][1] == {"role": "user", "content": "short prompt"}


@pytest.mark.asyncio
async def test_enhance_openrouter_builds_expected_request(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            calls.append({"url": url, "headers": headers or {}, "json": json})
            return _json_response(
                "POST",
                url,
                200,
                {"choices": [{"message": {"content": "ok"}}]},
            )

    monkeypatch.setattr("app.services.enhancement_service.httpx.AsyncClient", FakeAsyncClient)

    service = EnhancementService(
        Settings(app_name="Lumigen", openrouter_base_url="https://or.test/api/v1"),
        SimpleNamespace(decrypt_api_key=lambda _token: "or-secret"),
    )
    monkeypatch.setattr("app.services.enhancement_service.SessionLocal", lambda: _SessionCtx(SimpleNamespace()))
    monkeypatch.setattr(
        "app.services.enhancement_service.crud.get_enhancement_config",
        lambda _session: SimpleNamespace(provider="openrouter", model="or-model", api_key_encrypted="enc-or"),
    )

    output = await service.enhance("hello", None)
    assert output == "ok"
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://or.test/api/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer or-secret"
    assert call["headers"]["X-Title"] == "Lumigen"
    assert call["json"]["messages"] == [{"role": "user", "content": "hello"}]


@pytest.mark.asyncio
async def test_enhance_raises_for_unconfigured_unsupported_and_invalid_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.enhancement_service.SessionLocal", lambda: _SessionCtx(SimpleNamespace()))
    service = EnhancementService(Settings(), SimpleNamespace(decrypt_api_key=lambda token: "k"))

    monkeypatch.setattr("app.services.enhancement_service.crud.get_enhancement_config", lambda _session: None)
    with pytest.raises(ValueError, match="not configured"):
        await service.enhance("p", None)

    monkeypatch.setattr(
        "app.services.enhancement_service.crud.get_enhancement_config",
        lambda _session: SimpleNamespace(provider="google", model="m", api_key_encrypted="enc"),
    )
    with pytest.raises(ValueError, match="not supported"):
        await service.enhance("p", None)

    class FakeAsyncClient400:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, json
            return _json_response("POST", url, 400, {"error": "bad"})

    monkeypatch.setattr("app.services.enhancement_service.httpx.AsyncClient", FakeAsyncClient400)
    monkeypatch.setattr(
        "app.services.enhancement_service.crud.get_enhancement_config",
        lambda _session: SimpleNamespace(provider="openai", model="m", api_key_encrypted="enc"),
    )
    with pytest.raises(ValueError, match=r"request failed \(400\)"):
        await service.enhance("p", None)

    class FakeAsyncClientEmpty:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, json
            return _json_response("POST", url, 200, {"choices": [{"message": {"content": "   "}}]})

    monkeypatch.setattr("app.services.enhancement_service.httpx.AsyncClient", FakeAsyncClientEmpty)
    with pytest.raises(ValueError, match="empty content"):
        await service.enhance("p", None)
