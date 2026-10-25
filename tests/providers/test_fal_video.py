"""Tests for FAL.ai video model support (payload building and video result handling)."""
from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.providers.base import (
    ProviderError,
    ProviderGenerationRequest,
    ProviderInputImage,
)
from app.providers.fal_adapter import FalAdapter

VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42fal-video"


def _request(**overrides) -> ProviderGenerationRequest:
    values = dict(
        prompt="A cat surfing a wave",
        width=None,
        height=None,
        n_images=1,
        seed=None,
        output_format="png",
        model="fal-ai/kling-video/v1.5/pro",
        params={},
    )
    values.update(overrides)
    return ProviderGenerationRequest(**values)


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch):
    """Route FAL HTTP calls through a handler set by each test and skip poll sleeps."""
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

    monkeypatch.setattr("app.providers.fal_adapter.httpx.AsyncClient", fake_client)
    monkeypatch.setattr("app.providers.fal_adapter.asyncio.sleep", no_sleep)
    return state


def _video_handler(result_body: dict):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "POST":
            return httpx.Response(200, json={"request_id": "req-1"})
        if url.endswith("/requests/req-1/status"):
            return httpx.Response(200, json={"status": "COMPLETED"})
        if url.endswith("/requests/req-1"):
            return httpx.Response(200, json=result_body)
        if url.startswith("https://v.fal.media/"):
            return httpx.Response(200, content=VIDEO_BYTES)
        return httpx.Response(404)

    return handler


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("fal-ai/kling-video/v1.5/pro", True),
        ("fal-ai/minimax/video-01", True),
        ("fal-ai/luma-dream-machine", True),
        ("fal-ai/hunyuan-video", True),
        ("fal-ai/fast-svd", True),
        ("fal-ai/flux/schnell", False),
        ("fal-ai/stable-diffusion-xl", False),
    ],
)
def test_is_video_model(model: str, expected: bool) -> None:
    assert FalAdapter._is_video_model(model) is expected


def test_build_video_payload_includes_image_and_params_but_not_internal_keys() -> None:
    request = _request(
        aspect_ratio="16:9",
        seed=7,
        params={"duration": 5, "generate_audio": True, "media_type": "video", "category_ids": [1]},
        input_images=[ProviderInputImage(data=b"img", mime="image/png")],
    )
    payload = FalAdapter()._build_payload(request)

    assert payload["prompt"] == "A cat surfing a wave"
    assert payload["aspect_ratio"] == "16:9"
    assert payload["seed"] == 7
    assert payload["image_url"].startswith("data:image/png;base64,")
    assert payload["duration"] == 5
    assert payload["generate_audio"] is True
    assert "media_type" not in payload
    assert "category_ids" not in payload


@pytest.mark.asyncio
async def test_generate_returns_single_video(transport) -> None:  # type: ignore[no-untyped-def]
    transport["handler"] = _video_handler(
        {"video": {"url": "https://v.fal.media/out.mp4", "width": 1920, "height": 1080}}
    )
    result = await FalAdapter().generate(_request(), Settings(fal_api_key="fal-key"))

    assert len(result.images) == 1
    video = result.images[0]
    assert video.data == VIDEO_BYTES
    assert video.mime == "video/mp4"
    assert (video.width, video.height) == (1920, 1080)
    assert video.meta["media_type"] == "video"
    assert video.meta["video_url"] == "https://v.fal.media/out.mp4"
    submit = transport["calls"][0]
    assert json.loads(submit.content)["prompt"] == "A cat surfing a wave"


@pytest.mark.asyncio
async def test_generate_returns_videos_list_with_default_dimensions(transport) -> None:  # type: ignore[no-untyped-def]
    transport["handler"] = _video_handler(
        {"videos": [{"url": "https://v.fal.media/a.mp4"}, {"url": "https://v.fal.media/b.mp4"}]}
    )
    result = await FalAdapter().generate(_request(), Settings(fal_api_key="fal-key"))

    assert [v.meta["index"] for v in result.images] == [1, 2]
    assert all(v.mime == "video/mp4" for v in result.images)
    assert all((v.width, v.height) == (1280, 720) for v in result.images)


@pytest.mark.asyncio
async def test_video_model_accepts_input_images(transport) -> None:  # type: ignore[no-untyped-def]
    transport["handler"] = _video_handler({"video": {"url": "https://v.fal.media/out.mp4"}})
    request = _request(input_images=[ProviderInputImage(data=b"img", mime="image/png")])
    result = await FalAdapter().generate(request, Settings(fal_api_key="fal-key"))
    assert result.images[0].mime == "video/mp4"


@pytest.mark.asyncio
async def test_image_model_still_rejects_input_images() -> None:
    request = _request(
        model="fal-ai/flux/schnell",
        input_images=[ProviderInputImage(data=b"img", mime="image/png")],
    )
    with pytest.raises(ProviderError, match="does not support input images"):
        await FalAdapter().generate(request, Settings(fal_api_key="fal-key"))


@pytest.mark.asyncio
async def test_video_download_failure_raises_provider_error(transport) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith("https://v.fal.media/"):
            return httpx.Response(500)
        return _video_handler({"video": {"url": "https://v.fal.media/out.mp4"}})(request)

    transport["handler"] = handler
    with pytest.raises(ProviderError, match="Failed to fetch FAL video"):
        await FalAdapter().generate(_request(), Settings(fal_api_key="fal-key"))


@pytest.mark.asyncio
async def test_generate_uses_status_and_response_urls_from_submit_response(transport) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "request_id": "custom-req-1",
                    "status_url": "https://queue.fal.run/fal-ai/custom-parent/requests/custom-req-1/status",
                    "response_url": "https://queue.fal.run/fal-ai/custom-parent/requests/custom-req-1",
                },
            )
        if url == "https://queue.fal.run/fal-ai/custom-parent/requests/custom-req-1/status":
            return httpx.Response(200, json={"status": "COMPLETED"})
        if url == "https://queue.fal.run/fal-ai/custom-parent/requests/custom-req-1":
            return httpx.Response(
                200, json={"video": {"url": "https://v.fal.media/out.mp4", "width": 1280, "height": 720}}
            )
        if url.startswith("https://v.fal.media/"):
            return httpx.Response(200, content=VIDEO_BYTES)
        return httpx.Response(404)

    transport["handler"] = handler
    req = _request(model="fal-ai/custom-parent/sub-path/text-to-video")
    result = await FalAdapter().generate(req, Settings(fal_api_key="fal-key"))
    assert len(result.images) == 1
    assert result.images[0].mime == "video/mp4"


@pytest.mark.asyncio
async def test_generate_polls_response_url_when_status_url_returns_405(transport) -> None:  # type: ignore[no-untyped-def]
    status_calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "POST":
            return httpx.Response(200, json={"request_id": "req-405"})
        if url.endswith("/requests/req-405/status"):
            return httpx.Response(405)  # Method Not Allowed
        if url.endswith("/requests/req-405"):
            status_calls["count"] += 1
            if status_calls["count"] < 2:
                return httpx.Response(202)  # Still processing
            return httpx.Response(
                200, json={"video": {"url": "https://v.fal.media/out.mp4", "width": 1280, "height": 720}}
            )
        if url.startswith("https://v.fal.media/"):
            return httpx.Response(200, content=VIDEO_BYTES)
        return httpx.Response(404)

    transport["handler"] = handler
    req = _request()
    result = await FalAdapter().generate(req, Settings(fal_api_key="fal-key"))
    assert len(result.images) == 1
    assert result.images[0].mime == "video/mp4"


@pytest.mark.asyncio
async def test_image_to_video_requires_input_image() -> None:
    request = _request(
        model="fal-ai/kling-video/v2.5-turbo/standard/image-to-video",
        input_images=[],
    )
    with pytest.raises(ProviderError, match="image-to-video model and requires an input image"):
        await FalAdapter().generate(request, Settings(fal_api_key="fal-key"))

