from __future__ import annotations

import base64
from io import BytesIO

import pytest
from PIL import Image

from app.providers.base import ProviderError, ProviderGenerationRequest, ProviderImage


def _png_bytes(width: int = 8, height: int = 8) -> bytes:
    image = Image.new("RGB", (width, height), color=(200, 30, 30))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_get_provider_models_returns_list(client, app_module, monkeypatch) -> None:
    expected = ["model-a", "model-b"]

    async def fake_list_models(provider, api_key=None):  # type: ignore[no-untyped-def]
        assert provider == "openai"
        return list(expected)

    monkeypatch.setattr(
        app_module.provider_registry, "list_models", fake_list_models
    )

    response = client.get("/api/providers/openai/models")
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["models"] == expected


def test_get_provider_models_with_inline_api_key(
    client, app_module, monkeypatch
) -> None:
    captured: dict = {}

    async def fake_list_models(provider, api_key=None):  # type: ignore[no-untyped-def]
        captured["provider"] = provider
        captured["api_key"] = api_key
        return ["m1"]

    monkeypatch.setattr(
        app_module.provider_registry, "list_models", fake_list_models
    )

    response = client.get(
        "/api/providers/openai/models",
        params={"api_key": "  inline-secret  "},
    )
    assert response.status_code == 200
    assert captured["provider"] == "openai"
    assert captured["api_key"] == "inline-secret"


def test_get_provider_models_returns_empty_on_error(
    client, app_module, monkeypatch
) -> None:
    async def fake_list_models(provider, api_key=None):  # type: ignore[no-untyped-def]
        raise ProviderError("no key")

    monkeypatch.setattr(
        app_module.provider_registry, "list_models", fake_list_models
    )

    response = client.get("/api/providers/openai/models")
    assert response.status_code == 200
    body = response.json()
    assert body["models"] == []
    assert body["error"] == "no key"


def test_post_provider_test_returns_data_url(
    client, app_module, monkeypatch
) -> None:
    image_bytes = _png_bytes(16, 16)
    captured: dict = {}

    async def fake_test_connection(provider, model, api_key=None):  # type: ignore[no-untyped-def]
        captured["provider"] = provider
        captured["model"] = model
        captured["api_key"] = api_key
        from app.providers.base import ProviderGenerationResult

        return ProviderGenerationResult(
            images=[
                ProviderImage(
                    data=image_bytes,
                    mime="image/png",
                    width=16,
                    height=16,
                    meta={"provider": provider, "index": 1},
                )
            ],
            raw_meta={"provider": provider, "model": model},
        )

    monkeypatch.setattr(
        app_module.provider_registry, "test_connection", fake_test_connection
    )

    response = client.post(
        "/api/providers/openai/test",
        json={"model": "gpt-image-1", "api_key": "  my-key  "},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["provider"] == "openai"
    assert body["image"]["mime"] == "image/png"
    assert body["image"]["width"] == 16
    assert body["image"]["height"] == 16
    assert body["image"]["data_url"].startswith("data:image/png;base64,")
    # Confirm the base64 decodes back to the original PNG bytes.
    payload = body["image"]["data_url"].split(",", 1)[1]
    assert base64.b64decode(payload) == image_bytes
    assert captured["provider"] == "openai"
    assert captured["model"] == "gpt-image-1"
    assert captured["api_key"] == "my-key"


def test_post_provider_test_without_api_key_uses_db_stored_key(
    client, app_module, monkeypatch
) -> None:
    """When no inline API key is provided, the endpoint should use the centrally stored DB key."""
    captured: dict = {}

    async def fake_test_connection(provider, model, api_key=None):  # type: ignore[no-untyped-def]
        captured["api_key"] = api_key
        from app.providers.base import ProviderGenerationResult

        return ProviderGenerationResult(
            images=[
                ProviderImage(
                    data=_png_bytes(8, 8),
                    mime="image/png",
                    width=8,
                    height=8,
                )
            ]
        )

    # Mock model_config_service.get_default_api_key to return a known key
    def mock_get_default_api_key(provider):
        return "db-stored-api-key-for-testing"

    monkeypatch.setattr(
        app_module.provider_registry, "test_connection", fake_test_connection
    )
    monkeypatch.setattr(
        app_module.model_config_service, "get_default_api_key", mock_get_default_api_key
    )

    response = client.post(
        "/api/providers/openai/test",
        json={"model": "gpt-image-1"},
    )
    assert response.status_code == 200
    # Now the endpoint correctly uses the DB-stored key when no inline key is provided
    assert captured["api_key"] == "db-stored-api-key-for-testing"


def test_post_provider_test_missing_model_returns_422(
    client, app_module, monkeypatch
) -> None:
    async def fake_test_connection(provider, model, api_key=None):  # type: ignore[no-untyped-def]
        raise AssertionError("should not be called")

    monkeypatch.setattr(
        app_module.provider_registry, "test_connection", fake_test_connection
    )

    response = client.post(
        "/api/providers/openai/test",
        json={"api_key": "k"},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "Model is required."


def test_post_provider_test_unknown_provider_returns_404(
    client, app_module
) -> None:
    response = client.post(
        "/api/providers/no-such-provider/test",
        json={"model": "x"},
    )
    assert response.status_code == 404
    assert response.json()["error"] == "Unsupported provider."


def test_post_provider_test_propagates_provider_error(
    client, app_module, monkeypatch
) -> None:
    async def fake_test_connection(provider, model, api_key=None):  # type: ignore[no-untyped-def]
        raise ProviderError("auth failed")

    monkeypatch.setattr(
        app_module.provider_registry, "test_connection", fake_test_connection
    )

    response = client.post(
        "/api/providers/openai/test",
        json={"model": "gpt-image-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["image"] is None
    assert body["error"] == "auth failed"


def test_post_provider_test_requires_admin(anon_client, app_module) -> None:
    """Test endpoint requires admin; unauthenticated users are redirected (303)."""
    response = anon_client.post(
        "/api/providers/openai/test",
        json={"model": "gpt-image-1"},
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_minimax_adapter_parses_base64_response(
    app_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Smoke-test the MiniMax adapter against a fake HTTP client."""
    from app.providers.minimax_adapter import MiniMaxAdapter

    image_bytes = _png_bytes(4, 4)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    calls: list[dict] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            import httpx

            calls.append({"url": url, "headers": headers, "json": json})
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                request=request,
                json={"data": {"image_base64": [image_b64]}},
            )

    monkeypatch.setattr(
        "app.providers.minimax_adapter.httpx.AsyncClient", FakeAsyncClient
    )

    adapter = MiniMaxAdapter()
    request = ProviderGenerationRequest(
        prompt="a red square",
        width=256,
        height=256,
        n_images=1,
        seed=0,
        output_format="png",
        model="image-01",
    )
    settings = app_module.settings.model_copy(
        update={"minimax_api_key": "test-key", "minimax_base_url": "https://minimax.test"}
    )
    result = await adapter.generate(request, settings)
    assert len(result.images) == 1
    assert result.images[0].data == image_bytes
    assert result.images[0].mime == "image/png"
    assert result.images[0].width == 256
    assert result.images[0].height == 256
    assert calls[0]["headers"]["Authorization"] == "Bearer test-key"
    assert calls[0]["json"]["model"] == "image-01"
    assert calls[0]["json"]["response_format"] == "base64"


def test_minimax_adapter_list_models(app_module) -> None:
    from app.providers.minimax_adapter import MiniMaxAdapter

    settings = app_module.settings.model_copy(update={"minimax_api_key": "k"})

    async def run() -> list[str]:
        return await MiniMaxAdapter().list_models(settings)

    import asyncio

    models = asyncio.run(run())
    assert "image-01" in models
