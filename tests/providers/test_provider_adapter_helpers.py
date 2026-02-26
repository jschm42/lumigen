from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.providers.base import ProviderError, ProviderGenerationRequest
from app.providers.bfl_adapter import BFLAdapter
from app.providers.openai_adapter import OpenAIAdapter
from app.providers.openrouter_adapter import OpenRouterAdapter


def _png_bytes(size: tuple[int, int] = (12, 9)) -> bytes:
    image = Image.new("RGB", size, color=(80, 120, 160))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_openai_payload_and_format_helpers_cover_dalle_and_standard_paths() -> None:
    adapter = OpenAIAdapter()

    dalle_request = ProviderGenerationRequest(
        prompt="p",
        width=1024,
        height=1024,
        n_images=1,
        seed=None,
        output_format="jpg",
        model="dall-e-3",
        params={"quality": "high"},
    )
    dalle_payload = adapter._build_payload(dalle_request, output_format="jpeg")
    assert dalle_payload["response_format"] == "b64_json"
    assert "output_format" not in dalle_payload
    assert dalle_payload["quality"] == "high"

    standard_request = ProviderGenerationRequest(
        prompt="p",
        width=640,
        height=480,
        n_images=1,
        seed=None,
        output_format="webp",
        model="gpt-image-1",
    )
    standard_payload = adapter._build_payload(standard_request, output_format="webp")
    assert standard_payload["output_format"] == "webp"
    assert adapter._size_string(standard_request) == "640x480"
    assert adapter._resolve_dimensions(standard_request) == (640, 480)
    assert adapter._normalize_output_format("JPG") == "jpeg"
    assert adapter._normalize_output_format("invalid") == "png"
    assert adapter._mime_from_format("jpeg") == "image/jpeg"


def test_openai_extract_error_message_variants() -> None:
    adapter = OpenAIAdapter()
    req = httpx.Request("GET", "https://unit.test")

    response_dict = httpx.Response(
        400,
        json={"error": {"message": "detail"}},
        request=req,
    )
    assert adapter._extract_error_message(response_dict) == "detail"

    response_json = httpx.Response(400, json={"other": "x"}, request=req)
    assert "other" in adapter._extract_error_message(response_json)

    response_text = httpx.Response(500, text="plain error", request=req)
    assert adapter._extract_error_message(response_text) == "plain error"


def test_openrouter_helpers_extract_refs_and_retry_predicates() -> None:
    adapter = OpenRouterAdapter()

    ref_data = "data:image/png;base64," + base64.b64encode(_png_bytes()).decode("ascii")
    text = f"Here {ref_data} and ![img](https://a.example/img.png) plus https://a.example/img.png"
    refs = adapter._extract_refs_from_text(text)
    assert refs[0].startswith("data:image/png;base64,")
    assert refs[1] == "https://a.example/img.png"

    assert adapter._looks_like_base64_payload("A" * 64) is False
    assert (
        adapter._looks_like_base64_payload(
            base64.b64encode(_png_bytes((64, 64))).decode("ascii")
        )
        is True
    )

    with pytest.raises(ProviderError, match="valid base64 data URL"):
        adapter._decode_data_url("invalid", 1)

    req = httpx.Request("POST", "https://unit.test")
    modality_error = httpx.Response(
        400,
        json={"error": {"message": "No endpoints found that support the requested output modalities"}},
        request=req,
    )
    assert adapter._should_retry_with_image_only(modality_error, {"modalities": ["image", "text"]}) is True

    size_error = httpx.Response(
        400,
        json={"error": {"message": "size parameter is not supported"}},
        request=req,
    )
    assert adapter._should_retry_without_explicit_dimensions(size_error, {"size": "1024x1024"}) is True
    assert adapter._should_retry_empty_success_with_image_only({"modalities": ["image", "text"]}) is True
    assert adapter._should_retry_empty_success_with_image_only({"modalities": ["image"]}) is False

    summary = adapter._summarize_empty_image_response({"choices": [{"message": {"content": "x"}}]})
    assert "choices=" in summary


@pytest.mark.asyncio
async def test_openrouter_read_image_payload_http_and_data_paths() -> None:
    adapter = OpenRouterAdapter()

    class FakeClient:
        async def get(self, _url):
            req = httpx.Request("GET", "https://img.test")
            return httpx.Response(200, content=_png_bytes((14, 7)), headers={"content-type": "image/png"}, request=req)

    http_bytes, http_mime = await adapter._read_image_payload(FakeClient(), "https://img.test/a.png", 1)
    assert http_bytes
    assert http_mime == "image/png"

    data_url = "data:image/png;base64," + base64.b64encode(_png_bytes((5, 6))).decode("ascii")
    data_bytes, data_mime = await adapter._read_image_payload(FakeClient(), data_url, 2)
    assert data_bytes
    assert data_mime == "image/png"


def test_openrouter_build_payload_honors_image_config_dimensions() -> None:
    adapter = OpenRouterAdapter()
    request = ProviderGenerationRequest(
        prompt="prompt",
        width=1024,
        height=768,
        n_images=1,
        seed=7,
        output_format="png",
        model="m",
        params={"image_config": {"aspect_ratio": "16:9"}},
    )
    payload = adapter._build_payload(request)
    assert payload["seed"] == 7
    assert "size" not in payload
    assert payload["image_config"]["aspect_ratio"] == "16:9"


def test_bfl_helper_paths_for_payload_and_image_extraction(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = BFLAdapter()

    payload = adapter._build_payload(
        ProviderGenerationRequest(
            prompt="p",
            width=512,
            height=256,
            n_images=2,
            seed=42,
            output_format="webp",
            model="flux-pro-1.1",
            params={"guidance": 2.5},
        )
    )
    assert payload["width"] == 512
    assert payload["height"] == 256
    assert payload["num_images"] == 2
    assert payload["seed"] == 42
    assert payload["output_format"] == "webp"
    assert payload["guidance"] == 2.5

    # URL sample path
    sample_bytes = _png_bytes((18, 11))

    class FakeClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        def get(self, _url):
            req = httpx.Request("GET", "https://cdn.test/img.png")
            return httpx.Response(200, content=sample_bytes, request=req)

    monkeypatch.setattr("app.providers.bfl_adapter.httpx.Client", FakeClient)
    monkeypatch.setattr(BFLAdapter, "_write_debug_log", lambda self, prefix, data: None)

    request = ProviderGenerationRequest(
        prompt="p",
        width=100,
        height=50,
        n_images=1,
        seed=None,
        output_format="png",
        model="m",
    )
    images = adapter._extract_images_from_result(
        {"result": {"sample": "https://cdn.test/img.png"}},
        request,
    )
    assert len(images) == 1
    assert images[0].width == 18
    assert images[0].height == 11

    with pytest.raises(ProviderError, match="not a string"):
        adapter._extract_images_from_result({"result": {"sample": 123}}, request)

    assert adapter._probe_dimensions(b"not-an-image", 9, 8) == (9, 8)
    assert adapter._normalize_output_format("jpeg") == "jpeg"
    assert adapter._normalize_output_format("bad") == "png"
    assert adapter._mime_from_output_format("webp") == "image/webp"
