from __future__ import annotations

from pathlib import Path


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_within_base(path: Path, base_dir: Path) -> Path:
    resolved_base = base_dir.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError(f"Path escapes managed base directory: {path}") from exc
    return resolved_path


def prune_empty_directories(start_dir: Path, base_dir: Path) -> None:
    resolved_base = base_dir.resolve()
    current = start_dir.resolve()
    while current != resolved_base:
        if not current.exists() or any(current.iterdir()):
            break
        current.rmdir()
        current = current.parent
