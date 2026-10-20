from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.config import Settings
from app.db.models import Asset, Generation
from app.providers.base import ProviderGenerationResult, ProviderImage
from app.services.generation_service import GenerationService
from app.services.thumbnail_service import ThumbnailService


def _create_sample_png_bytes(width: int = 100, height: int = 100) -> bytes:
    img = Image.new("RGB", (width, height), color="red")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _MockStorageService:
    def __init__(self) -> None:
        self.writes: dict[Path, bytes] = {}

    def resolve_managed_path(self, base_dir: Path, relative_path: str | Path) -> Path:
        return Path(base_dir) / Path(relative_path)

    def render_relative_path(self, **kwargs) -> Path:
        ext = kwargs.get("ext", "png")
        idx = kwargs.get("idx", 1)
        return Path(f"outputs/gen_{idx}.{ext}")

    def write_bytes_atomic(self, abs_path: Path, data: bytes) -> None:
        self.writes[Path(abs_path)] = bytes(data)


def test_thumbnail_service_is_video_path():
    assert ThumbnailService.is_video_path("movie.mp4") is True
    assert ThumbnailService.is_video_path("clip.WEBM") is True
    assert ThumbnailService.is_video_path(Path("nested/dir/video.mov")) is True
    assert ThumbnailService.is_video_path("photo.jpg") is False
    assert ThumbnailService.is_video_path("picture.png") is False
    assert ThumbnailService.is_video_path("graphic.webp") is False


def test_thumbnail_service_video_frame_extraction(tmp_path: Path):
    storage = _MockStorageService()
    thumb_service = ThumbnailService(storage_service=storage, max_px=128)
    video_rel = "videos/sample.mp4"
    video_abs = storage.resolve_managed_path(tmp_path, video_rel)
    video_abs.parent.mkdir(parents=True, exist_ok=True)
    video_abs.write_bytes(b"dummy video bytes")

    png_bytes = _create_sample_png_bytes(640, 360)

    with patch.object(thumb_service, "_extract_first_frame", return_value=png_bytes) as mock_extract:
        thumb_rel = thumb_service.create_thumbnail(tmp_path, video_rel)
        mock_extract.assert_called_once_with(video_abs)
        assert thumb_rel == Path(".thumbs/videos/sample.webp")

        thumb_abs = storage.resolve_managed_path(tmp_path, thumb_rel)
        assert thumb_abs in storage.writes
        written = storage.writes[thumb_abs]
        with Image.open(BytesIO(written)) as img:
            assert img.format == "WEBP"
            assert max(img.size) <= 128


def test_thumbnail_service_video_extraction_failure(tmp_path: Path):
    storage = _MockStorageService()
    thumb_service = ThumbnailService(storage_service=storage, max_px=128)
    video_rel = "videos/broken.mp4"
    video_abs = storage.resolve_managed_path(tmp_path, video_rel)
    video_abs.parent.mkdir(parents=True, exist_ok=True)
    video_abs.write_bytes(b"corrupt")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout=b"", stderr=b"ffmpeg error: invalid data")
        with pytest.raises(RuntimeError, match="ffmpeg frame extraction failed"):
            thumb_service.create_thumbnail(tmp_path, video_rel)


def test_generation_service_normalize_video():
    gen_service = GenerationService.__new__(GenerationService)
    video_bytes = b"fake-mp4-payload"
    data, w, h, mime = gen_service._normalize_image_for_output(
        data=video_bytes,
        output_format="png",
        fallback_mime="video/mp4",
        fallback_width=1920,
        fallback_height=1080,
    )
    assert data == video_bytes
    assert w == 1920
    assert h == 1080
    assert mime == "video/mp4"


def test_generation_service_video_detection_helpers():
    gen_service = GenerationService.__new__(GenerationService)

    img_video_mime = ProviderImage(data=b"123", mime="video/mp4", width=1280, height=720)
    assert gen_service._is_video_result(img_video_mime) is True

    img_video_meta = ProviderImage(data=b"123", mime="application/octet-stream", width=1280, height=720, meta={"media_type": "video"})
    assert gen_service._is_video_result(img_video_meta) is True

    img_normal = ProviderImage(data=b"123", mime="image/png", width=1024, height=1024)
    assert gen_service._is_video_result(img_normal) is False

    assert gen_service._video_extension_from_mime("video/mp4") == "mp4"
    assert gen_service._video_extension_from_mime("video/webm") == "webm"
    assert gen_service._video_extension_from_mime("video/quicktime") == "mov"
    assert gen_service._video_extension_from_mime("video/x-matroska") == "mkv"
    assert gen_service._video_extension_from_mime("application/unknown") == "mp4"


@pytest.mark.asyncio
async def test_generation_service_execute_video_generation(tmp_path: Path):
    storage = _MockStorageService()
    thumb_service = ThumbnailService(storage_service=storage, max_px=128)  # type: ignore[arg-type]

    class _FakeSession:
        def __init__(self):
            self.added = []
            self.commits = 0
            self.rollbacks = 0
            self.refreshed = []

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

        def refresh(self, obj):
            self.refreshed.append(obj)

    fake_session = _FakeSession()

    settings = Settings(
        data_dir=tmp_path / "data",
        sqlite_path=tmp_path / "data" / "app.db",
        provider_config_key="x" * 44,
    )

    registry = MagicMock()
    video_bytes = b"mp4-content-stream"
    from unittest.mock import AsyncMock
    registry.generate = AsyncMock(return_value=ProviderGenerationResult(
        images=[
            ProviderImage(
                data=video_bytes,
                mime="video/mp4",
                width=1280,
                height=720,
                meta={"provider": "seedance", "media_type": "video"},
            )
        ],
        raw_meta={"request_id": "seedance-123"},
    ))

    sidecar_service = MagicMock()
    sidecar_service.write_asset_sidecar.return_value = Path("outputs/gen_1.json")

    gen_service = GenerationService(
        settings=settings,
        registry=registry,
        storage_service=storage,  # type: ignore[arg-type]
        thumbnail_service=thumb_service,
        sidecar_service=sidecar_service,
        model_config_service=None,
        upscale_service=None,
        fal_upscale_service=None,
    )

    generation = Generation(
        id=99,
        status="queued",
        provider="seedance",
        model="seedance-2-0-260128",
        prompt_user="a drone flying through neon city",
        prompt_final="a drone flying through neon city",
        profile_snapshot_json={"name": "VideoProfile"},
        storage_template_snapshot_json={"template": "{generation_id}/gen_{idx}.{ext}", "base_dir": str(tmp_path)},
        request_snapshot_json={
            "output_format": "png",  # User or profile default might say png, but video MUST override to mp4
            "upscale_provider": "local",  # Upscaler should be skipped for video
            "upscale_model": "realesrgan",
            "params_json": {"media_type": "video"},
        },
    )

    with patch("app.services.generation_service.SessionLocal") as mock_session_local, \
         patch.object(gen_service, "_raise_if_cancelled"), \
         patch.object(gen_service, "_provider_request_from_generation"), \
         patch.object(gen_service, "_prepare_provider_request", side_effect=lambda s, req: req), \
         patch.object(thumb_service, "_extract_first_frame", return_value=_create_sample_png_bytes(320, 180)):

        mock_session_local.return_value.__enter__.return_value = fake_session
        mock_session_local.return_value.__exit__.return_value = False

        # Mock crud.get_generation
        with patch("app.db.crud.get_generation", return_value=generation), \
             patch("app.db.crud.list_categories_by_ids", return_value=[]):
            await gen_service._execute_generation_job(generation.id)

    assert generation.error is None
    assert generation.status == "succeeded"
    assert len(fake_session.added) == 1
    asset = fake_session.added[0]
    assert isinstance(asset, Asset)
    assert asset.mime == "video/mp4"
    assert asset.file_path.endswith(".mp4")
    assert asset.thumbnail_path.endswith(".webp")
    assert asset.width == 1280
    assert asset.height == 720
