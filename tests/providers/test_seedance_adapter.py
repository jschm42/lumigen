"""Tests for the ByteDance Seedance video adapter (BytePlus ModelArk)."""
from __future__ import annotations

import base64
import json

import httpx
import pytest

from app.config import Settings
from app.providers.base import (
    ProviderConfigError,
    ProviderError,
    ProviderGenerationRequest,
    ProviderInputImage,
    ProviderRateLimitError,
)
from app.providers.registry import ProviderRegistry
from app.providers.seedance_adapter import _KNOWN_MODELS, SeedanceAdapter

VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42fake-video"
VIDEO_URL = "https://cdn.example.com/out/video.mp4"
BASE_URL = "https://ark.example.com/api/v3"


def _request(**overrides) -> ProviderGenerationRequest:
    values = dict(
        prompt="A drone shot over a misty forest",
        width=None,
        height=None,
        n_images=1,
        seed=None,
        output_format="png",
        model="seedance-2-0-260128",
        params={},
    )
    values.update(overrides)
    return ProviderGenerationRequest(**values)


def _settings(**overrides) -> Settings:
    values = dict(seedance_api_key="sd-key", seedance_base_url=BASE_URL, byteplus_api_key=None)
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch):
    """Route Seedance HTTP calls through a handler set by each test and skip poll sleeps."""
    state: dict = {"calls": [], "handler": None}

    def handle(request: httpx.Request) -> httpx.Response:
        state["calls"].append(request)
        return state["handler"](request)

    real_client = httpx.AsyncClient

    def fake_client(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.pop("transport", None)
        return real_client(*args, transport=httpx.MockTransport(handle), **kwargs)

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.providers.seedance_adapter.httpx.AsyncClient", fake_client)
    monkeypatch.setattr("app.providers.seedance_adapter.asyncio.sleep", no_sleep)
    return state


def _happy_handler(statuses: list[str]):  # type: ignore[no-untyped-def]
    remaining = list(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "POST" and url.endswith("/contents/generations/tasks"):
            return httpx.Response(200, json={"id": "task-1"})
        if request.method == "GET" and url.endswith("/contents/generations/tasks/task-1"):
            status = remaining.pop(0) if remaining else "succeeded"
            body: dict = {"id": "task-1", "status": status}
            if status == "succeeded":
                body["content"] = {"video_url": VIDEO_URL}
            return httpx.Response(200, json=body)
        if url == VIDEO_URL:
            return httpx.Response(200, content=VIDEO_BYTES)
        return httpx.Response(404)

    return handler


# --- Model listing ---------------------------------------------------------


@pytest.mark.asyncio
async def test_list_models_returns_known_models_copy() -> None:
    adapter = SeedanceAdapter()
    models = await adapter.list_models(_settings())
    assert models == _KNOWN_MODELS
    models.append("mutated")
    assert "mutated" not in _KNOWN_MODELS


def test_registry_registers_seedance_adapter() -> None:
    registry = ProviderRegistry(_settings())
    assert isinstance(registry.get("seedance"), SeedanceAdapter)


# --- Payload building ------------------------------------------------------


def test_build_payload_defaults() -> None:
    payload = SeedanceAdapter()._build_payload(_request())
    assert payload == {
        "model": "seedance-2-0-260128",
        "content": [{"type": "text", "text": "A drone shot over a misty forest"}],
        "ratio": "16:9",
        "resolution": "720p",
        "duration": 5,
        "generate_audio": False,
        "watermark": False,
    }


def test_build_payload_uses_params_seed_and_input_image() -> None:
    request = _request(
        aspect_ratio="9:16",
        seed=42,
        params={"resolution": "1080P", "duration": "8", "generate_audio": True, "watermark": True},
        input_images=[ProviderInputImage(data=b"img", mime="image/png")],
    )
    payload = SeedanceAdapter()._build_payload(request)

    assert payload["ratio"] == "9:16"
    assert payload["resolution"] == "1080p"
    assert payload["duration"] == 8
    assert payload["generate_audio"] is True
    assert payload["watermark"] is True
    assert payload["seed"] == 42
    image_part = payload["content"][1]
    assert image_part["type"] == "image_url"
    assert image_part["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(b"img").decode()


def test_build_payload_invalid_values_fall_back() -> None:
    request = _request(aspect_ratio="7:5", params={"resolution": "4k", "duration": "long"})
    payload = SeedanceAdapter()._build_payload(request)
    assert payload["ratio"] == "16:9"
    assert payload["resolution"] == "720p"
    assert payload["duration"] == 5


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [(1920, 1080, "16:9"), (1080, 1920, "9:16"), (1024, 768, "4:3"), (768, 1024, "3:4"), (512, 512, "1:1")],
)
def test_resolve_ratio_from_dimensions(width: int, height: int, expected: str) -> None:
    request = _request(width=width, height=height)
    assert SeedanceAdapter()._resolve_ratio(request) == expected


def test_resolve_ratio_reads_params_when_no_aspect_ratio() -> None:
    request = _request(params={"ratio": "21:9"})
    assert SeedanceAdapter()._resolve_ratio(request) == "21:9"


# --- Generation / video extraction -----------------------------------------


@pytest.mark.asyncio
async def test_generate_polls_and_downloads_video(transport) -> None:  # type: ignore[no-untyped-def]
    transport["handler"] = _happy_handler(["queued", "running", "succeeded"])
    request = _request(aspect_ratio="9:16", params={"resolution": "1080p"})

    result = await SeedanceAdapter().generate(request, _settings())

    assert len(result.images) == 1
    video = result.images[0]
    assert video.data == VIDEO_BYTES
    assert video.mime == "video/mp4"
    assert (video.width, video.height) == (1080, 1920)
    assert video.meta["media_type"] == "video"
    assert video.meta["video_url"] == VIDEO_URL
    assert result.raw_meta["media_type"] == "video"
    assert result.raw_meta["task_id"] == "task-1"

    submit = transport["calls"][0]
    assert submit.headers["Authorization"] == "Bearer sd-key"
    assert str(submit.url) == f"{BASE_URL}/contents/generations/tasks"
    assert json.loads(submit.content)["resolution"] == "1080p"
    poll_calls = [c for c in transport["calls"] if c.url.path.endswith("/task-1")]
    assert len(poll_calls) == 3


@pytest.mark.asyncio
async def test_extract_video_accepts_list_content(transport) -> None:  # type: ignore[no-untyped-def]
    transport["handler"] = _happy_handler([])
    async with httpx.AsyncClient() as client:
        videos = await SeedanceAdapter()._extract_video(
            {"content": [{"video_url": VIDEO_URL}]}, _request(), client
        )
    assert videos[0].data == VIDEO_BYTES
    assert (videos[0].width, videos[0].height) == (1280, 720)


@pytest.mark.asyncio
async def test_extract_video_without_url_raises() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderError, match="no video_url"):
            await SeedanceAdapter()._extract_video({"content": {}}, _request(), client)


@pytest.mark.asyncio
async def test_generate_falls_back_to_byteplus_key(transport) -> None:  # type: ignore[no-untyped-def]
    transport["handler"] = _happy_handler(["succeeded"])
    await SeedanceAdapter().generate(_request(), _settings(seedance_api_key=None, byteplus_api_key="bp-key"))
    assert transport["calls"][0].headers["Authorization"] == "Bearer bp-key"


@pytest.mark.asyncio
async def test_generate_without_any_key_raises_config_error() -> None:
    with pytest.raises(ProviderConfigError):
        await SeedanceAdapter().generate(_request(), _settings(seedance_api_key=None))


@pytest.mark.asyncio
async def test_generate_429_raises_rate_limit(transport) -> None:  # type: ignore[no-untyped-def]
    transport["handler"] = lambda _r: httpx.Response(429, json={"error": {"message": "slow down"}})
    with pytest.raises(ProviderRateLimitError):
        await SeedanceAdapter().generate(_request(), _settings())


@pytest.mark.asyncio
async def test_generate_failed_task_raises_with_message(transport) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"id": "task-1"})
        return httpx.Response(200, json={"status": "failed", "error": {"message": "content policy"}})

    transport["handler"] = handler
    with pytest.raises(ProviderError, match="content policy"):
        await SeedanceAdapter().generate(_request(), _settings())


@pytest.mark.asyncio
async def test_generate_400_surfaces_error_message(transport) -> None:  # type: ignore[no-untyped-def]
    transport["handler"] = lambda _r: httpx.Response(400, json={"error": {"message": "bad ratio"}})
    with pytest.raises(ProviderError, match="bad ratio"):
        await SeedanceAdapter().generate(_request(), _settings())
