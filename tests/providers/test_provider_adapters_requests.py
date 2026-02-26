from __future__ import annotations

import base64
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.config import Settings
from app.providers.base import ProviderGenerationRequest, ProviderInputImage
from app.providers.bfl_adapter import BFLAdapter
from app.providers.openai_adapter import OpenAIAdapter
from app.providers.openrouter_adapter import OpenRouterAdapter


def _png_bytes(width: int = 16, height: int = 12) -> bytes:
    image = Image.new("RGB", (width, height), color=(120, 80, 160))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _json_response(method: str, url: str, status: int, payload: dict) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(status, json=payload, request=request)


@pytest.mark.asyncio
async def test_openai_generate_calls_expected_endpoint_and_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    image_bytes = _png_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            calls.append({"method": "POST", "url": url, "headers": headers or {}, "json": json})
            return _json_response(
                "POST",
                url,
                200,
                {"created": 123, "data": [{"b64_json": image_b64, "revised_prompt": "rp"}]},
            )

    monkeypatch.setattr("app.providers.openai_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = OpenAIAdapter()
    settings = Settings(openai_api_key="openai-key", openai_base_url="https://api.openai.test/v1")
    request = ProviderGenerationRequest(
        prompt="A mountain",
        width=640,
        height=480,
        n_images=1,
        seed=7,
        output_format="png",
        model="gpt-image-1",
        params={"quality": "high"},
    )

    result = await adapter.generate(request, settings)

    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://api.openai.test/v1/images/generations"
    assert call["headers"]["Authorization"] == "Bearer openai-key"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["json"]["model"] == "gpt-image-1"
    assert call["json"]["prompt"] == "A mountain"
    assert call["json"]["n"] == 1
    assert call["json"]["size"] == "640x480"
    assert call["json"]["output_format"] == "png"
    assert call["json"]["quality"] == "high"
    assert len(result.images) == 1
    assert result.images[0].width == 640
    assert result.images[0].height == 480


@pytest.mark.asyncio
async def test_openrouter_generate_calls_expected_endpoint_and_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    output_bytes = _png_bytes(20, 10)
    output_b64 = base64.b64encode(output_bytes).decode("ascii")
    output_data_url = f"data:image/png;base64,{output_b64}"
    input_bytes = _png_bytes(8, 8)

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            calls.append({"method": "POST", "url": url, "headers": headers or {}, "json": json})
            return _json_response(
                "POST",
                url,
                200,
                {
                    "id": "or-1",
                    "model": "openrouter/model",
                    "choices": [{"message": {"images": [{"image_url": {"url": output_data_url}}]}}],
                },
            )

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            calls.append({"method": "GET", "url": url, "headers": headers or {}, "json": None})
            return _json_response("GET", url, 404, {"error": {"message": "unexpected"}})

    monkeypatch.setattr("app.providers.openrouter_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = OpenRouterAdapter()
    settings = Settings(
        app_name="Lumigen",
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/api/v1",
    )
    request = ProviderGenerationRequest(
        prompt="Draw a robot",
        width=1024,
        height=768,
        n_images=1,
        seed=99,
        output_format="png",
        model="openrouter/model",
        input_images=[ProviderInputImage(data=input_bytes, mime="image/png")],
    )

    result = await adapter.generate(request, settings)

    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://openrouter.test/api/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer or-key"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["headers"]["X-Title"] == "Lumigen"

    payload = call["json"]
    assert payload["model"] == "openrouter/model"
    assert payload["stream"] is False
    assert payload["seed"] == 99
    assert payload["size"] == "1024x768"
    assert payload["modalities"] == ["image", "text"]
    assert isinstance(payload["messages"], list)
    content = payload["messages"][0]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert len(result.images) == 1
    assert result.images[0].width == 20
    assert result.images[0].height == 10


@pytest.mark.asyncio
async def test_bfl_generate_calls_submit_and_polling_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    sample_bytes = _png_bytes(18, 14)
    sample_b64 = base64.b64encode(sample_bytes).decode("ascii")

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            calls.append({"method": "POST", "url": url, "headers": headers or {}, "json": json})
            return _json_response(
                "POST",
                url,
                200,
                {"id": "req-123", "polling_url": "https://poll.bfl.test/result/req-123"},
            )

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            calls.append({"method": "GET", "url": url, "headers": headers or {}, "json": None})
            return _json_response(
                "GET",
                url,
                200,
                {"status": "Ready", "result": {"sample": sample_b64}},
            )

    async def fast_sleep(_duration: float) -> None:
        return None

    monkeypatch.setattr("app.providers.bfl_adapter.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("app.providers.bfl_adapter.asyncio.sleep", fast_sleep)
    monkeypatch.setattr(BFLAdapter, "_write_debug_log", lambda self, prefix, data: None)

    adapter = BFLAdapter()
    settings = Settings(bfl_api_key="bfl-key")
    request = ProviderGenerationRequest(
        prompt="A city skyline",
        width=512,
        height=512,
        n_images=1,
        seed=123,
        output_format="png",
        model="flux-pro-1.1",
        params={"guidance": 3.5},
    )

    result = await adapter.generate(request, settings)

    assert len(calls) == 2
    submit_call, poll_call = calls

    assert submit_call["method"] == "POST"
    assert submit_call["url"] == "https://api.bfl.ai/v1/flux-pro-1.1"
    assert submit_call["headers"]["x-key"] == "bfl-key"
    assert submit_call["headers"]["Content-Type"] == "application/json"
    assert submit_call["json"]["prompt"] == "A city skyline"
    assert submit_call["json"]["width"] == 512
    assert submit_call["json"]["height"] == 512
    assert submit_call["json"]["seed"] == 123
    assert submit_call["json"]["guidance"] == 3.5

    assert poll_call["method"] == "GET"
    assert poll_call["url"] == "https://poll.bfl.test/result/req-123"
    assert poll_call["headers"]["accept"] == "application/json"

    assert len(result.images) == 1
    assert result.images[0].width == 18
    assert result.images[0].height == 14


@pytest.mark.asyncio
async def test_openai_list_models_calls_models_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def get(self, url, headers=None):  # type: ignore[no-untyped-def]
            calls.append({"method": "GET", "url": url, "headers": headers or {}})
            return _json_response(
                "GET",
                url,
                200,
                {"data": [{"id": "gpt-image-1"}, {"id": "text-model"}]},
            )

    monkeypatch.setattr("app.providers.openai_adapter.httpx.AsyncClient", FakeAsyncClient)

    adapter = OpenAIAdapter()
    settings = Settings(openai_api_key="openai-key", openai_base_url="https://api.openai.test/v1")
    models = await adapter.list_models(settings)

    assert len(calls) == 1
    assert calls[0]["url"] == "https://api.openai.test/v1/models"
    assert calls[0]["headers"]["Authorization"] == "Bearer openai-key"
    assert models == ["gpt-image-1"]
