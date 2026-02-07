from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Optional, Union

from app.utils.paths import ensure_dir, ensure_within_base, prune_empty_directories
from app.utils.slugify import slugify


_EXT_RE = re.compile(r"^[a-z0-9]+$")


class StorageService:
    def __init__(self, max_slug_length: int = 64) -> None:
        self.max_slug_length = max_slug_length

    def render_relative_path(
        self,
        *,
        template: str,
        profile_name: str,
        prompt_user: str,
        generation_id: int,
        idx: int,
        ext: str,
        when: Optional[datetime] = None,
    ) -> Path:
        safe_ext = ext.lower().lstrip(".")
        if not _EXT_RE.match(safe_ext):
            raise ValueError(f"Invalid file extension: {ext}")

        now = when or datetime.utcnow()
        context = {
            "profile": slugify(profile_name, max_length=48),
            "yyyy": f"{now.year:04d}",
            "mm": f"{now.month:02d}",
            "dd": f"{now.day:02d}",
            "slug": slugify(prompt_user, max_length=self.max_slug_length),
            "gen_id": generation_id,
            "idx": idx,
            "ext": safe_ext,
        }

        rendered = template.format(**context).replace("\\", "/")
        relative_str = rendered.lstrip("/")
        relative_posix = PurePosixPath(relative_str)

        if ".." in relative_posix.parts:
            raise ValueError("Path traversal is not allowed in rendered storage template")

        return Path(*relative_posix.parts)

    def resolve_managed_path(self, base_dir: Path, relative_path: Union[str, Path]) -> Path:
        base = base_dir.resolve()
        candidate = (base / Path(relative_path)).resolve()
        return ensure_within_base(candidate, base)

    def write_bytes_atomic(self, absolute_path: Path, data: bytes) -> None:
        ensure_dir(absolute_path.parent)
        tmp_path = absolute_path.parent / f".{absolute_path.name}.{uuid.uuid4().hex}.tmp"
        with tmp_path.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, absolute_path)

    def write_json_atomic(self, absolute_path: Path, content: str) -> None:
        ensure_dir(absolute_path.parent)
        tmp_path = absolute_path.parent / f".{absolute_path.name}.{uuid.uuid4().hex}.tmp"
        with tmp_path.open("w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, absolute_path)

    def delete_relative_file(self, base_dir: Path, relative_path: Union[str, Path]) -> None:
        absolute_path = self.resolve_managed_path(base_dir, relative_path)
        if not absolute_path.exists():
            return
        absolute_path.unlink(missing_ok=True)
        prune_empty_directories(absolute_path.parent, base_dir.resolve())
