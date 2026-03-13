from __future__ import annotations

import base64
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.config import Settings
from app.providers.base import (
    ProviderError,
    ProviderGenerationRequest,
    ProviderRateLimitError,
    ProviderServiceUnavailableError,
)
from app.providers.bfl_adapter import BFLAdapter
from app.providers.fal_adapter import FalAdapter
from app.providers.google_adapter import GoogleAdapter
from app.providers.openai_adapter import OpenAIAdapter
from app.providers.openrouter_adapter import OpenRouterAdapter


def _json_response(method: str, url: str, status: int, payload: dict) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(status, json=payload, request=request)


def _png_b64() -> str:
    image = Image.new("RGB", (10, 10), color=(10, 20, 30))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@pytest.mark.asyncio
async def test_google_generate_429_raises_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, params=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, params, json
            return _json_response("POST", url, 429, {"error": {"message": "rate"}})

    monkeypatch.setattr("app.providers.google_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = GoogleAdapter()
    settings = Settings(google_api_key="google-key")
    request = ProviderGenerationRequest(
        prompt="p",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="png",
        model="gemini-2.0-flash-preview-image-generation",
    )

    with pytest.raises(ProviderRateLimitError):
        await adapter.generate(request, settings)


@pytest.mark.asyncio
async def test_openai_generate_429_raises_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, json
            return _json_response("POST", url, 429, {"error": {"message": "rate"}})

    monkeypatch.setattr("app.providers.openai_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = OpenAIAdapter()
    settings = Settings(openai_api_key="openai-key")
    request = ProviderGenerationRequest(
        prompt="p",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="png",
        model="gpt-image-1",
    )

    with pytest.raises(ProviderRateLimitError):
        await adapter.generate(request, settings)


@pytest.mark.asyncio
async def test_openai_generate_empty_data_raises_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, json
            return _json_response("POST", url, 200, {"created": 1, "data": []})

    monkeypatch.setattr("app.providers.openai_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = OpenAIAdapter()
    settings = Settings(openai_api_key="openai-key")
    request = ProviderGenerationRequest(
        prompt="p",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="png",
        model="gpt-image-1",
    )

    with pytest.raises(ProviderError, match="no image data"):
        await adapter.generate(request, settings)


@pytest.mark.asyncio
async def test_openrouter_generate_503_raises_service_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, json
            return _json_response("POST", url, 503, {"error": {"message": "down"}})

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            return _json_response("GET", url, 404, {})

    monkeypatch.setattr("app.providers.openrouter_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = OpenRouterAdapter()
    settings = Settings(openrouter_api_key="or-key")
    request = ProviderGenerationRequest(
        prompt="p",
        width=1024,
        height=1024,
        n_images=1,
        seed=None,
        output_format="png",
        model="openrouter/model",
    )

    with pytest.raises(ProviderServiceUnavailableError):
        await adapter.generate(request, settings)


@pytest.mark.asyncio
async def test_openrouter_generate_empty_image_response_retries_then_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            calls.append({"url": url, "json": json})
            return _json_response(
                "POST",
                url,
                200,
                {"choices": [{"message": {"content": "No image available"}}]},
            )

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            return _json_response("GET", url, 404, {})

    monkeypatch.setattr("app.providers.openrouter_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = OpenRouterAdapter()
    settings = Settings(openrouter_api_key="or-key")
    request = ProviderGenerationRequest(
        prompt="p",
        width=1024,
        height=1024,
        n_images=1,
        seed=None,
        output_format="png",
        model="openrouter/model",
    )

    with pytest.raises(ProviderError, match="no generated image data"):
        await adapter.generate(request, settings)

    assert len(calls) == 2
    assert calls[0]["json"]["modalities"] == ["image", "text"]
    assert calls[1]["json"]["modalities"] == ["image"]


@pytest.mark.asyncio
async def test_bfl_generate_submit_429_raises_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, json
            return _json_response("POST", url, 429, {"error": {"message": "rate"}})

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            return _json_response("GET", url, 404, {})

    monkeypatch.setattr("app.providers.bfl_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = BFLAdapter()
    settings = Settings(bfl_api_key="bfl-key")
    request = ProviderGenerationRequest(
        prompt="p",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="png",
        model="flux-pro-1.1",
    )

    with pytest.raises(ProviderRateLimitError):
        await adapter.generate(request, settings)


@pytest.mark.asyncio
async def test_bfl_generate_polling_failed_status_raises_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, json
            return _json_response(
                "POST",
                url,
                200,
                {"id": "req-1", "polling_url": "https://poll.bfl.test/result/req-1"},
            )

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            return _json_response(
                "GET",
                url,
                200,
                {"status": "failed", "error": "upstream failure"},
            )

    async def fast_sleep(_duration: float) -> None:
        return None

    monkeypatch.setattr("app.providers.bfl_adapter.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("app.providers.bfl_adapter.asyncio.sleep", fast_sleep)

    adapter = BFLAdapter()
    settings = Settings(bfl_api_key="bfl-key")
    request = ProviderGenerationRequest(
        prompt="p",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="png",
        model="flux-pro-1.1",
    )

    with pytest.raises(ProviderError, match="generation failed"):
        await adapter.generate(request, settings)


@pytest.mark.asyncio
async def test_bfl_generate_polling_5xx_exhaustion_raises_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, json
            return _json_response(
                "POST",
                url,
                200,
                {"id": "req-2", "polling_url": "https://poll.bfl.test/result/req-2"},
            )

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            return _json_response("GET", url, 503, {"message": "temporary"})

    async def fast_sleep(_duration: float) -> None:
        return None

    monkeypatch.setattr("app.providers.bfl_adapter.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("app.providers.bfl_adapter.asyncio.sleep", fast_sleep)
    monkeypatch.setattr(BFLAdapter, "MAX_POLL_ATTEMPTS", 2)

    adapter = BFLAdapter()
    settings = Settings(bfl_api_key="bfl-key")
    request = ProviderGenerationRequest(
        prompt="p",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="png",
        model="flux-pro-1.1",
    )

    with pytest.raises(ProviderServiceUnavailableError, match="polling failed"):
        await adapter.generate(request, settings)


@pytest.mark.asyncio
async def test_openai_list_models_non_json_raises_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            request = httpx.Request("GET", url)
            return httpx.Response(200, text="not json", request=request)

    monkeypatch.setattr("app.providers.openai_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = OpenAIAdapter()
    settings = Settings(openai_api_key="openai-key", openai_base_url="https://api.openai.test/v1")

    with pytest.raises(ProviderError, match="non-JSON models response"):
        await adapter.list_models(settings)


@pytest.mark.asyncio
async def test_openrouter_list_models_4xx_includes_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            return _json_response("GET", url, 401, {"error": {"message": "invalid token"}})

    monkeypatch.setattr("app.providers.openrouter_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = OpenRouterAdapter()
    settings = Settings(openrouter_api_key="or-key", openrouter_base_url="https://openrouter.test/api/v1")

    with pytest.raises(ProviderError, match="invalid token"):
        await adapter.list_models(settings)


@pytest.mark.asyncio
async def test_openrouter_list_models_non_json_raises_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            request = httpx.Request("GET", url)
            return httpx.Response(200, text="<html>oops</html>", request=request)

    monkeypatch.setattr("app.providers.openrouter_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = OpenRouterAdapter()
    settings = Settings(openrouter_api_key="or-key", openrouter_base_url="https://openrouter.test/api/v1")

    with pytest.raises(ProviderError, match="non-JSON models response"):
        await adapter.list_models(settings)


@pytest.mark.asyncio
async def test_bfl_list_models_4xx_includes_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            return _json_response("GET", url, 403, {"message": "forbidden"})

    monkeypatch.setattr("app.providers.bfl_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = BFLAdapter()
    settings = Settings(bfl_api_key="bfl-key")

    with pytest.raises(ProviderError, match="forbidden"):
        await adapter.list_models(settings)


@pytest.mark.asyncio
async def test_bfl_list_models_non_json_raises_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            request = httpx.Request("GET", url)
            return httpx.Response(200, text="plain text", request=request)

    monkeypatch.setattr("app.providers.bfl_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = BFLAdapter()
    settings = Settings(bfl_api_key="bfl-key")

    with pytest.raises(ProviderError, match="non-JSON models response"):
        await adapter.list_models(settings)


@pytest.mark.asyncio
async def test_fal_generate_submit_429_raises_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, json
            return _json_response("POST", url, 429, {"detail": "rate limit exceeded"})

    monkeypatch.setattr("app.providers.fal_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = FalAdapter()
    settings = Settings(fal_api_key="fal-key")
    request = ProviderGenerationRequest(
        prompt="p",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="jpeg",
        model="fal-ai/flux/schnell",
    )

    with pytest.raises(ProviderRateLimitError):
        await adapter.generate(request, settings)


@pytest.mark.asyncio
async def test_fal_generate_submit_503_raises_service_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, json
            return _json_response("POST", url, 503, {"detail": "service down"})

    monkeypatch.setattr("app.providers.fal_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = FalAdapter()
    settings = Settings(fal_api_key="fal-key")
    request = ProviderGenerationRequest(
        prompt="p",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="jpeg",
        model="fal-ai/flux/schnell",
    )

    with pytest.raises(ProviderServiceUnavailableError):
        await adapter.generate(request, settings)


@pytest.mark.asyncio
async def test_fal_generate_no_request_id_raises_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, json
            return _json_response("POST", url, 200, {"status": "something"})

    monkeypatch.setattr("app.providers.fal_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = FalAdapter()
    settings = Settings(fal_api_key="fal-key")
    request = ProviderGenerationRequest(
        prompt="p",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="jpeg",
        model="fal-ai/flux/schnell",
    )

    with pytest.raises(ProviderError, match="request_id"):
        await adapter.generate(request, settings)


@pytest.mark.asyncio
async def test_fal_generate_polling_failed_status_raises_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, json
            return _json_response("POST", url, 200, {"request_id": "req-f"})

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            return _json_response("GET", url, 200, {"status": "FAILED", "error": "model error"})

    async def fast_sleep(_duration: float) -> None:
        return None

    monkeypatch.setattr("app.providers.fal_adapter.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("app.providers.fal_adapter.asyncio.sleep", fast_sleep)

    adapter = FalAdapter()
    settings = Settings(fal_api_key="fal-key")
    request = ProviderGenerationRequest(
        prompt="p",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="jpeg",
        model="fal-ai/flux/schnell",
    )

    with pytest.raises(ProviderError, match="generation failed"):
        await adapter.generate(request, settings)


@pytest.mark.asyncio
async def test_fal_generate_polling_5xx_exhaustion_raises_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            _ = headers, json
            return _json_response("POST", url, 200, {"request_id": "req-5xx"})

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            return _json_response("GET", url, 503, {"detail": "down"})

    async def fast_sleep(_duration: float) -> None:
        return None

    monkeypatch.setattr("app.providers.fal_adapter.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("app.providers.fal_adapter.asyncio.sleep", fast_sleep)
    monkeypatch.setattr(FalAdapter, "MAX_POLL_ATTEMPTS", 2)

    adapter = FalAdapter()
    settings = Settings(fal_api_key="fal-key")
    request = ProviderGenerationRequest(
        prompt="p",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="jpeg",
        model="fal-ai/flux/schnell",
    )

    with pytest.raises(ProviderServiceUnavailableError, match="polling failed"):
        await adapter.generate(request, settings)
