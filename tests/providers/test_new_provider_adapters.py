"""Request/response tests for the Stability, Replicate, Together, xAI and Ideogram adapters."""
from __future__ import annotations

import base64
import json
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.config import Settings
from app.providers import http_common
from app.providers.base import (
    ProviderConfigError,
    ProviderError,
    ProviderGenerationRequest,
    ProviderInputImage,
    ProviderRateLimitError,
)
from app.providers.ideogram_adapter import IdeogramAdapter
from app.providers.registry import ProviderRegistry
from app.providers.replicate_adapter import ReplicateAdapter
from app.providers.stability_adapter import StabilityAdapter
from app.providers.together_adapter import TogetherAdapter
from app.providers.xai_adapter import XAIAdapter


def _png(width: int = 32, height: int = 18) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(10, 120, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


PNG = _png()
PNG_B64 = base64.b64encode(PNG).decode("ascii")


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch):
    """Route all adapter HTTP calls through a handler set by each test."""
    state: dict = {"calls": [], "handler": None}

    def handle(request: httpx.Request) -> httpx.Response:
        state["calls"].append(request)
        return state["handler"](request)

    def fake_client(settings: Settings) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handle))

    monkeypatch.setattr(http_common, "make_client", fake_client)
    return state


def _request(**overrides) -> ProviderGenerationRequest:
    values = dict(
        prompt="A lighthouse at dusk",
        width=None,
        height=None,
        n_images=1,
        seed=None,
        output_format="png",
        model="model",
        api_key="secret",
        params={},
    )
    values.update(overrides)
    return ProviderGenerationRequest(**values)


def _multipart_fields(request: httpx.Request) -> str:
    return request.content.decode("latin-1")


@pytest.mark.asyncio
async def test_stability_sd3_multipart_and_seed_increment(transport):
    transport["handler"] = lambda req: httpx.Response(200, json={"image": PNG_B64, "finish_reason": "SUCCESS", "seed": 7})
    result = await StabilityAdapter().generate(
        _request(model="sd3.5-large", n_images=2, seed=100, aspect_ratio="16:9", negative_prompt="blur"),
        Settings(),
    )
    assert len(result.images) == 2
    assert (result.images[0].width, result.images[0].height) == (32, 18)
    first, second = transport["calls"]
    assert str(first.url) == "https://api.stability.ai/v2beta/stable-image/generate/sd3"
    assert first.headers["authorization"] == "Bearer secret"
    assert first.headers["accept"] == "application/json"
    body = _multipart_fields(first)
    for expected in ('name="model"', "sd3.5-large", 'name="aspect_ratio"', "16:9", "blur", "100"):
        assert expected in body
    assert "101" in _multipart_fields(second)


@pytest.mark.asyncio
async def test_stability_content_filter_and_core_reference(transport):
    transport["handler"] = lambda req: httpx.Response(200, json={"image": PNG_B64, "finish_reason": "CONTENT_FILTERED"})
    with pytest.raises(ProviderError, match="filtered"):
        await StabilityAdapter().generate(_request(model="ultra"), Settings())
    with pytest.raises(ProviderError, match="core"):
        await StabilityAdapter().generate(
            _request(model="core", input_images=[ProviderInputImage(data=PNG, mime="image/png")]), Settings()
        )


@pytest.mark.asyncio
async def test_together_payload_dimensions_and_rate_limit(transport):
    transport["handler"] = lambda req: httpx.Response(200, json={"id": "x", "data": [{"index": 0, "b64_json": PNG_B64}]})
    result = await TogetherAdapter().generate(
        _request(model="black-forest-labs/FLUX.1-schnell", aspect_ratio="16:9", params={"steps": 4, "evil": 1}),
        Settings(),
    )
    payload = json.loads(transport["calls"][0].content)
    assert str(transport["calls"][0].url) == "https://api.together.ai/v1/images/generations"
    assert payload["width"] > payload["height"] and payload["width"] % 16 == 0
    assert payload["steps"] == 4 and "evil" not in payload
    assert payload["response_format"] == "base64"
    assert len(result.images) == 1

    transport["handler"] = lambda req: httpx.Response(429, json={"error": {"message": "slow down"}})
    with pytest.raises(ProviderRateLimitError):
        await TogetherAdapter().generate(_request(model="m"), Settings())


@pytest.mark.asyncio
async def test_xai_generation_and_edit(transport):
    transport["handler"] = lambda req: httpx.Response(200, json={"data": [{"b64_json": PNG_B64}, {"b64_json": PNG_B64}]})
    result = await XAIAdapter().generate(
        _request(model="grok-imagine-image-2.0", n_images=2, aspect_ratio="4:5", params={"resolution": "2K"}),
        Settings(),
    )
    payload = json.loads(transport["calls"][0].content)
    assert payload["aspect_ratio"] == "3:4"  # nearest supported ratio
    assert payload["resolution"] == "2k" and payload["n"] == 2
    assert len(result.images) == 2

    await XAIAdapter().generate(
        _request(model="grok-imagine-image-2.0", input_images=[ProviderInputImage(data=PNG, mime="image/png")]),
        Settings(),
    )
    edit_call = transport["calls"][-1]
    assert str(edit_call.url).endswith("/v1/images/edits")
    assert json.loads(edit_call.content)["image"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_ideogram_downloads_and_skips_unsafe(transport):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(
                200,
                json={"data": [
                    {"url": "https://ideogram.test/img1.png", "is_image_safe": True, "seed": 5},
                    {"url": None, "is_image_safe": False},
                ]},
            )
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})

    transport["handler"] = handler
    result = await IdeogramAdapter().generate(
        _request(model="ideogram-v3-turbo", aspect_ratio="16:9", n_images=2), Settings()
    )
    post = transport["calls"][0]
    assert post.headers["api-key"] == "secret"
    body = _multipart_fields(post)
    assert "TURBO" in body and "16x9" in body
    assert len(result.images) == 1 and result.raw_meta["skipped_unsafe"] == 1

    with pytest.raises(ProviderError, match="Unknown Ideogram model"):
        await IdeogramAdapter().generate(_request(model="ideogram-v9"), Settings())


@pytest.mark.asyncio
async def test_replicate_polls_until_succeeded(transport, monkeypatch):
    monkeypatch.setattr("app.providers.replicate_adapter._POLL_INTERVAL_SECONDS", 0)
    polls = {"count": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(201, json={"id": "p1", "status": "starting", "urls": {"get": "https://api.replicate.com/v1/predictions/p1"}})
        if "predictions/p1" in str(req.url):
            polls["count"] += 1
            if polls["count"] < 2:
                return httpx.Response(200, json={"id": "p1", "status": "processing", "urls": {"get": str(req.url)}})
            return httpx.Response(200, json={"id": "p1", "status": "succeeded", "output": ["https://replicate.delivery/a.png"], "urls": {"get": str(req.url)}})
        assert req.headers["authorization"] == "Bearer secret"
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})

    transport["handler"] = handler
    result = await ReplicateAdapter().generate(
        _request(model="black-forest-labs/flux-schnell", aspect_ratio="3:2", params={"go_fast": True, "image_config": {}}),
        Settings(),
    )
    create = transport["calls"][0]
    assert str(create.url) == "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions"
    assert create.headers["prefer"] == "wait=60"
    body = json.loads(create.content)
    assert body["input"] == {"prompt": "A lighthouse at dusk", "aspect_ratio": "3:2", "go_fast": True}
    assert len(result.images) == 1 and polls["count"] == 2


@pytest.mark.asyncio
async def test_replicate_version_and_failure(transport):
    transport["handler"] = lambda req: httpx.Response(200, json={"id": "p", "status": "failed", "error": "NSFW"})
    with pytest.raises(ProviderError, match="NSFW"):
        await ReplicateAdapter().generate(_request(model="owner/model:abc123"), Settings())
    body = json.loads(transport["calls"][0].content)
    assert str(transport["calls"][0].url).endswith("/v1/predictions") and body["version"] == "abc123"


@pytest.mark.asyncio
async def test_missing_api_key_raises_config_error():
    with pytest.raises(ProviderConfigError):
        await XAIAdapter().generate(_request(api_key=None), Settings(xai_api_key=None))


def test_registry_maps_custom_keys_for_new_providers():
    registry = ProviderRegistry(Settings())
    for provider in ("stability", "replicate", "together", "xai", "ideogram", "byteplus"):
        assert provider in registry.provider_names()
        patched = registry._settings_for_provider(provider, "k-123")
        assert getattr(patched, f"{provider}_api_key") == "k-123"


@pytest.mark.asyncio
async def test_byteplus_seedream_payload_and_usage(transport):
    from app.providers.byteplus_adapter import BytePlusAdapter

    transport["handler"] = lambda req: httpx.Response(
        200,
        json={
            "model": "seedream-4-5-251128",
            "data": [{"b64_json": PNG_B64, "size": "2048x2048"}, {"error": {"code": "x", "message": "sensitive"}}],
            "usage": {"generated_images": 1, "output_tokens": 16384, "total_tokens": 16384},
        },
    )
    result = await BytePlusAdapter().generate(
        _request(
            model="seedream-4-5-251128",
            n_images=2,
            seed=3,
            aspect_ratio="16:9",
            params={"resolution": "2K"},
            input_images=[ProviderInputImage(data=PNG, mime="image/png")],
        ),
        Settings(),
    )
    call = transport["calls"][0]
    assert str(call.url) == "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations"
    payload = json.loads(call.content)
    width, height = (int(v) for v in payload["size"].split("x"))
    assert width > height and 3_500_000 < width * height < 4_700_000
    assert payload["sequential_image_generation"] == "auto"
    assert payload["sequential_image_generation_options"] == {"max_images": 2}
    assert payload["watermark"] is False and payload["seed"] == 3
    assert payload["image"].startswith("data:image/png;base64,")
    assert len(result.images) == 1
    assert result.raw_meta["partial_errors"] == ["sensitive"]
    assert result.raw_meta["usage"]["output_tokens"] == 16384


@pytest.mark.asyncio
async def test_byteplus_resolution_keyword_and_all_failed(transport):
    from app.providers.byteplus_adapter import BytePlusAdapter

    transport["handler"] = lambda req: httpx.Response(200, json={"data": [{"error": {"message": "blocked"}}]})
    with pytest.raises(ProviderError, match="blocked"):
        await BytePlusAdapter().generate(_request(model="seedream-4-0-250828", params={"resolution": "4K"}), Settings())
    payload = json.loads(transport["calls"][0].content)
    assert payload["size"] == "4K" and payload["sequential_image_generation"] == "disabled"
