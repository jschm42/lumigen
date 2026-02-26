from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.db.models import Generation
from app.providers.base import (
    ProviderGenerationRequest,
    ProviderGenerationResult,
    ProviderImage,
)
from app.services.generation_service import GenerationCancelledError, GenerationService


class _SessionCtx:
    def __init__(self, session):  # type: ignore[no-untyped-def]
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False


class _FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, item) -> None:  # type: ignore[no-untyped-def]
        self.added.append(item)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def refresh(self, _item) -> None:
        return None


class _FakeStorageService:
    def __init__(self) -> None:
        self.writes = []
        self.deletes = []

    def render_relative_path(self, **kwargs):  # type: ignore[no-untyped-def]
        return Path(f"generated-{kwargs['idx']}.png")

    def resolve_managed_path(self, base_dir, relative_path):  # type: ignore[no-untyped-def]
        return Path(base_dir) / Path(relative_path)

    def write_bytes_atomic(self, abs_path, data):  # type: ignore[no-untyped-def]
        self.writes.append((Path(abs_path), bytes(data)))

    def delete_relative_file(self, base_dir, rel):  # type: ignore[no-untyped-def]
        self.deletes.append((Path(base_dir), str(rel)))


class _FakeThumbnailService:
    def __init__(self, raise_exc: Exception | None = None) -> None:
        self.raise_exc = raise_exc

    def create_thumbnail(self, _base_dir, _rel):  # type: ignore[no-untyped-def]
        if self.raise_exc:
            raise self.raise_exc
        return Path(".thumbs/generated-1.webp")


class _FakeSidecarService:
    def __init__(self) -> None:
        self.asset_calls = 0
        self.failure_calls = 0

    def write_asset_sidecar(self, _base_dir, _rel_path, _payload):  # type: ignore[no-untyped-def]
        self.asset_calls += 1
        return Path("generated-1.png.json")

    def write_failure_sidecar(self, _base_dir, _profile_name, _generation_id, _payload):  # type: ignore[no-untyped-def]
        self.failure_calls += 1
        return Path(".failures/2026/02/failure.json")


def _build_generation(status: str = "queued") -> Generation:
    return Generation(
        id=101,
        profile_id=1,
        profile_name="Profile A",
        prompt_user="user prompt",
        prompt_final="final prompt",
        provider="stub",
        model="stub-v1",
        status=status,
        error=None,
        profile_snapshot_json={},
        storage_template_snapshot_json={
            "base_dir": ".",
            "template": "/{profile}/{slug}-{gen_id}-{idx}.{ext}",
        },
        request_snapshot_json={
            "output_format": "png",
            "category_ids": [1],
            "upscale_model": None,
        },
        failure_sidecar_path=None,
    )


def _provider_request() -> ProviderGenerationRequest:
    return ProviderGenerationRequest(
        prompt="final prompt",
        width=512,
        height=512,
        n_images=1,
        seed=1,
        output_format="png",
        model="stub-v1",
        api_key="dummy",
    )


@pytest.mark.asyncio
async def test_run_generation_job_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    generation = _build_generation()
    session = _FakeSession()
    storage = _FakeStorageService()
    thumbs = _FakeThumbnailService()
    sidecars = _FakeSidecarService()

    class _Registry:
        async def generate(self, _provider, _request):  # type: ignore[no-untyped-def]
            return ProviderGenerationResult(
                images=[
                    ProviderImage(
                        data=b"image-bytes",
                        mime="image/png",
                        width=64,
                        height=64,
                        meta={"seed": 1},
                    )
                ],
                raw_meta={"request_id": "ok"},
            )

    service = GenerationService(
        settings=Settings(),
        registry=_Registry(),
        storage_service=storage,
        thumbnail_service=thumbs,
        sidecar_service=sidecars,
        model_config_service=None,
        upscale_service=None,
    )

    monkeypatch.setattr("app.services.generation_service.SessionLocal", lambda: _SessionCtx(session))
    monkeypatch.setattr("app.services.generation_service.ensure_dir", lambda _path: None)
    monkeypatch.setattr("app.services.generation_service.crud.get_generation", lambda _s, _id: generation)
    monkeypatch.setattr("app.services.generation_service.crud.list_categories_by_ids", lambda _s, _ids: [])
    monkeypatch.setattr(service, "_provider_request_from_generation", lambda _g: _provider_request())
    monkeypatch.setattr(service, "_raise_if_cancelled", lambda _s, _id: None)
    monkeypatch.setattr(
        service,
        "_normalize_image_for_output",
        lambda **_kwargs: (b"normalized", 64, 64, "image/png"),
    )

    await service.run_generation_job(generation.id)

    assert generation.status == "succeeded"
    assert generation.error is None
    assert generation.failure_sidecar_path is None
    assert session.commits == 2
    assert len(session.added) == 1
    assert storage.writes
    assert sidecars.asset_calls == 1


@pytest.mark.asyncio
async def test_run_generation_job_failure_cleans_up_and_writes_failure_sidecar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generation = _build_generation()
    session = _FakeSession()
    storage = _FakeStorageService()
    thumbs = _FakeThumbnailService(raise_exc=RuntimeError("thumbnail failed"))
    sidecars = _FakeSidecarService()

    class _Registry:
        async def generate(self, _provider, _request):  # type: ignore[no-untyped-def]
            return ProviderGenerationResult(
                images=[
                    ProviderImage(
                        data=b"image-bytes",
                        mime="image/png",
                        width=64,
                        height=64,
                        meta={"seed": 1},
                    )
                ],
                raw_meta={"request_id": "ok"},
            )

    service = GenerationService(
        settings=Settings(),
        registry=_Registry(),
        storage_service=storage,
        thumbnail_service=thumbs,
        sidecar_service=sidecars,
        model_config_service=None,
        upscale_service=None,
    )

    calls = {"count": 0}

    def _get_generation(_session, _generation_id):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        return generation

    monkeypatch.setattr("app.services.generation_service.SessionLocal", lambda: _SessionCtx(session))
    monkeypatch.setattr("app.services.generation_service.ensure_dir", lambda _path: None)
    monkeypatch.setattr("app.services.generation_service.crud.get_generation", _get_generation)
    monkeypatch.setattr("app.services.generation_service.crud.list_categories_by_ids", lambda _s, _ids: [])
    monkeypatch.setattr(service, "_provider_request_from_generation", lambda _g: _provider_request())
    monkeypatch.setattr(service, "_raise_if_cancelled", lambda _s, _id: None)
    monkeypatch.setattr(
        service,
        "_normalize_image_for_output",
        lambda **_kwargs: (b"normalized", 64, 64, "image/png"),
    )

    await service.run_generation_job(generation.id)

    assert generation.status == "failed"
    assert "thumbnail failed" in (generation.error or "")
    assert generation.failure_sidecar_path == ".failures/2026/02/failure.json"
    assert session.rollbacks == 1
    assert session.commits == 2
    assert sidecars.failure_calls == 1
    assert storage.deletes
    assert calls["count"] >= 2


@pytest.mark.asyncio
async def test_run_generation_job_cancelled_cleans_up_without_failure_sidecar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generation = _build_generation()
    session = _FakeSession()
    storage = _FakeStorageService()
    thumbs = _FakeThumbnailService(raise_exc=GenerationCancelledError("Canceled by user."))
    sidecars = _FakeSidecarService()

    class _Registry:
        async def generate(self, _provider, _request):  # type: ignore[no-untyped-def]
            return ProviderGenerationResult(
                images=[
                    ProviderImage(
                        data=b"image-bytes",
                        mime="image/png",
                        width=64,
                        height=64,
                        meta={"seed": 1},
                    )
                ],
                raw_meta={"request_id": "ok"},
            )

    service = GenerationService(
        settings=Settings(),
        registry=_Registry(),
        storage_service=storage,
        thumbnail_service=thumbs,
        sidecar_service=sidecars,
        model_config_service=None,
        upscale_service=None,
    )

    monkeypatch.setattr("app.services.generation_service.SessionLocal", lambda: _SessionCtx(session))
    monkeypatch.setattr("app.services.generation_service.ensure_dir", lambda _path: None)
    monkeypatch.setattr("app.services.generation_service.crud.get_generation", lambda _s, _id: generation)
    monkeypatch.setattr("app.services.generation_service.crud.list_categories_by_ids", lambda _s, _ids: [])
    monkeypatch.setattr(service, "_provider_request_from_generation", lambda _g: _provider_request())
    monkeypatch.setattr(service, "_raise_if_cancelled", lambda _s, _id: None)
    monkeypatch.setattr(
        service,
        "_normalize_image_for_output",
        lambda **_kwargs: (b"normalized", 64, 64, "image/png"),
    )

    await service.run_generation_job(generation.id)

    assert generation.status == "cancelled"
    assert generation.error == "Canceled by user."
    assert generation.failure_sidecar_path is None
    assert session.rollbacks == 1
    assert session.commits == 2
    assert sidecars.failure_calls == 0
    assert storage.deletes
