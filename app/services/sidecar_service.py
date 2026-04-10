from __future__ import annotations

from datetime import datetime, timezone

# For Python < 3.12 compatibility
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc
from pathlib import Path

from app.services.storage_service import StorageService
from app.utils.jsonutil import dumps_json
from app.utils.slugify import slugify


class SidecarService:
    """Service that writes JSON sidecar files alongside generated images and failure records."""

    def __init__(self, storage_service: StorageService) -> None:
        self.storage_service = storage_service

    def asset_sidecar_relative_path(self, image_relative_path: str | Path) -> Path:
        """Return the relative path for an asset's JSON sidecar (``<image_path>.json``)."""
        image_rel = Path(image_relative_path)
        return Path(f"{image_rel.as_posix()}.json")

    def failure_sidecar_relative_path(self, profile_name: str, generation_id: int, when: datetime | None = None) -> Path:
        """Return the relative path for a failure sidecar under ``.failures/YYYY/MM/``."""
        ts = when or datetime.now(UTC)
        safe_profile = slugify(profile_name, max_length=48)
        filename = f"{safe_profile}-{generation_id}.json"
        return Path(".failures") / f"{ts.year:04d}" / f"{ts.month:02d}" / filename

    def write_asset_sidecar(self, base_dir: Path, image_relative_path: str | Path, payload: dict) -> Path:
        """Write *payload* as a pretty-printed JSON sidecar next to the image file. Returns the sidecar relative path."""
        rel_path = self.asset_sidecar_relative_path(image_relative_path)
        abs_path = self.storage_service.resolve_managed_path(base_dir, rel_path)
        self.storage_service.write_json_atomic(abs_path, dumps_json(payload, pretty=True))
        return rel_path

    def write_failure_sidecar(self, base_dir: Path, profile_name: str, generation_id: int, payload: dict) -> Path:
        """Write *payload* as a pretty-printed JSON failure sidecar. Returns the sidecar relative path."""
        rel_path = self.failure_sidecar_relative_path(profile_name, generation_id)
        abs_path = self.storage_service.resolve_managed_path(base_dir, rel_path)
        self.storage_service.write_json_atomic(abs_path, dumps_json(payload, pretty=True))
        return rel_path
