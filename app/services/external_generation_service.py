"""Image generation for external clients such as the MCP endpoint.

External apps (for example TaleWeaver) address models, profiles and
categories by name instead of database IDs and usually want to wait for the
finished image. This service resolves those references, builds the same
``overrides`` the web UI sends, creates the ``Generation`` row via
``GenerationService`` and runs the job.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.db import crud
from app.db import engine as db_engine
from app.db.models import Asset, Category, ChatSession, Generation, ModelConfig, Profile
from app.services.generation_service import GenerationService

FINISHED_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
CATEGORY_NAME_MAX_LENGTH = 30
MAX_IMAGES_PER_REQUEST = 8
SESSION_TITLE_MAX_LENGTH = 40
SESSION_NAME_MAX_LENGTH = 200
SESSION_LIST_MAX = 200
POLL_INTERVAL_SECONDS = 1.0


class ExternalGenerationError(ValueError):
    """Raised when an external generation request references unknown or invalid data."""


@dataclass
class ExternalImageRequest:
    """Parameters of an image request coming from an external client.

    ``model``, ``profile`` and each entry of ``categories`` may be a database
    ID or a name (case-insensitive). Models can also be matched by their
    provider model identifier. ``session`` names the Lumigen session that
    collects the images: requests with the same name land in the same session.
    """

    prompt: str
    model: str | int | None = None
    profile: str | int | None = None
    categories: list[str | int] = field(default_factory=list)
    negative_prompt: str | None = None
    aspect_ratio: str | None = None
    resolution: str | None = None
    n_images: int | None = None
    seed: int | None = None
    session: str | None = None
    create_missing_categories: bool = True


class ExternalGenerationService:
    """Resolve external references and create, run and read generation jobs."""

    def __init__(self, generation_service: GenerationService) -> None:
        self.generation_service = generation_service
        self._background_tasks: set[asyncio.Task[None]] = set()

    # ------------------------------------------------------------------ lookup

    def list_models(self, session: Session) -> list[dict[str, Any]]:
        """Return the configured image models as plain dicts."""
        return [
            {
                "id": cfg.id,
                "name": cfg.name,
                "provider": cfg.provider,
                "model": cfg.model,
                "supports_image_input": cfg.supports_image_input,
            }
            for cfg in crud.list_model_configs(session)
        ]

    def list_profiles(self, session: Session) -> list[dict[str, Any]]:
        """Return all generation profiles with their model and categories."""
        return [
            {
                "id": profile.id,
                "name": profile.name,
                "model": profile.model_config.name if profile.model_config else profile.model,
                "aspect_ratio": profile.aspect_ratio,
                "n_images": profile.n_images,
                "base_prompt": profile.base_prompt,
                "categories": [
                    {"id": category.id, "name": category.name} for category in profile.categories
                ],
            }
            for profile in crud.list_profiles(session)
        ]

    def list_categories(self, session: Session) -> list[dict[str, Any]]:
        """Return all gallery categories."""
        return [{"id": cat.id, "name": cat.name} for cat in crud.list_categories(session)]

    def list_sessions(self, session: Session, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recently updated Lumigen sessions (newest first)."""
        limit = max(1, min(SESSION_LIST_MAX, int(limit)))
        return [
            {
                "id": chat.chat_session_id,
                "name": chat.title,
                "updated_at": chat.updated_at.isoformat() if chat.updated_at else None,
            }
            for chat in crud.list_chat_sessions(session)[:limit]
        ]

    def resolve_session(
        self,
        session: Session,
        name: str | None,
        *,
        prompt: str,
        profile: Profile,
        model_cfg: ModelConfig | None,
    ) -> ChatSession:
        """Return the Lumigen session for *name*, creating it if needed.

        *name* matches an existing session by its ID or by its title
        (case-insensitive; the most recently used one wins). Without a name a
        new session titled after the prompt is created.

        Raises:
            ExternalGenerationError: If the name is longer than 200 characters.
        """
        from app.main import build_chat_session_token

        name = (name or "").strip()
        if len(name) > SESSION_NAME_MAX_LENGTH:
            raise ExternalGenerationError(
                f"Session name is longer than {SESSION_NAME_MAX_LENGTH} characters."
            )
        if name:
            chat = crud.get_chat_session(session, name)
            if chat is None:
                needle = name.lower()
                chat = next(
                    (
                        item
                        for item in crud.list_chat_sessions(session)
                        if (item.title or "").strip().lower() == needle
                    ),
                    None,
                )
            if chat is not None:
                chat.last_profile_id = profile.id
                chat.last_model_config_id = model_cfg.id if model_cfg else None
                session.commit()
                return chat
        return crud.create_chat_session(
            session,
            chat_session_id=build_chat_session_token(),
            title=name or _title_from_prompt(prompt),
            last_profile_id=profile.id,
            last_model_config_id=model_cfg.id if model_cfg else None,
        )

    def resolve_model(self, session: Session, ref: str | int) -> ModelConfig:
        """Return the model config matching *ref* (ID, name or provider model identifier).

        Raises:
            ExternalGenerationError: If no or more than one model matches.
        """
        configs = crud.list_model_configs(session)
        by_id = _match_id(configs, ref)
        if by_id is not None:
            return by_id
        needle = str(ref).strip().lower()
        by_name = [cfg for cfg in configs if cfg.name.strip().lower() == needle]
        if len(by_name) == 1:
            return by_name[0]
        by_model = [cfg for cfg in configs if cfg.model.strip().lower() == needle]
        if len(by_model) == 1:
            return by_model[0]
        if len(by_model) > 1:
            names = ", ".join(cfg.name for cfg in by_model)
            raise ExternalGenerationError(
                f"Model '{ref}' is ambiguous, use one of these names: {names}."
            )
        raise ExternalGenerationError(f"Unknown model '{ref}'. Call list_models for valid values.")

    def resolve_profile(self, session: Session, ref: str | int) -> Profile:
        """Return the profile matching *ref* (ID or name).

        Raises:
            ExternalGenerationError: If no profile matches.
        """
        profiles = crud.list_profiles(session)
        found = _match_id(profiles, ref)
        if found is not None:
            return found
        needle = str(ref).strip().lower()
        for profile in profiles:
            if profile.name.strip().lower() == needle:
                return profile
        raise ExternalGenerationError(
            f"Unknown profile '{ref}'. Call list_profiles for valid values."
        )

    def resolve_categories(
        self, session: Session, refs: list[str | int], *, create_missing: bool
    ) -> list[Category]:
        """Return the categories for *refs* (IDs or names), creating missing names if allowed.

        Raises:
            ExternalGenerationError: If a reference is unknown and may not be created,
                or a new name is too long.
        """
        existing = crud.list_categories(session)
        result: list[Category] = []
        for ref in refs:
            found = _match_id(existing, ref)
            if found is None:
                needle = str(ref).strip().lower()
                found = next(
                    (cat for cat in existing if cat.name.strip().lower() == needle), None
                )
            if found is None:
                name = str(ref).strip()
                if not name or isinstance(ref, int) or name.isdigit():
                    raise ExternalGenerationError(f"Unknown category '{ref}'.")
                if not create_missing:
                    raise ExternalGenerationError(
                        f"Unknown category '{ref}'. Call list_categories for valid values."
                    )
                if len(name) > CATEGORY_NAME_MAX_LENGTH:
                    raise ExternalGenerationError(
                        f"Category name '{name}' is longer than {CATEGORY_NAME_MAX_LENGTH} characters."
                    )
                found = crud.create_category(session, name=name)
                existing.append(found)
            if all(item.id != found.id for item in result):
                result.append(found)
        return result

    # ------------------------------------------------------------------ jobs

    def create_job(self, session: Session, request: ExternalImageRequest) -> Generation:
        """Validate *request*, persist a queued ``Generation`` and return it.

        The model wins over the profile's model when both are given. Without a
        profile the neutral ``Default`` profile is used.

        Raises:
            ExternalGenerationError: If the prompt is empty or a reference is invalid.
        """
        from app.api.generation import _default_profile

        prompt = (request.prompt or "").strip()
        if not prompt:
            raise ExternalGenerationError("Prompt is required.")

        profile = (
            self.resolve_profile(session, request.profile)
            if request.profile not in (None, "")
            else _default_profile(session)
        )
        model_cfg: ModelConfig | None = None
        if request.model not in (None, ""):
            model_cfg = self.resolve_model(session, request.model)
        elif profile.model_config_id:
            model_cfg = crud.get_model_config(session, profile.model_config_id)
        if model_cfg is None and not (profile.provider and profile.model):
            raise ExternalGenerationError(
                "No model selected. Pass a model or a profile with a model."
            )

        overrides: dict[str, Any] = {}
        if model_cfg is not None:
            overrides.update(
                model_config_id=model_cfg.id,
                provider=model_cfg.provider,
                model=model_cfg.model,
                model_name=model_cfg.name,
            )
            cfg_params = getattr(model_cfg, "generic_params", None)
            if isinstance(cfg_params, dict) and "output_format" in cfg_params:
                overrides["output_format"] = str(cfg_params["output_format"]).strip().lower().lstrip(".")

        if request.categories:
            categories = self.resolve_categories(
                session, request.categories, create_missing=request.create_missing_categories
            )
            overrides["category_ids"] = [cat.id for cat in categories]

        provider = str(overrides.get("provider") or profile.provider or "").strip().lower()
        # Without an aspect ratio (request or profile) none is sent and the prompt decides.
        aspect_ratio = (request.aspect_ratio or "").strip() or (profile.aspect_ratio or "").strip()
        resolution = (request.resolution or "").strip() or "1K"
        try:
            overrides.update(_sizing_overrides(profile, provider, aspect_ratio, resolution))
        except ValueError as exc:
            raise ExternalGenerationError(str(exc)) from exc
        if aspect_ratio:
            overrides["aspect_ratio"] = aspect_ratio
        overrides["resolution"] = resolution

        if request.n_images is not None:
            overrides["n_images"] = max(1, min(MAX_IMAGES_PER_REQUEST, int(request.n_images)))
        if request.seed is not None:
            overrides["seed"] = int(request.seed)
        if request.negative_prompt and request.negative_prompt.strip():
            overrides["negative_prompt"] = request.negative_prompt.strip()

        chat = self.resolve_session(
            session, request.session, prompt=prompt, profile=profile, model_cfg=model_cfg
        )
        overrides["chat_session_id"] = chat.chat_session_id
        if chat.title:
            overrides["chat_session_title"] = chat.title

        try:
            return self.generation_service.create_generation_from_profile(
                session, profile, prompt, overrides=overrides
            )
        except ValueError as exc:
            raise ExternalGenerationError(str(exc)) from exc

    def start_job(self, generation_id: int) -> asyncio.Task[None]:
        """Run the generation job in the background of the current event loop."""
        task = asyncio.create_task(self.generation_service.run_generation_job(generation_id))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def wait_for_job(self, generation_id: int, timeout_seconds: float) -> Generation | None:
        """Poll the job until it is finished or *timeout_seconds* passed.

        Returns:
            The latest ``Generation`` row (with assets), or ``None`` if it no longer exists.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.0, timeout_seconds)
        while True:
            generation = self.load_job(generation_id)
            if generation is None or generation.status in FINISHED_STATUSES:
                return generation
            if loop.time() >= deadline:
                return generation
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    @staticmethod
    def load_job(generation_id: int) -> Generation | None:
        """Return the generation with its assets loaded, or ``None``."""
        with db_engine.SessionLocal() as session:
            return crud.get_generation(session, generation_id, with_assets=True)

    def describe_job(self, generation: Generation) -> dict[str, Any]:
        """Return a JSON-serializable summary of *generation* and its assets."""
        snapshot = generation.request_snapshot_json or {}
        return {
            "job_id": generation.id,
            "status": generation.status,
            "finished": generation.status in FINISHED_STATUSES,
            "error": generation.error,
            "prompt": generation.prompt_user,
            "model": generation.model,
            "model_config_id": snapshot.get("model_config_id"),
            "provider": generation.provider,
            "profile": generation.profile_name,
            "aspect_ratio": snapshot.get("aspect_ratio"),
            "seed": snapshot.get("seed"),
            "categories": self._category_summary(snapshot.get("category_ids") or []),
            "session": {
                "id": snapshot.get("chat_session_id"),
                "name": snapshot.get("chat_session_title"),
            },
            "images": [
                {
                    "asset_id": asset.id,
                    "width": asset.width,
                    "height": asset.height,
                    "mime": asset.mime,
                }
                for asset in (generation.assets or [])
            ],
        }

    @staticmethod
    def _category_summary(category_ids: list[int]) -> list[dict[str, Any]]:
        """Return ``{id, name}`` for the categories the job files its images under."""
        if not category_ids:
            return []
        with db_engine.SessionLocal() as session:
            return [
                {"id": cat.id, "name": cat.name}
                for cat in crud.list_categories_by_ids(session, list(category_ids))
            ]

    def read_asset(self, asset_id: int, *, thumbnail: bool = False) -> tuple[bytes, str]:
        """Return the bytes and MIME type of an asset file or its thumbnail.

        Raises:
            ExternalGenerationError: If the asset or its file does not exist.
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        with db_engine.SessionLocal() as session:
            asset = session.scalar(
                select(Asset).options(selectinload(Asset.generation)).where(Asset.id == asset_id)
            )
            if asset is None or asset.generation is None:
                raise ExternalGenerationError(f"Unknown image '{asset_id}'.")
            try:
                path = self.generation_service.asset_absolute_path(
                    asset, which="thumb" if thumbnail else "file"
                )
            except ValueError as exc:
                raise ExternalGenerationError(f"File for image '{asset_id}' is missing.") from exc
            mime = "image/webp" if thumbnail else asset.mime
        if not path.exists():
            raise ExternalGenerationError(f"File for image '{asset_id}' is missing.")
        data = path.read_bytes()
        if thumbnail:
            mime = _mime_from_suffix(path.suffix) or mime
        return data, mime

    def read_asset_base64(self, asset_id: int, *, thumbnail: bool = False) -> tuple[str, str]:
        """Return the base64-encoded asset and its MIME type."""
        data, mime = self.read_asset(asset_id, thumbnail=thumbnail)
        return base64.b64encode(data).decode("ascii"), mime


def _match_id(rows: list[Any], ref: str | int) -> Any | None:
    """Return the row whose ``id`` equals *ref* when *ref* is an int or digit string."""
    if isinstance(ref, bool):
        return None
    if isinstance(ref, int):
        ref_id = ref
    elif isinstance(ref, str) and ref.strip().isdigit():
        ref_id = int(ref.strip())
    else:
        return None
    return next((row for row in rows if row.id == ref_id), None)


def _title_from_prompt(prompt: str) -> str:
    """Return a short chat session title derived from *prompt*."""
    flat = prompt.replace("\r\n", " ").replace("\n", " ").strip()
    if len(flat) <= SESSION_TITLE_MAX_LENGTH:
        return flat
    return flat[:SESSION_TITLE_MAX_LENGTH].rsplit(" ", 1)[0] or flat[:SESSION_TITLE_MAX_LENGTH]


def _sizing_overrides(
    profile: Profile, provider: str, aspect_ratio: str, resolution: str
) -> dict[str, Any]:
    """Map aspect ratio and resolution to the provider-specific ``params_json`` keys."""
    from app.main import (
        apply_fal_image_config,
        apply_google_image_config,
        apply_openrouter_image_config,
    )

    params_json = dict(profile.params_json or {})
    if provider == "openrouter":
        params_json = apply_openrouter_image_config(
            params_json=params_json,
            provider=provider,
            aspect_ratio=aspect_ratio,
            image_size=resolution,
            allow_clear=False,
        )
    elif provider == "fal":
        params_json = apply_fal_image_config(
            params_json=params_json,
            provider=provider,
            fal_aspect_ratio=aspect_ratio,
            fal_resolution=resolution,
            allow_clear=False,
        )
    elif provider == "google":
        params_json = apply_google_image_config(
            params_json=params_json,
            provider=provider,
            google_aspect_ratio=aspect_ratio,
            google_resolution=resolution,
            allow_clear=False,
        )
    else:
        return {}
    return {"params_json": params_json}


def _mime_from_suffix(suffix: str) -> str | None:
    """Return the MIME type for an image file suffix, or ``None`` if unknown."""
    return {
        ".webp": "image/webp",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
    }.get(suffix.lower())
