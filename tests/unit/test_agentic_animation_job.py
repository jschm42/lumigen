"""Tests for the agentic GIF animation job and its request validation."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from PIL import Image

from app.config import Settings
from app.db.models import Asset, Generation
from app.providers.base import ProviderGenerationRequest, ProviderGenerationResult, ProviderImage
from app.providers.registry import ProviderRegistry
from app.services.agentic_service import AgenticAnimationPlan, AgenticFramePlan
from app.services.generation_service import GenerationService

_UI_SETTINGS = {
    "show_token_usage": False,
    "cost_currency": "USD",
    "animation_max_frames": 24,
    "animation_max_dimension_px": 128,
    "animation_max_file_size_mb": 10,
    "animation_default_frame_ms": 100,
}


class _SessionCtx:
    def __init__(self, session):  # type: ignore[no-untyped-def]
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False


class _FakeSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, item) -> None:  # type: ignore[no-untyped-def]
        if isinstance(item, Asset) and item.id is None:
            item.id = len(self.added) + 1
        self.added.append(item)

    def commit(self) -> None:
        return None

    def refresh(self, _item) -> None:  # type: ignore[no-untyped-def]
        return None


class _FakeStorage:
    def __init__(self) -> None:
        self.writes: dict[str, bytes] = {}

    def render_relative_path(self, **kwargs):  # type: ignore[no-untyped-def]
        return Path(f"anim-{kwargs['idx']}.{kwargs['ext']}")

    def resolve_managed_path(self, base_dir, relative_path):  # type: ignore[no-untyped-def]
        return Path(base_dir) / Path(relative_path)

    def write_bytes_atomic(self, abs_path, data):  # type: ignore[no-untyped-def]
        self.writes[Path(abs_path).name] = bytes(data)


class _FakeThumbs:
    def create_thumbnail(self, _base_dir, rel):  # type: ignore[no-untyped-def]
        return Path(f".thumbs/{Path(rel).stem}.webp")


class _FakeSidecars:
    def write_asset_sidecar(self, _base_dir, rel_path, _payload):  # type: ignore[no-untyped-def]
        return Path(f"{rel_path}.json")


class _Registry:
    """Records requests and returns a solid-colour PNG per call."""

    def __init__(self, supports_input: bool = True, fail_on: int | None = None) -> None:
        self.requests: list[ProviderGenerationRequest] = []
        self.supports_input = supports_input
        self.fail_on = fail_on

    def supports_image_input(self, _provider, _model, _explicit=None) -> bool:  # type: ignore[no-untyped-def]
        return self.supports_input

    async def generate(self, _provider, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        if self.fail_on is not None and len(self.requests) > self.fail_on:
            raise RuntimeError("provider exploded")
        shade = (len(self.requests) * 40) % 256
        image = Image.new("RGB", (160, 160), (shade, 255 - shade, 90))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return ProviderGenerationResult(
            images=[ProviderImage(data=buffer.getvalue(), mime="image/png", width=160, height=160)],
            raw_meta={"n": len(self.requests)},
        )


def _plan(frames: int = 3) -> AgenticAnimationPlan:
    return AgenticAnimationPlan(
        title="Bounce",
        subject_anchor="red ball",
        scene_anchor="flat background",
        style_anchor="flat vector",
        negative_prompt="blurry, sprite sheet",
        loop="loop",
        default_frame_ms=90,
        frames=[AgenticFramePlan(title=f"F{i}", pose=f"pose {i}", duration_ms=120 if i == 0 else None) for i in range(frames)],
    )


def _generation() -> Generation:
    return Generation(
        id=7,
        profile_id=1,
        profile_name="Profile",
        prompt_user="a bouncing ball",
        prompt_final="a bouncing ball",
        provider="stub",
        model="stub-v1",
        status="queued",
        profile_snapshot_json={},
        storage_template_snapshot_json={"base_dir": ".", "template": "{idx}.{ext}"},
        request_snapshot_json={
            "is_agentic": True,
            "agentic_kind": "animation",
            "animation": {"loop": None, "frame_ms": None, "transparent": False},
            "category_ids": [],
            "seed": 42,
        },
    )


def _service(monkeypatch: pytest.MonkeyPatch, registry: _Registry, generation: Generation, plan: AgenticAnimationPlan):
    session = _FakeSession()
    storage = _FakeStorage()
    agentic = MagicMock()
    agentic.plan_animation = AsyncMock(return_value=plan)
    service = GenerationService(
        settings=Settings(),
        registry=registry,  # type: ignore[arg-type]
        storage_service=storage,  # type: ignore[arg-type]
        thumbnail_service=_FakeThumbs(),  # type: ignore[arg-type]
        sidecar_service=_FakeSidecars(),  # type: ignore[arg-type]
        agentic_service=agentic,
    )
    monkeypatch.setattr("app.services.generation_service.SessionLocal", lambda: _SessionCtx(session))
    monkeypatch.setattr("app.services.generation_service.ensure_dir", lambda _p: None)
    monkeypatch.setattr("app.services.generation_service.crud.get_generation", lambda _s, _id: generation)
    monkeypatch.setattr("app.services.generation_service.crud.list_categories_by_ids", lambda _s, _ids: [])
    monkeypatch.setattr(
        "app.services.generation_service.AppSettingsService.get_ui_settings", lambda _self, _s: dict(_UI_SETTINGS)
    )
    monkeypatch.setattr(service, "_raise_if_cancelled", lambda _s, _id: None)
    monkeypatch.setattr(
        service,
        "_provider_request_from_generation",
        lambda _g: ProviderGenerationRequest(
            prompt="x", width=None, height=None, n_images=4, seed=None, output_format="webp", model="stub-v1"
        ),
    )
    return service, session, storage, agentic


@pytest.mark.asyncio
async def test_animation_job_chains_keyframe_and_builds_gif_cover(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _Registry()
    generation = _generation()
    service, session, storage, agentic = _service(monkeypatch, registry, generation, _plan(3))

    await service.run_generation_job(generation.id)

    assert generation.status == "succeeded", generation.error
    assert generation.request_snapshot_json["agentic_step"] == "completed"
    assert generation.request_snapshot_json["agentic_plan"]["kind"] == "animation"
    agentic.plan_animation.assert_awaited_once()
    assert agentic.plan_animation.await_args.kwargs["frame_limit"] == 24

    # Frame 0 is text-to-image; later frames only reference the keyframe (no copy chain via the previous frame).
    assert [len(r.input_images) for r in registry.requests] == [0, 1, 1]
    assert registry.requests[2].input_images[0].data == registry.requests[1].input_images[0].data
    assert all(r.seed == 42 and r.n_images == 1 and r.output_format == "png" for r in registry.requests)
    assert registry.requests[0].prompt.startswith("red ball, pose 0")
    assert "pose 2" in registry.requests[2].prompt

    assets = [item for item in session.added if isinstance(item, Asset)]
    assert len(assets) == 4
    gif = next(a for a in assets if a.mime == "image/gif")
    frames = sorted((a for a in assets if a.mime == "image/png"), key=lambda a: a.stack_order)
    assert gif.stack_order == 0
    assert [a.stack_order for a in frames] == [1, 2, 3]
    assert len({a.stack_id for a in assets}) == 1
    assert gif.meta_json["role"] == "animation"
    assert gif.meta_json["frame_asset_ids"] == [a.id for a in frames]
    assert gif.meta_json["durations_ms"] == [120, 90, 90]
    assert frames[0].meta_json["role"] == "frame"

    encoded = Image.open(BytesIO(storage.writes["anim-0.gif"]))
    assert encoded.n_frames == 3
    assert max(encoded.size) == 128  # studio dimension limit applied


@pytest.mark.asyncio
async def test_animation_job_rejects_model_without_image_input(monkeypatch: pytest.MonkeyPatch) -> None:
    generation = _generation()
    registry = _Registry(supports_input=False)
    service, session, _storage, agentic = _service(monkeypatch, registry, generation, _plan())

    await service.run_generation_job(generation.id)

    assert generation.status == "failed"
    assert "does not support image input" in (generation.error or "")
    agentic.plan_animation.assert_not_awaited()
    assert registry.requests == []


@pytest.mark.asyncio
async def test_animation_job_keeps_frames_when_a_frame_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    generation = _generation()
    registry = _Registry(fail_on=1)  # first call succeeds, every later call fails
    service, session, _storage, _agentic = _service(monkeypatch, registry, generation, _plan(3))

    await service.run_generation_job(generation.id)

    assert generation.status == "failed"
    assert "Frame 2" in (generation.error or "")
    assert len(registry.requests) == 3  # one success + one retry pair for frame 2
    assets = [item for item in session.added if isinstance(item, Asset)]
    assert len(assets) == 1 and assets[0].stack_order == 0


# --- request validation -------------------------------------------------------------------------


def _submit_request(payload: dict) -> MagicMock:
    request = MagicMock()
    request.headers = {"content-type": "application/json"}
    request.json = AsyncMock(return_value=payload)
    return request


def _profile(model: str) -> MagicMock:
    profile = MagicMock()
    profile.id = 1
    profile.provider = "stub" if model.startswith("stub") else "openai"
    profile.model = model
    profile.model_config_id = None
    profile.params_json = {}
    return profile


@pytest.mark.asyncio
async def test_submit_animation_rejects_model_without_image_input() -> None:
    from app.api.generation import api_generate_submit

    with patch("app.api.generation.generation_service.enqueue") as enqueue, \
         patch("app.api.generation.generation_service.create_generation_from_profile") as create, \
         patch("app.db.crud.get_profile", return_value=_profile("dall-e-3")), \
         patch("app.db.crud.get_chat_session", return_value=object()), \
         patch("app.db.crud.list_session_input_images", return_value=[]):
        with pytest.raises(HTTPException) as exc_info:
            await api_generate_submit(
                request=_submit_request(
                    {"prompt": "spinning coin", "profile_id": 1, "is_agentic": True, "agentic_kind": "animation"}
                ),
                background_tasks=MagicMock(),
                session=MagicMock(),
            )
    assert exc_info.value.status_code == 422
    assert "image input" in exc_info.value.detail
    create.assert_not_called()
    enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_submit_animation_stores_normalized_options() -> None:
    from app.api.generation import api_generate_submit

    generation = MagicMock(id=5, status="queued")
    with patch("app.api.generation.generation_service.enqueue"), \
         patch("app.api.generation.generation_service.create_generation_from_profile", return_value=generation) as create, \
         patch("app.db.crud.get_profile", return_value=_profile("stub-v1")), \
         patch("app.db.crud.get_chat_session", return_value=object()), \
         patch("app.db.crud.list_session_input_images", return_value=[]), \
         patch("app.api.generation.app_settings_service.get_ui_settings", return_value={**_UI_SETTINGS, "animation_max_frames": 10}):
        await api_generate_submit(
            request=_submit_request(
                {
                    "prompt": "spinning coin",
                    "profile_id": 1,
                    "is_agentic": True,
                    "agentic_kind": "animation",
                    "min_images": 4,
                    "max_images": 99,
                    "animation": {"loop": "pingpong", "frame_ms": 5, "transparent": True, "output": "WEBP"},
                }
            ),
            background_tasks=MagicMock(),
            session=MagicMock(),
        )
    overrides = create.call_args.kwargs["overrides"]
    assert overrides["agentic_kind"] == "animation"
    assert overrides["min_images"] == 4
    assert overrides["max_images"] == 10  # capped by the studio frame limit
    assert overrides["animation"] == {"loop": "pingpong", "frame_ms": 20, "transparent": True, "output": "webp"}


@pytest.mark.asyncio
async def test_submit_animation_rejects_invalid_kind_and_loop() -> None:
    from app.api.generation import api_generate_submit

    for extra, message in (
        ({"agentic_kind": "movie"}, "agentic_kind"),
        ({"agentic_kind": "animation", "animation": {"loop": "bounce"}}, "animation.loop"),
        ({"agentic_kind": "animation", "animation": {"output": "mp4"}}, "animation.output"),
    ):
        with patch("app.api.generation.generation_service.enqueue"), \
             patch("app.api.generation.generation_service.create_generation_from_profile"), \
             patch("app.db.crud.get_profile", return_value=_profile("stub-v1")), \
             patch("app.db.crud.get_chat_session", return_value=object()), \
             patch("app.db.crud.list_session_input_images", return_value=[]):
            with pytest.raises(HTTPException) as exc_info:
                await api_generate_submit(
                    request=_submit_request({"prompt": "x", "profile_id": 1, "is_agentic": True, **extra}),
                    background_tasks=MagicMock(),
                    session=MagicMock(),
                )
        assert exc_info.value.status_code == 400
        assert message in exc_info.value.detail


def test_registry_image_input_capability() -> None:
    registry = ProviderRegistry(Settings())
    assert registry.supports_image_input("stub", "stub-v1") is True
    assert registry.supports_image_input("openai", "dall-e-3") is False
    assert registry.supports_image_input("openai", "gpt-image-1") is True
    assert registry.supports_image_input("fal", "fal-ai/nano-banana-2/edit") is True
    # Explicit admin override wins in both directions.
    assert registry.supports_image_input("openai", "dall-e-3", True) is True
    assert registry.supports_image_input("openai", "gpt-image-1", False) is False
    assert registry.supports_image_input("unknown", "gpt-image-1") is False
    assert registry.capabilities_for("openai", "gpt-image-1") == ["image", "image_input"]
    assert registry.capabilities_for("openai", "dall-e-3") == ["image"]


def test_admin_model_config_image_input_override() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.api import admin as admin_api
    from app.db.models import Base

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, future=True)() as session:
        created = admin_api.create_model_config(
            {"name": "Dalle", "provider": "openai", "model_identifier": "dall-e-3"}, session=session
        )
        assert created["supports_image_input"] is None
        assert created["image_input"] is False
        assert "image_input" not in created["capabilities"]

        updated = admin_api.update_model_config(created["id"], {"supports_image_input": True}, session=session)
        assert updated["supports_image_input"] is True
        assert updated["image_input"] is True
        assert "image_input" in updated["capabilities"]

        # Omitting the field keeps the override; "auto" resets it.
        kept = admin_api.update_model_config(created["id"], {"name": "Dalle 3"}, session=session)
        assert kept["supports_image_input"] is True
        reset = admin_api.update_model_config(created["id"], {"supports_image_input": "auto"}, session=session)
        assert reset["supports_image_input"] is None

        with pytest.raises(HTTPException):
            admin_api.update_model_config(created["id"], {"supports_image_input": "yes"}, session=session)


@pytest.mark.asyncio
async def test_animation_job_sends_no_seed_unless_user_set_one(monkeypatch: pytest.MonkeyPatch) -> None:
    generation = _generation()
    generation.request_snapshot_json = {**generation.request_snapshot_json, "seed": None}
    registry = _Registry()
    service, _session, _storage, _agentic = _service(monkeypatch, registry, generation, _plan(2))

    await service.run_generation_job(generation.id)

    assert generation.status == "succeeded", generation.error
    assert [r.seed for r in registry.requests] == [None, None]


def test_default_profile_never_uses_an_arbitrary_user_profile() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.api.generation import _default_profile
    from app.db import crud
    from app.db.models import Base, StorageTemplate

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, future=True)() as session:
        template = StorageTemplate(name="t", base_dir=".", template="{idx}.{ext}")
        session.add(template)
        session.commit()
        crud.create_profile(
            session, name="BFL FLUX.2 Klein 9B", storage_template_id=template.id, seed=7, params_json={"x": 1}
        )

        created = _default_profile(session)
        assert created.name == "Default"
        assert created.seed is None and not created.params_json

        # A second call reuses the same neutral profile instead of creating another one.
        assert _default_profile(session).id == created.id
        assert len(crud.list_profiles(session)) == 2



def _with_animation(generation: Generation, **options) -> Generation:  # type: ignore[no-untyped-def]
    snapshot = dict(generation.request_snapshot_json)
    snapshot["animation"] = {**snapshot["animation"], **options}
    generation.request_snapshot_json = snapshot
    return generation


@pytest.mark.asyncio
async def test_animation_job_writes_animated_webp_cover(monkeypatch: pytest.MonkeyPatch) -> None:
    generation = _with_animation(_generation(), output="webp")
    service, session, storage, _agentic = _service(monkeypatch, _Registry(), generation, _plan(3))

    await service.run_generation_job(generation.id)

    assert generation.status == "succeeded", generation.error
    assets = [item for item in session.added if isinstance(item, Asset)]
    cover = next(a for a in assets if a.stack_order == 0)
    assert cover.mime == "image/webp"
    assert cover.file_path.endswith(".webp")
    assert cover.meta_json["format"] == "webp"
    webp = Image.open(BytesIO(storage.writes["anim-0.webp"]))
    assert webp.format == "WEBP" and webp.n_frames == 3


@pytest.mark.asyncio
async def test_animation_job_frames_only_keeps_series_without_assembly(monkeypatch: pytest.MonkeyPatch) -> None:
    generation = _with_animation(_generation(), output="none")
    service, session, storage, _agentic = _service(monkeypatch, _Registry(), generation, _plan(3))

    await service.run_generation_job(generation.id)

    assert generation.status == "succeeded", generation.error
    assert generation.request_snapshot_json["agentic_step"] == "completed"
    assets = [item for item in session.added if isinstance(item, Asset)]
    assert [a.mime for a in assets] == ["image/png"] * 3
    assert sorted(a.stack_order for a in assets) == [0, 1, 2]  # frame 0 is the cover
    assert not any(name.endswith((".gif", ".webp")) for name in storage.writes)


@pytest.mark.asyncio
async def test_animation_job_stores_keyed_frames_when_transparent(monkeypatch: pytest.MonkeyPatch) -> None:
    class _KeyRegistry(_Registry):
        async def generate(self, _provider, request):  # type: ignore[no-untyped-def]
            self.requests.append(request)
            image = Image.new("RGB", (120, 120), (0, 255, 0))
            image.paste((200, 30, 30), (40, 40, 80, 80))
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return ProviderGenerationResult(
                images=[ProviderImage(data=buffer.getvalue(), mime="image/png", width=120, height=120)]
            )

    generation = _with_animation(_generation(), output="none", transparent=True)
    registry = _KeyRegistry()
    plan = _plan(2)
    plan.key_color = "#00FF00"
    service, _session, storage, _agentic = _service(monkeypatch, registry, generation, plan)

    await service.run_generation_job(generation.id)

    assert generation.status == "succeeded", generation.error
    stored = Image.open(BytesIO(storage.writes["anim-1.png"])).convert("RGBA")
    assert stored.getpixel((5, 5))[3] == 0  # background keyed out in the stored frame
    assert stored.getpixel((60, 60)) == (200, 30, 30, 255)
    # The model still receives the raw frame (with key background) as reference.
    reference = Image.open(BytesIO(registry.requests[1].input_images[0].data)).convert("RGBA")
    assert reference.getpixel((5, 5)) == (0, 255, 0, 255)



@pytest.mark.asyncio
async def test_animation_job_retries_frames_that_copy_the_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    class _CopyingRegistry(_Registry):
        """Returns the same image every time, like an edit model that ignores the pose instruction."""

        prompts: list[str] = []

        async def generate(self, _provider, request):  # type: ignore[no-untyped-def]
            self.requests.append(request)
            self.prompts.append(request.prompt)
            image = Image.new("RGB", (160, 160), (40, 90, 160))
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return ProviderGenerationResult(
                images=[ProviderImage(data=buffer.getvalue(), mime="image/png", width=160, height=160)]
            )

    generation = _generation()
    registry = _CopyingRegistry()
    service, session, _storage, _agentic = _service(monkeypatch, registry, generation, _plan(3))

    await service.run_generation_job(generation.id)

    # One static retry per frame after the keyframe, then the run continues instead of failing.
    assert generation.status == "succeeded", generation.error
    assert len(registry.requests) == 1 + 2 * 2
    assert "IMPORTANT" not in registry.prompts[1]
    assert "IMPORTANT" in registry.prompts[2]
    frames = [a for a in session.added if isinstance(a, Asset) and a.meta_json.get("role") == "frame"]
    assert [a.meta_json["static_retry"] for a in sorted(frames, key=lambda a: a.meta_json["frame_index"])] == [
        False,
        True,
        True,
    ]


@pytest.mark.asyncio
async def test_animation_job_does_not_retry_distinct_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    class _MovingRegistry(_Registry):
        async def generate(self, _provider, request):  # type: ignore[no-untyped-def]
            self.requests.append(request)
            image = Image.new("RGB", (160, 160), (0, 255, 0))
            offset = len(self.requests) * 30
            image.paste((20, 20, 20), (offset % 120, 40, offset % 120 + 40, 120))
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return ProviderGenerationResult(
                images=[ProviderImage(data=buffer.getvalue(), mime="image/png", width=160, height=160)]
            )

    generation = _generation()
    registry = _MovingRegistry()
    service, _session, _storage, _agentic = _service(monkeypatch, registry, generation, _plan(3))

    await service.run_generation_job(generation.id)

    assert generation.status == "succeeded", generation.error
    assert len(registry.requests) == 3
