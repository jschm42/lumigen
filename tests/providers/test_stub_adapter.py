from __future__ import annotations

import pytest
from PIL import Image

from app.config import Settings
from app.providers.base import ProviderGenerationRequest
from app.providers.stub_adapter import StubAdapter


@pytest.mark.asyncio
async def test_stub_adapter_list_models_returns_stub_v1() -> None:
    adapter = StubAdapter()
    models = await adapter.list_models(Settings())
    assert models == ["stub-v1"]


@pytest.mark.asyncio
async def test_stub_adapter_generate_uses_defaults_and_enforces_minimum_images() -> None:
    adapter = StubAdapter()
    request = ProviderGenerationRequest(
        prompt="Test",
        width=None,
        height=None,
        n_images=0,
        seed=123,
        output_format="png",
        model="stub-v1",
    )

    result = await adapter.generate(request, Settings())

    assert len(result.images) == 1
    image = result.images[0]
    assert image.width == 768
    assert image.height == 768
    assert image.mime == "image/png"
    assert image.meta["seed"] == 123
    assert result.raw_meta["adapter"] == "stub"


@pytest.mark.asyncio
async def test_stub_adapter_generate_jpeg_and_webp_mime_mapping() -> None:
    adapter = StubAdapter()

    jpeg_request = ProviderGenerationRequest(
        prompt="JPEG",
        width=64,
        height=32,
        n_images=1,
        seed=1,
        output_format="jpg",
        model="stub-v1",
    )
    webp_request = ProviderGenerationRequest(
        prompt="WEBP",
        width=64,
        height=32,
        n_images=1,
        seed=2,
        output_format="webp",
        model="stub-v1",
    )

    jpeg_result = await adapter.generate(jpeg_request, Settings())
    webp_result = await adapter.generate(webp_request, Settings())

    assert jpeg_result.images[0].mime == "image/jpeg"
    assert webp_result.images[0].mime == "image/webp"


@pytest.mark.asyncio
async def test_stub_adapter_generate_unknown_format_falls_back_to_png() -> None:
    adapter = StubAdapter()
    request = ProviderGenerationRequest(
        prompt="fallback",
        width=48,
        height=48,
        n_images=1,
        seed=7,
        output_format="tiff",
        model="stub-v1",
    )

    result = await adapter.generate(request, Settings())
    image = result.images[0]
    assert image.mime == "image/png"

    with Image.open(__import__("io").BytesIO(image.data)) as decoded:
        assert decoded.format == "PNG"


@pytest.mark.asyncio
async def test_stub_adapter_generate_without_seed_uses_random_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.providers.stub_adapter.random.randint", lambda _a, _b: 4242)
    adapter = StubAdapter()
    request = ProviderGenerationRequest(
        prompt="random seed",
        width=32,
        height=32,
        n_images=2,
        seed=None,
        output_format="png",
        model="stub-v1",
    )

    result = await adapter.generate(request, Settings())

    assert len(result.images) == 2
    assert all(item.meta["seed"] == 4242 for item in result.images)
    assert result.raw_meta["seed"] == 4242
