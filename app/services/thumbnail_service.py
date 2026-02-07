from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Union

from PIL import Image

from app.services.storage_service import StorageService


class ThumbnailService:
    def __init__(self, storage_service: StorageService, max_px: int = 384) -> None:
        self.storage_service = storage_service
        self.max_px = max_px

    def thumbnail_relative_path(self, image_relative_path: Union[str, Path]) -> Path:
        image_rel = Path(image_relative_path)
        return Path(".thumbs") / image_rel.with_suffix(".webp")

    def create_thumbnail(self, base_dir: Path, image_relative_path: Union[str, Path]) -> Path:
        image_abs = self.storage_service.resolve_managed_path(base_dir, image_relative_path)
        thumbnail_rel = self.thumbnail_relative_path(image_relative_path)
        thumbnail_abs = self.storage_service.resolve_managed_path(base_dir, thumbnail_rel)

        with Image.open(image_abs) as source:
            image = source.convert("RGB")
            image.thumbnail((self.max_px, self.max_px))
            buffer = BytesIO()
            image.save(buffer, format="WEBP", quality=85)

        self.storage_service.write_bytes_atomic(thumbnail_abs, buffer.getvalue())
        return thumbnail_rel
