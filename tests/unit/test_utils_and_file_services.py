from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image

from app.services.sidecar_service import SidecarService
from app.services.storage_service import StorageService
from app.services.thumbnail_service import ThumbnailService
from app.utils.jsonutil import dumps_json
from app.utils.paths import ensure_within_base
from app.utils.slugify import slugify


def test_slugify_normalizes_and_falls_back() -> None:
    assert slugify("  Héllo, Wörld!  ") == "hello-world"
    assert slugify("###", fallback="fallback") == "fallback"


def test_ensure_within_base_blocks_escaping_paths(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir(parents=True, exist_ok=True)
    inside = ensure_within_base(base_dir / "nested" / "file.txt", base_dir)
    assert inside.is_relative_to(base_dir.resolve())

    with pytest.raises(ValueError):
        ensure_within_base(base_dir / ".." / "outside.txt", base_dir)


def test_dumps_json_encodes_dates_decimal_and_path() -> None:
    payload = {
        "dt": datetime(2026, 2, 26, 12, 30, 0),
        "d": date(2026, 2, 26),
        "amount": Decimal("12.5"),
        "path": Path("foo/bar.txt"),
    }
    compact = dumps_json(payload)
    pretty = dumps_json(payload, pretty=True)

    assert '"dt":"2026-02-26T12:30:00"' in compact
    assert '"d":"2026-02-26"' in compact
    assert '"amount":12.5' in compact
    assert '"path":"foo/bar.txt"' in compact
    assert "\n" in pretty


def test_storage_render_relative_path_and_validations() -> None:
    service = StorageService(max_slug_length=32)
    rendered = service.render_relative_path(
        template="/{profile}/{yyyy}/{mm}/{slug}-{gen_id}-{idx}.{ext}",
        profile_name="My Profile",
        prompt_user="A test prompt",
        generation_id=7,
        idx=2,
        ext="PNG",
        when=datetime(2026, 2, 26, 8, 0, 0),
    )
    assert rendered == Path("my-profile/2026/02/a-test-prompt-7-2.png")

    with pytest.raises(ValueError):
        service.render_relative_path(
            template="/foo/file.{ext}",
            profile_name="x",
            prompt_user="x",
            generation_id=1,
            idx=1,
            ext="bad/ext",
        )

    with pytest.raises(ValueError):
        service.render_relative_path(
            template="/../escape-{idx}.{ext}",
            profile_name="x",
            prompt_user="x",
            generation_id=1,
            idx=1,
            ext="png",
        )


def test_storage_move_relative_file(tmp_path: Path) -> None:
    base_dir = tmp_path / "images"
    source = base_dir / "a" / "source.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("payload", encoding="utf-8")

    service = StorageService()
    service.move_relative_file(base_dir, "a/source.txt", "b/target.txt")

    assert not source.exists()
    assert (base_dir / "b" / "target.txt").read_text(encoding="utf-8") == "payload"


def test_sidecar_failure_relative_path_uses_failures_tree() -> None:
    sidecar = SidecarService(StorageService())
    rel_path = sidecar.failure_sidecar_relative_path(
        profile_name="Open Router",
        generation_id=42,
        when=datetime(2026, 2, 26, 9, 15, 0),
    )
    assert rel_path == Path(".failures/2026/02/open-router-42.json")


def test_thumbnail_create_thumbnail_writes_webp(tmp_path: Path) -> None:
    base_dir = tmp_path / "images"
    image_rel = Path("in/sample.png")
    image_abs = base_dir / image_rel
    image_abs.parent.mkdir(parents=True, exist_ok=True)

    image = Image.new("RGB", (1024, 512), color=(100, 120, 150))
    image.save(image_abs, format="PNG")

    storage = StorageService()
    thumbnail_service = ThumbnailService(storage_service=storage, max_px=256)
    thumb_rel = thumbnail_service.create_thumbnail(base_dir, image_rel)
    thumb_abs = base_dir / thumb_rel

    assert thumb_rel == Path(".thumbs/in/sample.webp")
    assert thumb_abs.exists()

    with Image.open(thumb_abs) as thumb_img:
        assert max(thumb_img.size) <= 256


def test_storage_write_json_atomic_and_resolve_managed_path(tmp_path: Path) -> None:
    base_dir = tmp_path / "images"
    service = StorageService()

    rel = Path("meta/asset.json")
    abs_path = service.resolve_managed_path(base_dir, rel)
    service.write_json_atomic(abs_path, '{"ok":true}')

    assert abs_path.read_text(encoding="utf-8") == '{"ok":true}'
    with pytest.raises(ValueError):
        service.resolve_managed_path(base_dir, "../escape.json")


def test_storage_delete_relative_file_handles_missing_and_prunes(tmp_path: Path) -> None:
    base_dir = tmp_path / "images"
    service = StorageService()

    # missing file should be a no-op
    service.delete_relative_file(base_dir, "no/such/file.png")

    existing = base_dir / "nested" / "file.txt"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("x", encoding="utf-8")
    service.delete_relative_file(base_dir, "nested/file.txt")

    assert not existing.exists()
    assert not (base_dir / "nested").exists()


def test_storage_move_relative_file_edge_cases(tmp_path: Path) -> None:
    base_dir = tmp_path / "images"
    service = StorageService()

    same = base_dir / "a" / "same.txt"
    same.parent.mkdir(parents=True, exist_ok=True)
    same.write_text("same", encoding="utf-8")
    service.move_relative_file(base_dir, "a/same.txt", "a/same.txt")
    assert same.exists()

    # missing source should be a no-op
    service.move_relative_file(base_dir, "missing.txt", "target.txt")

    src = base_dir / "src.txt"
    dst = base_dir / "dst.txt"
    src.write_text("src", encoding="utf-8")
    dst.write_text("dst", encoding="utf-8")
    with pytest.raises(FileExistsError):
        service.move_relative_file(base_dir, "src.txt", "dst.txt")


def test_sidecar_write_asset_and_failure_sidecar(tmp_path: Path) -> None:
    base_dir = tmp_path / "images"
    storage = StorageService()
    sidecar = SidecarService(storage)

    asset_rel = Path("p/img.png")
    expected_asset_sidecar = Path("p/img.png.json")
    assert sidecar.asset_sidecar_relative_path(asset_rel) == expected_asset_sidecar

    written_asset_rel = sidecar.write_asset_sidecar(
        base_dir,
        asset_rel,
        {"k": "v"},
    )
    assert written_asset_rel == expected_asset_sidecar
    assert (base_dir / expected_asset_sidecar).exists()

    written_failure_rel = sidecar.write_failure_sidecar(
        base_dir,
        "Profile Name",
        99,
        {"error": "boom"},
    )
    assert written_failure_rel.as_posix().startswith(".failures/")
    assert (base_dir / written_failure_rel).exists()
