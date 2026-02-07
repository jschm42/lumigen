from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from app.services.storage_service import StorageService
from app.utils.jsonutil import dumps_json
from app.utils.slugify import slugify


class SidecarService:
    def __init__(self, storage_service: StorageService) -> None:
        self.storage_service = storage_service

    def asset_sidecar_relative_path(self, image_relative_path: Union[str, Path]) -> Path:
        image_rel = Path(image_relative_path)
        return Path(f"{image_rel.as_posix()}.json")

    def failure_sidecar_relative_path(self, profile_name: str, generation_id: int, when: Optional[datetime] = None) -> Path:
        ts = when or datetime.utcnow()
        safe_profile = slugify(profile_name, max_length=48)
        filename = f"{safe_profile}-{generation_id}.json"
        return Path(".failures") / f"{ts.year:04d}" / f"{ts.month:02d}" / filename

    def write_asset_sidecar(self, base_dir: Path, image_relative_path: Union[str, Path], payload: dict) -> Path:
        rel_path = self.asset_sidecar_relative_path(image_relative_path)
        abs_path = self.storage_service.resolve_managed_path(base_dir, rel_path)
        self.storage_service.write_json_atomic(abs_path, dumps_json(payload, pretty=True))
        return rel_path

    def write_failure_sidecar(self, base_dir: Path, profile_name: str, generation_id: int, payload: dict) -> Path:
        rel_path = self.failure_sidecar_relative_path(profile_name, generation_id)
        abs_path = self.storage_service.resolve_managed_path(base_dir, rel_path)
        self.storage_service.write_json_atomic(abs_path, dumps_json(payload, pretty=True))
        return rel_path
