import base64
from io import BytesIO
from typing import Any

import httpx
import pytest
from PIL import Image

from app.config import Settings
from app.providers.base import (
    ProviderError,
    ProviderGenerationRequest,
    ProviderInputImage,
)
from app.providers.openrouter_adapter import OpenRouterAdapter


def _png_bytes(width: int = 16, height: int = 16) -> bytes:
    """Helper to generate valid PNG bytes with specific dimensions."""
    buf = BytesIO()
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_openrouter_fallback_to_images_endpoint_on_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that 404 indicating image generation model retries via /api/v1/images."""
    calls: list[dict[str, Any]] = []
    generated_png = _png_bytes(32, 48)
    b64_sample = base64.b64encode(generated_png).decode("ascii")

    class FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def post(self, url: str, **kwargs: Any) -> httpx.Response:
            calls.append({"url": url, **kwargs})
            req = httpx.Request("POST", url)
            # First call to /chat/completions fails with the 404 image model message
            if url.endswith("/chat/completions"):
                return httpx.Response(
                    404,
                    request=req,
                    json={
                        "error": {
                            "message": (
                                "openai/gpt-image-2.5-sunburst is an image generation model "
                                "and cannot be used with the chat/completions endpoint. "
                                "Use the /api/v1/images endpoint instead."
                            )
                        }
                    },
                )
            # Second call to /images succeeds
            return httpx.Response(
                200,
                request=req,
                json={
                    "id": "gen-123",
                    "created": 1788916368,
                    "model": "openai/gpt-image-2.5-sunburst",
                    "data": [{"b64_json": b64_sample}],
                },
            )

    monkeypatch.setattr(
        "app.providers.openrouter_adapter.httpx.AsyncClient", FakeAsyncClient
    )

    adapter = OpenRouterAdapter()
    settings = Settings(
        app_name="Lumigen",
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.test/api/v1",
    )
    request = ProviderGenerationRequest(
        prompt="Cyberpunk portrait",
        width=1024,
        height=1024,
        n_images=1,
        seed=42,
        output_format="png",
        model="openai/gpt-image-2.5-sunburst",
        params={"image_config": {"aspect_ratio": "2:3"}},
    )

    result = await adapter.generate(request, settings)

    assert len(calls) == 2
    assert calls[0]["url"] == "https://openrouter.test/api/v1/chat/completions"
    assert calls[1]["url"] == "https://openrouter.test/api/v1/images"

    images_payload = calls[1]["json"]
    assert images_payload["model"] == "openai/gpt-image-2.5-sunburst"
    assert images_payload["prompt"] == "Cyberpunk portrait"
    assert images_payload["aspect_ratio"] == "2:3"
    assert images_payload["seed"] == 42
    assert images_payload["n"] == 1

    assert len(result.images) == 1
    assert result.images[0].width == 32
    assert result.images[0].height == 48
    assert result.raw_meta["endpoint"] == "images"


@pytest.mark.asyncio
async def test_openrouter_images_api_with_input_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test input reference conversion for /api/v1/images payload."""
    calls: list[dict[str, Any]] = []
    generated_png = _png_bytes(20, 20)
    b64_sample = base64.b64encode(generated_png).decode("ascii")
    input_png = _png_bytes(10, 10)

    class FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def post(self, url: str, **kwargs: Any) -> httpx.Response:
            calls.append({"url": url, **kwargs})
            req = httpx.Request("POST", url)
            if url.endswith("/chat/completions"):
                return httpx.Response(
                    400,
                    request=req,
                    json={
                        "error": {
                            "message": "Use the /api/v1/images endpoint instead."
                        }
                    },
                )
            return httpx.Response(
                200,
                request=req,
                json={
                    "id": "gen-456",
                    "data": [{"b64_json": b64_sample}],
                },
            )

    monkeypatch.setattr(
        "app.providers.openrouter_adapter.httpx.AsyncClient", FakeAsyncClient
    )

    adapter = OpenRouterAdapter()
    settings = Settings(
        app_name="Lumigen",
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.test/api/v1",
    )
    request = ProviderGenerationRequest(
        prompt="Image edit",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="png",
        model="openai/gpt-image-2.5-sunburst",
        input_images=[ProviderInputImage(data=input_png, mime="image/png")],
    )

    result = await adapter.generate(request, settings)

    assert len(calls) == 2
    images_payload = calls[1]["json"]
    assert "input_references" in images_payload
    assert len(images_payload["input_references"]) == 1
    assert images_payload["input_references"][0]["type"] == "image_url"
    assert images_payload["input_references"][0]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )
    assert len(result.images) == 1


@pytest.mark.asyncio
async def test_openrouter_images_api_error_propagation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that errors returned by /api/v1/images are properly raised."""
    class FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def post(self, url: str, **kwargs: Any) -> httpx.Response:
            req = httpx.Request("POST", url)
            if url.endswith("/chat/completions"):
                return httpx.Response(
                    404,
                    request=req,
                    json={
                        "error": {
                            "message": "Use the /api/v1/images endpoint instead."
                        }
                    },
                )
            return httpx.Response(
                400,
                request=req,
                json={"error": {"message": "Invalid aspect ratio"}},
            )

    monkeypatch.setattr(
        "app.providers.openrouter_adapter.httpx.AsyncClient", FakeAsyncClient
    )

    adapter = OpenRouterAdapter()
    settings = Settings(
        app_name="Lumigen",
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.test/api/v1",
    )
    request = ProviderGenerationRequest(
        prompt="Failing request",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="png",
        model="openai/gpt-image-2.5-sunburst",
    )

    with pytest.raises(ProviderError, match="Invalid aspect ratio"):
        await adapter.generate(request, settings)
