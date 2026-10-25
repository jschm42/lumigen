from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.providers.base import ProviderImage
from app.providers.fal_adapter import FalAdapter
from app.services.generation_service import GenerationService
from app.services.thumbnail_service import ThumbnailService


class _MockStorageService:
    def __init__(self) -> None:
        self.writes: dict[Path, bytes] = {}

    def resolve_managed_path(self, base_dir: Path, relative_path: str | Path) -> Path:
        return Path(base_dir) / Path(relative_path)

    def render_relative_path(self, **kwargs) -> Path:
        ext = kwargs.get("ext", "svg")
        idx = kwargs.get("idx", 1)
        return Path(f"outputs/gen_{idx}.{ext}")

    def write_bytes_atomic(self, abs_path: Path, data: bytes) -> None:
        self.writes[Path(abs_path)] = bytes(data)


SAMPLE_SVG_BYTES = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480">'
    b'<circle cx="320" cy="240" r="100" fill="blue"/>'
    b"</svg>"
)

SAMPLE_VIEWBOX_SVG_BYTES = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600">'
    b'<rect width="800" height="600" fill="green"/>'
    b"</svg>"
)


def test_fal_adapter_normalize_output_format_svg():
    adapter = FalAdapter()
    assert adapter._normalize_output_format("svg") == "svg"
    assert adapter._normalize_output_format(".SVG") == "svg"
    assert adapter._normalize_output_format("png") == "png"
    assert adapter._normalize_output_format("jpeg") == "jpeg"


def test_fal_adapter_mime_from_content_type_svg():
    adapter = FalAdapter()
    assert adapter._mime_from_content_type("image/svg+xml", "jpeg") == "image/svg+xml"
    assert adapter._mime_from_content_type("text/xml; charset=utf-8", "svg") == "image/svg+xml"
    assert adapter._mime_from_content_type("image/svg", "png") == "image/svg+xml"


def test_fal_adapter_probe_dimensions_svg():
    adapter = FalAdapter()
    w, h = adapter._probe_dimensions(SAMPLE_SVG_BYTES, 100, 100)
    assert (w, h) == (640, 480)

    w2, h2 = adapter._probe_dimensions(SAMPLE_VIEWBOX_SVG_BYTES, 100, 100)
    assert (w2, h2) == (800, 600)

    # Invalid SVG should fall back to given dimensions
    w3, h3 = adapter._probe_dimensions(b"<not-svg></not-svg>", 300, 200)
    assert (w3, h3) == (300, 200)


def test_thumbnail_service_svg_handling(tmp_path: Path):
    storage = _MockStorageService()
    thumb_service = ThumbnailService(storage_service=storage)

    svg_rel = "images/vector_art.svg"
    svg_abs = storage.resolve_managed_path(tmp_path, svg_rel)
    svg_abs.parent.mkdir(parents=True, exist_ok=True)
    svg_abs.write_bytes(SAMPLE_SVG_BYTES)

    assert thumb_service.is_svg_path("vector.svg") is True
    assert thumb_service.is_svg_path("vector.SVG") is True
    assert thumb_service.is_svg_path("image.png") is False

    rel_thumb = thumb_service.thumbnail_relative_path(svg_rel)
    assert rel_thumb == Path(".thumbs/images/vector_art.svg")

    # Creating thumbnail should copy SVG bytes directly without Pillow error
    thumb_out = thumb_service.create_thumbnail(tmp_path, svg_rel)
    assert thumb_out == rel_thumb
    thumb_abs = storage.resolve_managed_path(tmp_path, thumb_out)
    assert storage.writes[thumb_abs] == SAMPLE_SVG_BYTES


def test_generation_service_svg_normalization():
    storage = _MockStorageService()
    gen_service = GenerationService(
        settings=MagicMock(),
        registry=MagicMock(),
        storage_service=storage,
        thumbnail_service=MagicMock(),
        sidecar_service=MagicMock(),
    )

    data, w, h, mime = gen_service._normalize_image_for_output(
        data=SAMPLE_SVG_BYTES,
        output_format="svg",
        fallback_mime="image/svg+xml",
        fallback_width=640,
        fallback_height=480,
    )
    assert data == SAMPLE_SVG_BYTES
    assert (w, h) == (640, 480)
    assert mime == "image/svg+xml"


def test_generation_service_is_svg_result():
    img_svg = ProviderImage(
        data=SAMPLE_SVG_BYTES,
        mime="image/svg+xml",
        width=640,
        height=480,
    )
    assert GenerationService._is_svg_result(img_svg) is True

    img_data_only = ProviderImage(
        data=SAMPLE_SVG_BYTES,
        mime="application/octet-stream",
        width=640,
        height=480,
    )
    assert GenerationService._is_svg_result(img_data_only) is True

    img_png = ProviderImage(
        data=b"\x89PNG\r\n\x1a\nfake",
        mime="image/png",
        width=100,
        height=100,
    )
    assert GenerationService._is_svg_result(img_png) is False
