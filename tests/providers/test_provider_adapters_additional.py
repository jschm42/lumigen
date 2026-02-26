from __future__ import annotations

import base64
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.config import Settings
from app.providers.base import (
    ProviderConfigError,
    ProviderError,
    ProviderGenerationRequest,
)
from app.providers.bfl_adapter import BFLAdapter
from app.providers.google_adapter import GoogleAdapter
from app.providers.openrouter_adapter import OpenRouterAdapter


def _png_bytes(size: tuple[int, int] = (14, 9)) -> bytes:
    image = Image.new("RGB", size, color=(90, 110, 140))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _data_url_png(size: tuple[int, int] = (14, 9)) -> str:
    return "data:image/png;base64," + base64.b64encode(_png_bytes(size)).decode("ascii")


def _json_response(method: str, url: str, status: int, payload: dict) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(status, json=payload, request=request)


@pytest.mark.asyncio
async def test_openrouter_generate_retries_without_explicit_dimensions(
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
            calls.append({"url": url, "json": json or {}})
            if len(calls) == 1:
                return _json_response(
                    "POST",
                    url,
                    400,
                    {"error": {"message": "size parameter is not supported"}},
                )
            return _json_response(
                "POST",
                url,
                200,
                {"choices": [{"message": {"images": [{"url": _data_url_png((21, 13))}]}}]},
            )

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            return _json_response("GET", url, 404, {})

    monkeypatch.setattr("app.providers.openrouter_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = OpenRouterAdapter()
    settings = Settings(openrouter_api_key="or-key", openrouter_base_url="https://openrouter.test/api/v1")
    request = ProviderGenerationRequest(
        prompt="prompt",
        width=1024,
        height=768,
        n_images=1,
        seed=None,
        output_format="png",
        model="openrouter/model",
    )

    result = await adapter.generate(request, settings)

    assert len(calls) == 2
    assert "size" in calls[0]["json"]
    assert "size" not in calls[1]["json"]
    assert len(result.images) == 1
    assert result.images[0].width == 21
    assert result.images[0].height == 13


@pytest.mark.asyncio
async def test_openrouter_generate_retries_with_image_only_modalities(
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
            calls.append({"url": url, "json": json or {}})
            if len(calls) == 1:
                return _json_response(
                    "POST",
                    url,
                    404,
                    {
                        "error": {
                            "message": "No endpoints found that support the requested output modalities"
                        }
                    },
                )
            return _json_response(
                "POST",
                url,
                200,
                {"choices": [{"message": {"images": [{"url": _data_url_png((15, 10))}]}}]},
            )

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            return _json_response("GET", url, 404, {})

    monkeypatch.setattr("app.providers.openrouter_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = OpenRouterAdapter()
    settings = Settings(openrouter_api_key="or-key", openrouter_base_url="https://openrouter.test/api/v1")
    request = ProviderGenerationRequest(
        prompt="prompt",
        width=None,
        height=None,
        n_images=1,
        seed=None,
        output_format="png",
        model="openrouter/model",
    )

    result = await adapter.generate(request, settings)

    assert len(calls) == 2
    assert calls[0]["json"]["modalities"] == ["image", "text"]
    assert calls[1]["json"]["modalities"] == ["image"]
    assert len(result.images) == 1
    assert result.images[0].width == 15
    assert result.images[0].height == 10


@pytest.mark.asyncio
async def test_openrouter_extract_refs_and_decode_error_paths() -> None:
    adapter = OpenRouterAdapter()
    big_b64 = base64.b64encode(_png_bytes((64, 64))).decode("ascii")

    refs = adapter._extract_image_refs(
        {
            "choices": [
                {
                    "message": {
                        "images": [{"image_url": {"url": _data_url_png((12, 8))}}],
                        "content": [
                            {"type": "image_url", "image_url": {"url": _data_url_png((7, 5))}},
                            "https://img.example/a.png",
                        ],
                    }
                }
            ],
            "data": [{"b64_json": big_b64}],
            "output": [{"content": "![x](https://img.example/b.png)"}],
        },
        output_format="png",
    )

    assert any(item.startswith("data:image/png;base64,") for item in refs)
    assert "https://img.example/a.png" in refs
    assert "https://img.example/b.png" in refs

    with pytest.raises(ProviderError, match="unsupported format"):
        await adapter._read_image_payload(None, "invalid-ref", 1)  # type: ignore[arg-type]

    with pytest.raises(ProviderError, match="Decoded OpenRouter image payload was empty"):
        adapter._decode_data_url("data:image/png;base64,   ", 1)


@pytest.mark.asyncio
async def test_bfl_generate_uses_custom_request_key_and_handles_missing_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submit_calls: list[dict] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            submit_calls.append({"url": url, "headers": headers or {}, "json": json or {}})
            if len(submit_calls) == 1:
                return _json_response(
                    "POST",
                    url,
                    200,
                    {"id": "req-9", "polling_url": "https://poll.bfl.test/result/req-9"},
                )
            return _json_response("POST", url, 200, {"polling_url": "https://poll.bfl.test/missing"})

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            return _json_response(
                "GET",
                url,
                200,
                {"status": "ready", "result": {"sample": base64.b64encode(_png_bytes((11, 6))).decode("ascii")}},
            )

    async def fast_sleep(_duration: float) -> None:
        return None

    monkeypatch.setattr("app.providers.bfl_adapter.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("app.providers.bfl_adapter.asyncio.sleep", fast_sleep)
    monkeypatch.setattr(BFLAdapter, "_write_debug_log", lambda self, prefix, data: None)

    adapter = BFLAdapter()
    request = ProviderGenerationRequest(
        prompt="p",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="png",
        model="flux-pro-1.1",
        api_key="custom-key",
    )
    settings = Settings(bfl_api_key=None)

    result = await adapter.generate(request, settings)
    assert len(result.images) == 1
    assert submit_calls[0]["headers"]["x-key"] == "custom-key"

    with pytest.raises(ProviderError, match="did not return a request ID"):
        await adapter.generate(request, settings)


@pytest.mark.asyncio
async def test_bfl_poll_non_json_and_list_models_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    class PollClient:
        async def get(self, _url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            request = httpx.Request("GET", "https://poll.bfl.test")
            return httpx.Response(200, text="not-json", request=request)

    async def fast_sleep(_duration: float) -> None:
        return None

    monkeypatch.setattr("app.providers.bfl_adapter.asyncio.sleep", fast_sleep)
    adapter = BFLAdapter()
    request = ProviderGenerationRequest(
        prompt="p",
        width=1,
        height=1,
        n_images=1,
        seed=None,
        output_format="png",
        model="m",
    )
    with pytest.raises(ProviderError, match="polling returned non-JSON"):
        await adapter._poll_for_result(PollClient(), "https://poll.bfl.test", "id", request)

    class ModelsClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            _ = headers
            if url.endswith("/models"):
                return _json_response("GET", url, 200, {"models": [{"name": "flux-a"}, {"id": "flux-b"}, 1]})
            request_obj = httpx.Request("GET", url)
            return httpx.Response(200, text="not-json", request=request_obj)

    monkeypatch.setattr("app.providers.bfl_adapter.httpx.AsyncClient", ModelsClient)
    models = await adapter.list_models(Settings(bfl_api_key="k"))
    assert models == ["flux-a", "flux-b"]


@pytest.mark.asyncio
async def test_google_adapter_config_and_pending_paths() -> None:
    adapter = GoogleAdapter()
    request = ProviderGenerationRequest(
        prompt="p",
        width=1,
        height=1,
        n_images=1,
        seed=None,
        output_format="png",
        model="imagen",
    )

    with pytest.raises(ProviderConfigError):
        await adapter.list_models(Settings(google_api_key=None))

    with pytest.raises(ProviderConfigError):
        await adapter.generate(request, Settings(google_api_key=None))

    assert await adapter.list_models(Settings(google_api_key="g-key")) == [
        "imagen-3.0-generate-002"
    ]
    with pytest.raises(ProviderError, match="implementation is pending"):
        await adapter.generate(request, Settings(google_api_key="g-key"))
