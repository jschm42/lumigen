from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.config import Settings
from app.db.models import Asset, Generation
from app.providers.base import ProviderError
from app.services.generation_service import GenerationCancelledError, GenerationService


def _image_bytes(mode: str = "RGB", size: tuple[int, int] = (12, 8), fmt: str = "PNG") -> bytes:
    image = Image.new(mode, size, color=(100, 120, 140, 255) if mode == "RGBA" else (100, 120, 140))
    buffer = BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def _service_with_model_config(model_config_service) -> GenerationService:
    return GenerationService(
        settings=Settings(),
        registry=SimpleNamespace(),
        storage_service=SimpleNamespace(),
        thumbnail_service=SimpleNamespace(),
        sidecar_service=SimpleNamespace(),
        model_config_service=model_config_service,
        upscale_service=None,
    )


def test_provider_request_from_generation_uses_custom_model_key() -> None:
    model_config_service = SimpleNamespace(
        get_model_config=lambda _id: SimpleNamespace(use_custom_api_key=True),
        get_api_key=lambda _id: "custom-key",
        get_default_api_key=lambda _provider: "env-key",
    )
    service = _service_with_model_config(model_config_service)
    image_b64 = base64.b64encode(_image_bytes()).decode("ascii")
    generation = Generation(
        profile_name="P",
        prompt_user="u",
        prompt_final="f",
        provider="openai",
        model="gpt-image-1",
        status="queued",
        profile_snapshot_json={},
        storage_template_snapshot_json={},
        request_snapshot_json={
            "model": "gpt-image-1",
            "provider": "openai",
            "model_config_id": 7,
            "output_format": "png",
            "n_images": 2,
            "input_images": [
                {"mime": "image/png", "b64": image_b64},
                {"mime": "image/png", "b64": "not-base64"},
            ],
        },
    )

    request = service._provider_request_from_generation(generation)

    assert request.api_key == "custom-key"
    assert request.model == "gpt-image-1"
    assert request.n_images == 2
    assert len(request.input_images) == 1


def test_provider_request_from_generation_uses_default_key_when_no_custom() -> None:
    model_config_service = SimpleNamespace(
        get_model_config=lambda _id: SimpleNamespace(use_custom_api_key=False),
        get_api_key=lambda _id: None,
        get_default_api_key=lambda provider: f"{provider}-env-key",
    )
    service = _service_with_model_config(model_config_service)
    generation = Generation(
        profile_name="P",
        prompt_user="u",
        prompt_final="f",
        provider="openrouter",
        model="or-model",
        status="queued",
        profile_snapshot_json={},
        storage_template_snapshot_json={},
        request_snapshot_json={
            "provider": "openrouter",
            "model": "or-model",
            "model_config_id": 5,
            "output_format": "png",
        },
    )

    request = service._provider_request_from_generation(generation)
    assert request.api_key == "openrouter-env-key"


def test_provider_request_from_generation_missing_model_or_api_key_raises() -> None:
    model_config_service = SimpleNamespace(
        get_model_config=lambda _id: SimpleNamespace(use_custom_api_key=False),
        get_api_key=lambda _id: None,
        get_default_api_key=lambda _provider: None,
    )
    service = _service_with_model_config(model_config_service)

    generation_no_model = Generation(
        profile_name="P",
        prompt_user="u",
        prompt_final="f",
        provider="openai",
        model="",
        status="queued",
        profile_snapshot_json={},
        storage_template_snapshot_json={},
        request_snapshot_json={"provider": "openai", "model": ""},
    )
    with pytest.raises(ProviderError, match="no model"):
        service._provider_request_from_generation(generation_no_model)

    generation_no_key = Generation(
        profile_name="P",
        prompt_user="u",
        prompt_final="f",
        provider="openai",
        model="gpt-image-1",
        status="queued",
        profile_snapshot_json={},
        storage_template_snapshot_json={},
        request_snapshot_json={"provider": "openai", "model": "gpt-image-1"},
    )
    with pytest.raises(ProviderError, match="API key"):
        service._provider_request_from_generation(generation_no_key)


def test_build_asset_sidecar_payload_sanitizes_input_images() -> None:
    service = _service_with_model_config(
        SimpleNamespace(
            get_model_config=lambda _id: None,
            get_api_key=lambda _id: None,
            get_default_api_key=lambda _provider: "x",
        )
    )
    generation = Generation(
        id=11,
        profile_name="Profile",
        prompt_user="u",
        prompt_final="f",
        provider="stub",
        model="stub-v1",
        status="queued",
        profile_snapshot_json={"a": 1},
        storage_template_snapshot_json={"base_dir": "."},
        request_snapshot_json={
            "input_images": [{"name": "a", "mime": "image/png", "b64": "abc"}],
        },
    )

    payload = service._build_asset_sidecar_payload(
        generation=generation,
        asset_index=1,
        image_rel="p/a.png",
        thumbnail_rel=".thumbs/p/a.webp",
        provider_meta={"i": 1},
        raw_meta={"r": 2},
        image_width=100,
        image_height=80,
        image_mime="image/png",
    )

    assert payload["type"] == "asset_success"
    sanitized = payload["request_snapshot_json"]["input_images"][0]
    assert sanitized["name"] == "a"
    assert sanitized["mime"] == "image/png"
    assert "b64" not in sanitized


def test_normalize_image_for_output_converts_rgba_to_jpeg_and_raises_on_invalid_data() -> None:
    service = _service_with_model_config(
        SimpleNamespace(
            get_model_config=lambda _id: None,
            get_api_key=lambda _id: "x",
            get_default_api_key=lambda _provider: "x",
        )
    )

    jpeg_bytes, width, height, mime = service._normalize_image_for_output(
        data=_image_bytes(mode="RGBA", size=(21, 13), fmt="PNG"),
        output_format="jpeg",
        fallback_mime="image/png",
        fallback_width=1,
        fallback_height=1,
    )
    assert jpeg_bytes
    assert width == 21
    assert height == 13
    assert mime == "image/jpeg"

    with pytest.raises(ProviderError, match="Failed to process image"):
        service._normalize_image_for_output(
            data=b"not-an-image",
            output_format="png",
            fallback_mime="image/png",
            fallback_width=1,
            fallback_height=1,
        )


def test_delete_asset_and_delete_generation_remove_files_and_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    delete_calls: list[str] = []
    storage_service = SimpleNamespace(
        delete_relative_file=lambda _base_dir, rel: delete_calls.append(str(rel))
    )
    service = GenerationService(
        settings=Settings(),
        registry=SimpleNamespace(),
        storage_service=storage_service,
        thumbnail_service=SimpleNamespace(),
        sidecar_service=SimpleNamespace(),
        model_config_service=None,
        upscale_service=None,
    )

    class FakeSession:
        def __init__(self) -> None:
            self.deleted = []
            self.commits = 0

        def delete(self, item) -> None:  # type: ignore[no-untyped-def]
            self.deleted.append(item)

        def commit(self) -> None:
            self.commits += 1

    session = FakeSession()

    generation = Generation(
        id=2,
        profile_name="P",
        prompt_user="u",
        prompt_final="f",
        provider="stub",
        model="stub-v1",
        status="queued",
        profile_snapshot_json={},
        storage_template_snapshot_json={"base_dir": "."},
        request_snapshot_json={},
        failure_sidecar_path=".failures/f.json",
    )
    asset = Asset(
        id=5,
        generation_id=2,
        file_path="a.png",
        sidecar_path="a.png.json",
        thumbnail_path=".thumbs/a.webp",
        width=1,
        height=1,
        mime="image/png",
    )
    asset.generation = generation
    generation.assets = [asset]

    monkeypatch.setattr("app.services.generation_service.crud.get_asset", lambda _s, _id, with_generation=True: asset)
    monkeypatch.setattr("app.services.generation_service.crud.get_generation", lambda _s, _id, with_assets=True: generation)

    assert service.delete_asset(session, 5) is True
    assert service.delete_generation(session, 2) is True
    assert session.commits == 2
    assert len(session.deleted) == 2
    assert "a.png" in delete_calls
    assert ".thumbs/a.webp" in delete_calls
    assert "a.png.json" in delete_calls
    assert ".failures/f.json" in delete_calls


def test_create_generation_from_profile_builds_snapshots_and_applies_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_create_generation(_session, generation):  # type: ignore[no-untyped-def]
        generation.id = 77
        captured["generation"] = generation
        return generation

    monkeypatch.setattr("app.services.generation_service.crud.create_generation", fake_create_generation)

    service = GenerationService(
        settings=Settings(),
        registry=SimpleNamespace(),
        storage_service=SimpleNamespace(),
        thumbnail_service=SimpleNamespace(),
        sidecar_service=SimpleNamespace(),
        model_config_service=None,
        upscale_service=None,
    )

    profile = SimpleNamespace(
        id=3,
        name="Portrait",
        provider="openai",
        model="gpt-image-1",
        model_config_id=5,
        base_prompt="cinematic",
        width=1024,
        height=768,
        n_images=1,
        seed=11,
        output_format="png",
        upscale_provider=None,
        upscale_model="",
        params_json={"k": "v"},
        storage_template_id=9,
        storage_template=SimpleNamespace(
            id=9,
            name="default",
            base_dir=".",
            template="/{profile}/{slug}-{gen_id}-{idx}.{ext}",
        ),
        categories=[SimpleNamespace(id=1, name="A"), SimpleNamespace(id=2, name="B")],
    )

    generation = service.create_generation_from_profile(
        session=SimpleNamespace(),
        profile=profile,
        prompt_user="a subject",
        overrides={
            "width": 640,
            "n_images": 3,
            "seed": 42,
            "params_json": {"extra": True},
            "upscale_model": " model-x ",
            "upscale_topaz_model_id": "12",
            "category_ids": [2, 2, "3", -1],
            "input_images": [{"name": "img"}],
            "chat_session_id": "session:abc",
        },
    )

    assert generation.id == 77
    assert generation.status == "queued"
    assert generation.prompt_final == "cinematic\na subject"
    request_snapshot = generation.request_snapshot_json
    assert request_snapshot["width"] == 640
    assert request_snapshot["height"] == 768
    assert request_snapshot["n_images"] == 3
    assert request_snapshot["seed"] == 42
    assert request_snapshot["upscale_model"] == "model-x"
    assert request_snapshot["upscale_topaz_model_id"] == 12
    assert request_snapshot["category_ids"] == [2, 3]
    assert request_snapshot["chat_session_id"] == "session:abc"
    assert request_snapshot["params_json"] == {"extra": True}
    assert request_snapshot["overrides"]["width"] is True
    assert request_snapshot["overrides"]["height"] is False

    storage_snapshot = generation.storage_template_snapshot_json
    assert storage_snapshot["id"] == 9
    assert storage_snapshot["name"] == "default"
    assert storage_snapshot["template"] == "/{profile}/{slug}-{gen_id}-{idx}.{ext}"

    profile_snapshot = generation.profile_snapshot_json
    assert profile_snapshot["id"] == 3
    assert profile_snapshot["category_ids"] == [1, 2]
    assert profile_snapshot["category_names"] == ["A", "B"]
    assert "generation" in captured


def test_create_generation_from_profile_requires_storage_template() -> None:
    service = GenerationService(
        settings=Settings(),
        registry=SimpleNamespace(),
        storage_service=SimpleNamespace(),
        thumbnail_service=SimpleNamespace(),
        sidecar_service=SimpleNamespace(),
        model_config_service=None,
        upscale_service=None,
    )
    profile = SimpleNamespace(
        id=1,
        name="P",
        provider="stub",
        model="m",
        model_config_id=1,
        base_prompt="",
        width=1,
        height=1,
        n_images=1,
        seed=None,
        output_format="png",
        upscale_provider=None,
        upscale_model=None,
        params_json={},
        storage_template_id=None,
        storage_template=None,
        categories=[],
    )

    with pytest.raises(ValueError, match="no storage template"):
        service.create_generation_from_profile(SimpleNamespace(), profile, "prompt")


def test_create_generation_from_snapshot_resets_upscaling_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_create_generation(_session, generation):  # type: ignore[no-untyped-def]
        generation.id = 55
        return generation

    monkeypatch.setattr("app.services.generation_service.crud.create_generation", fake_create_generation)

    service = GenerationService(
        settings=Settings(),
        registry=SimpleNamespace(),
        storage_service=SimpleNamespace(),
        thumbnail_service=SimpleNamespace(),
        sidecar_service=SimpleNamespace(),
        model_config_service=None,
        upscale_service=None,
    )
    source = Generation(
        id=10,
        profile_id=2,
        profile_name="P",
        prompt_user="u",
        prompt_final="f",
        provider="stub",
        model="m",
        status="failed",
        profile_snapshot_json={"a": 1},
        storage_template_snapshot_json={"base_dir": "."},
        request_snapshot_json={"upscaling_active": True},
    )

    clone = service.create_generation_from_snapshot(SimpleNamespace(), source)
    assert clone.id == 55
    assert clone.status == "queued"
    assert clone.request_snapshot_json["upscaling_active"] is False


def test_cancel_generation_and_raise_if_cancelled_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    service = GenerationService(
        settings=Settings(),
        registry=SimpleNamespace(),
        storage_service=SimpleNamespace(),
        thumbnail_service=SimpleNamespace(),
        sidecar_service=SimpleNamespace(),
        model_config_service=None,
        upscale_service=None,
    )

    class FakeSession:
        def __init__(self) -> None:
            self.commits = 0
            self.refreshed = 0

        def commit(self) -> None:
            self.commits += 1

        def refresh(self, _obj) -> None:  # type: ignore[no-untyped-def]
            self.refreshed += 1

    session = FakeSession()

    running = Generation(
        id=8,
        profile_name="P",
        prompt_user="u",
        prompt_final="f",
        provider="stub",
        model="m",
        status="running",
        profile_snapshot_json={},
        storage_template_snapshot_json={},
        request_snapshot_json={},
    )
    done = Generation(
        id=9,
        profile_name="P",
        prompt_user="u",
        prompt_final="f",
        provider="stub",
        model="m",
        status="succeeded",
        profile_snapshot_json={},
        storage_template_snapshot_json={},
        request_snapshot_json={},
    )

    monkeypatch.setattr(
        "app.services.generation_service.crud.get_generation",
        lambda _session, generation_id, with_assets=True: running if generation_id == 8 else done,
    )

    cancelled = service.cancel_generation(session, 8)
    already_done = service.cancel_generation(session, 9)
    assert cancelled is running
    assert cancelled.status == "cancelled"
    assert cancelled.error == "Canceled by user."
    assert already_done is done
    assert session.commits == 1
    assert session.refreshed == 1

    calls = {"count": 0}

    def _get_generation_for_raise(_session, _id):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return SimpleNamespace(status="cancelled")

    monkeypatch.setattr("app.services.generation_service.crud.get_generation", _get_generation_for_raise)
    with pytest.raises(GenerationCancelledError, match="no longer exists"):
        service._raise_if_cancelled(session, 1)
    with pytest.raises(GenerationCancelledError, match="Canceled by user"):
        service._raise_if_cancelled(session, 1)


def test_asset_absolute_path_requires_generation_and_resolves_thumbnail() -> None:
    storage = SimpleNamespace(
        resolve_managed_path=lambda base_dir, rel: Path(base_dir) / Path(str(rel)),
    )
    service = GenerationService(
        settings=Settings(),
        registry=SimpleNamespace(),
        storage_service=storage,
        thumbnail_service=SimpleNamespace(),
        sidecar_service=SimpleNamespace(),
        model_config_service=None,
        upscale_service=None,
    )

    asset = Asset(
        id=1,
        generation_id=1,
        file_path="a.png",
        sidecar_path="a.json",
        thumbnail_path=".thumbs/a.webp",
        width=1,
        height=1,
        mime="image/png",
    )

    with pytest.raises(ValueError, match="no associated generation"):
        service.asset_absolute_path(asset)

    asset.generation = Generation(
        id=1,
        profile_name="P",
        prompt_user="u",
        prompt_final="f",
        provider="stub",
        model="m",
        status="queued",
        profile_snapshot_json={},
        storage_template_snapshot_json={"base_dir": "."},
        request_snapshot_json={},
    )

    thumb_path = service.asset_absolute_path(asset, which="thumb")
    assert str(thumb_path).endswith(".thumbs\\a.webp") or str(thumb_path).endswith(".thumbs/a.webp")
