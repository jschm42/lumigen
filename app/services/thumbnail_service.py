from __future__ import annotations

import shutil
import subprocess
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from app.services.storage_service import StorageService

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
_FFMPEG_FALLBACK_PATH = "/home/jean/.local/bin/ffmpeg"
_FFMPEG_TIMEOUT_SECONDS = 60.0


class ThumbnailService:
    """Service that generates WebP thumbnails for image and video assets."""

    def __init__(self, storage_service: StorageService, max_px: int = 384) -> None:
        self.storage_service = storage_service
        self.max_px = max_px

    def thumbnail_relative_path(self, image_relative_path: str | Path) -> Path:
        """Return the relative path for the thumbnail of *image_relative_path* (stored under ``.thumbs/``)."""
        image_rel = Path(image_relative_path)
        return Path(".thumbs") / image_rel.with_suffix(".webp")

    @staticmethod
    def is_video_path(path: str | Path) -> bool:
        """Return True if *path* has a known video file extension."""
        return Path(path).suffix.lower() in VIDEO_EXTENSIONS

    def create_thumbnail(self, base_dir: Path, image_relative_path: str | Path) -> Path:
        """Generate and write a WebP thumbnail for the asset at *image_relative_path*.

        For video files the first frame is extracted with ``ffmpeg``. Returns the
        thumbnail relative path.
        """
        image_abs = self.storage_service.resolve_managed_path(base_dir, image_relative_path)
        thumbnail_rel = self.thumbnail_relative_path(image_relative_path)
        thumbnail_abs = self.storage_service.resolve_managed_path(base_dir, thumbnail_rel)

        if self.is_video_path(image_abs):
            source_bytes = self._extract_first_frame(image_abs)
            with Image.open(BytesIO(source_bytes)) as source:
                buffer = self._render_thumbnail(source)
        else:
            with Image.open(image_abs) as source:
                buffer = self._render_thumbnail(source)

        self.storage_service.write_bytes_atomic(thumbnail_abs, buffer.getvalue())
        return thumbnail_rel

    def _render_thumbnail(self, source: Image.Image) -> BytesIO:
        transposed = ImageOps.exif_transpose(source)
        image = transposed.convert("RGB")
        image.thumbnail((self.max_px, self.max_px))
        buffer = BytesIO()
        image.save(buffer, format="WEBP", quality=85)
        return buffer

    @staticmethod
    def _extract_first_frame(video_abs: Path) -> bytes:
        """Return the first frame of *video_abs* as PNG bytes using ``ffmpeg``.

        Raises ``RuntimeError`` if ffmpeg fails or produces no output.
        """
        ffmpeg_bin = shutil.which("ffmpeg") or _FFMPEG_FALLBACK_PATH
        cmd = [
            ffmpeg_bin,
            "-ss", "00:00:00.000",
            "-i", str(video_abs),
            "-vframes", "1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-",
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                check=False,
                timeout=_FFMPEG_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"ffmpeg frame extraction failed: {exc}") from exc
        if proc.returncode != 0 or not proc.stdout:
            stderr = proc.stderr.decode("utf-8", errors="replace")[-500:]
            raise RuntimeError(f"ffmpeg frame extraction failed (exit {proc.returncode}): {stderr}")
        return proc.stdout
