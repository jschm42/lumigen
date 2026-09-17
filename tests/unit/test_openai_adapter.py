"""Unit tests for the OpenAI provider adapter."""
from __future__ import annotations

from app.providers.base import ProviderGenerationRequest
from app.providers.openai_adapter import OpenAIAdapter


def test_openai_adapter_filters_internal_and_unknown_params():
    """Verify OpenAI adapter filters out profile metadata (such as description) from payload."""
    adapter = OpenAIAdapter()
    request = ProviderGenerationRequest(
        prompt="A futuristic neon portrait",
        model="gpt-image-2",
        width=1024,
        height=1024,
        n_images=1,
        seed=1234,
        output_format="png",
        params={
            "description": "A cyberpunk album cover",
            "resolution": "1K",
            "aspect_ratio": "1:1",
            "fal_aspect_ratio": "1:1",
            "quality": "hd",
            "style": "vivid",
        },
    )

    payload = adapter._build_payload(request, output_format="png")

    assert payload["model"] == "gpt-image-2"
    assert payload["prompt"] == "A futuristic neon portrait"
    assert payload["size"] == "1024x1024"
    assert payload["output_format"] == "png"
    # Allowed OpenAI parameters are preserved
    assert payload["quality"] == "hd"
    assert payload["style"] == "vivid"
    # Internal/profile metadata must be stripped
    assert "description" not in payload
    assert "resolution" not in payload
    assert "aspect_ratio" not in payload
    assert "fal_aspect_ratio" not in payload
