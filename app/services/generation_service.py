from __future__ import annotations

import base64
import copy
from datetime import datetime

# For Python < 3.12 compatibility
try:
    from datetime import UTC
except ImportError:
    UTC = UTC
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks
from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import crud
from app.db.engine import SessionLocal
from app.db.models import Asset, Generation, ModelConfig, Profile, Style
from app.providers.base import (
    ExpandSpec,
    ProviderError,
    ProviderGenerationRequest,
    ProviderInputImage,
)
from app.providers.registry import ProviderRegistry
from app.services.expand_service import ExpandService, expand_to_provider_params
from app.services.model_config_service import ModelConfigService
from app.services.sidecar_service import SidecarService
from app.services.storage_service import StorageService
from app.services.thumbnail_service import ThumbnailService
from app.services.upscale_service import UpscaleService
from app.utils.paths import ensure_dir


class GenerationCancelledError(ProviderError):
    """Raised inside a generation job when the request has been cancelled by the user."""


class GenerationService:
    """Orchestrates the full lifecycle of an image generation job.

    Responsibilities include: building the provider request from a profile and
    optional overrides, persisting the ``Generation`` row, enqueuing the async
    background job, writing image/sidecar/thumbnail files via the storage and
    sidecar services, and updating the final job status.
    """

    def __init__(
        self,
        settings: Settings,
        registry: ProviderRegistry,
        storage_service: StorageService,
        thumbnail_service: ThumbnailService,
        sidecar_service: SidecarService,
        model_config_service: ModelConfigService | None = None,
        upscale_service: UpscaleService | None = None,
        fal_upscale_service=None,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.storage_service = storage_service
        self.thumbnail_service = thumbnail_service
        self.sidecar_service = sidecar_service
        self.model_config_service = model_config_service
        self.upscale_service = upscale_service
        self.fal_upscale_service = fal_upscale_service

    def create_generation_from_profile(
        self,
        session: Session,
        profile: Profile,
        prompt_user: str,
        overrides: dict[str, Any] | None = None,
    ) -> Generation:
        """Create and persist a queued ``Generation`` row derived from *profile* and optional *overrides*."""
        prompt_final = self._compose_prompt(profile.base_prompt, prompt_user)
        storage_template = profile.storage_template
        if storage_template is None:
            raise ValueError("Profile has no storage template configured")
        effective_overrides = overrides or {}

        width = effective_overrides.get("width", profile.width)
        height = effective_overrides.get("height", profile.height)
        n_images = int(effective_overrides.get("n_images", profile.n_images) or 1)
        seed = effective_overrides.get("seed", profile.seed)
        params_json_override = effective_overrides.get("params_json")
        if isinstance(params_json_override, dict):
            params_json = copy.deepcopy(params_json_override)
        else:
            params_json = copy.deepcopy(profile.params_json or {})

        # Resolve upscale provider and model from overrides or profile
        if "upscale_provider" in effective_overrides:
            upscale_provider = effective_overrides.get("upscale_provider") or None
        else:
            upscale_provider = profile.upscale_provider or None

        if "upscale_model" in effective_overrides:
            upscale_model_override = effective_overrides.get("upscale_model")
            if isinstance(upscale_model_override, str):
                upscale_model = upscale_model_override.strip() or None
            else:
                upscale_model = None
        else:
            upscale_model = str(profile.upscale_model or "").strip() or None

        if "upscale_topaz_model_id" in effective_overrides:
            upscale_topaz_model_id = self._parse_optional_int(
                effective_overrides.get("upscale_topaz_model_id")
            )
        else:
            upscale_topaz_model_id = self._parse_optional_int(
                getattr(profile, "upscale_topaz_model_id", None)
            )

        input_images = effective_overrides.get("input_images")
        chat_session_id = str(effective_overrides.get("chat_session_id") or "").strip()
        profile_category_ids = [item.id for item in profile.categories]
        category_ids = self._parse_int_list(
            effective_overrides.get("category_ids", profile_category_ids)
        )

        mode = str(effective_overrides.get("mode") or "generate").strip().lower()
        if mode not in {"generate", "edit", "expand"}:
            raise ValueError(f"Unsupported generation mode: {mode!r}")
        expand_spec = effective_overrides.get("expand")
        serialized_expand = self._serialize_expand_spec(expand_spec)

        profile_snapshot = {
            "id": profile.id,
            "name": profile.name,
            "provider": profile.provider,
            "model": profile.model,
            "model_config_id": profile.model_config_id,
            "base_prompt": profile.base_prompt,
            "width": profile.width,
            "height": profile.height,
            "n_images": profile.n_images,
            "seed": profile.seed,
            "output_format": profile.output_format,
            "upscale_provider": profile.upscale_provider,
            "upscale_model": profile.upscale_model,
            "upscale_topaz_model_id": getattr(profile, "upscale_topaz_model_id", None),
            "params_json": profile.params_json or {},
            "storage_template_id": profile.storage_template_id,
            "category_ids": profile_category_ids,
            "category_names": [item.name for item in profile.categories],
        }

        storage_snapshot = {
            "id": storage_template.id,
            "name": storage_template.name,
            "base_dir": Path(storage_template.base_dir).resolve().as_posix(),
            "template": storage_template.template,
        }

        request_snapshot = {
            "prompt_user": prompt_user,
            "prompt_user_original": str(
                effective_overrides.get("prompt_user_original") or prompt_user
            ),
            "prompt_final": prompt_final,
            "chat_session_id": chat_session_id or None,
            "chat_session_title": (
                str(effective_overrides.get("chat_session_title")).strip()
                if isinstance(effective_overrides.get("chat_session_title"), str)
                and str(effective_overrides.get("chat_session_title")).strip()
                else None
            ),
            "selected_style_ids": self._parse_int_list(
                effective_overrides.get("selected_style_ids", [])
            ),
            "selected_style_names": [
                str(name).strip()
                for name in effective_overrides.get("selected_style_names", [])
                if str(name).strip()
            ],
            "width": width,
            "height": height,
            "n_images": max(1, n_images),
            "seed": seed,
            "upscale_provider": upscale_provider,
            "upscale_model": upscale_model,
            "upscale_topaz_model_id": upscale_topaz_model_id,
            "upscaling_active": False,
            "output_format": profile.output_format,
            "provider": profile.provider,
            "model": profile.model,
            "model_config_id": profile.model_config_id,
            "params_json": params_json,
            "category_ids": category_ids,
            "input_images": input_images or [],
            "mode": mode,
            "expand": serialized_expand,
            "source_asset_id": (
                serialized_expand.get("source_asset_id")
                if isinstance(serialized_expand, dict)
                else None
            ),
            "continuation_prompt": (
                serialized_expand.get("continuation_prompt")
                if isinstance(serialized_expand, dict)
                else None
            ),
            "overrides": {
                "width": "width" in effective_overrides,
                "height": "height" in effective_overrides,
                "n_images": "n_images" in effective_overrides,
                "seed": "seed" in effective_overrides,
                "params_json": "params_json" in effective_overrides,
                "upscale_provider": "upscale_provider" in effective_overrides,
                "upscale_model": "upscale_model" in effective_overrides,
                "upscale_topaz_model_id": "upscale_topaz_model_id"
                in effective_overrides,
                "category_ids": "category_ids" in effective_overrides,
                "input_images": "input_images" in effective_overrides,
                "chat_session_id": "chat_session_id" in effective_overrides,
                "chat_session_title": "chat_session_title" in effective_overrides,
                "mode": "mode" in effective_overrides,
                "expand": "expand" in effective_overrides,
            },
        }

        generation = Generation(
            profile_id=profile.id,
            profile_name=profile.name,
            prompt_user=prompt_user,
            prompt_final=prompt_final,
            provider=profile.provider,
            model=profile.model,
            status="queued",
            error=None,
            profile_snapshot_json=profile_snapshot,
            storage_template_snapshot_json=storage_snapshot,
            request_snapshot_json=request_snapshot,
            failure_sidecar_path=None,
        )
        return crud.create_generation(session, generation)

    def create_generation_for_style(
        self,
        session: Session,
        style: Style,
        model_config: ModelConfig,
        prompt: str,
    ) -> Generation:
        """Create a generation job specifically for a style thumbnail."""
        from app.db.models import StorageTemplate
        storage_template = session.scalar(select(StorageTemplate).limit(1))
        if not storage_template:
             from app.config import settings
             storage_template = crud.ensure_default_storage_template(
                 session, settings.data_dir / "generations", "{idx}_{prompt}.{ext}"
             )

        request_snapshot = {
            "prompt_user": prompt,
            "prompt_final": prompt,
            "width": 1024,
            "height": 1024,
            "n_images": 1,
            "seed": None,
            "output_format": "webp",
            "provider": model_config.provider,
            "model": model_config.model,
            "model_config_id": model_config.id,
            "params_json": {},
            "is_style_generation": True,
            "style_id": style.id,
        }

        generation = Generation(
            profile_id=None,
            profile_name=f"Style: {style.name}",
            prompt_user=prompt,
            prompt_final=prompt,
            provider=model_config.provider,
            model=model_config.model,
            status="queued",
            profile_snapshot_json={},
            storage_template_snapshot_json={
                "id": storage_template.id,
                "name": storage_template.name,
                "base_dir": Path(storage_template.base_dir).resolve().as_posix(),
                "template": storage_template.template,
            },
            request_snapshot_json=request_snapshot,
        )
        return crud.create_generation(session, generation)

    def create_generation_from_snapshot(
        self, session: Session, source: Generation
    ) -> Generation:
        """Clone *source* into a new queued generation using its frozen snapshot data."""
        profile_snapshot = copy.deepcopy(source.profile_snapshot_json or {})
        storage_snapshot = copy.deepcopy(source.storage_template_snapshot_json or {})
        request_snapshot = copy.deepcopy(source.request_snapshot_json or {})
        request_snapshot["upscaling_active"] = False

        generation = Generation(
            profile_id=source.profile_id,
            profile_name=source.profile_name,
            prompt_user=source.prompt_user,
            prompt_final=source.prompt_final,
            provider=source.provider,
            model=source.model,
            status="queued",
            error=None,
            profile_snapshot_json=profile_snapshot,
            storage_template_snapshot_json=storage_snapshot,
            request_snapshot_json=request_snapshot,
            failure_sidecar_path=None,
        )
        return crud.create_generation(session, generation)

    def enqueue(self, background_tasks: BackgroundTasks, generation_id: int) -> None:
        """Add the generation job to FastAPI's background task queue."""
        background_tasks.add_task(self.run_generation_job, generation_id)

    def cancel_generation(
        self, session: Session, generation_id: int
    ) -> Generation | None:
        """Mark a queued or running generation as cancelled. Returns the updated row, or ``None`` if not found."""
        generation = crud.get_generation(session, generation_id, with_assets=True)
        if not generation:
            return None

        if generation.status in {"succeeded", "failed", "cancelled"}:
            return generation

        generation.status = "cancelled"
        generation.error = "Canceled by user."
        generation.failure_sidecar_path = None
        generation.finished_at = datetime.now(UTC)
        session.commit()
        session.refresh(generation)
        return generation

    def delete_asset(self, session: Session, asset_id: int) -> bool:
        """Delete a single asset and its on-disk files.

        Removes the image, sidecar and thumbnail files from storage, deletes the
        ``Asset`` row and commits the session. Returns ``True`` if the asset was
        deleted, ``False`` if it was not found.
        """
        asset = crud.get_asset(session, asset_id, with_generation=True)
        if not asset:
            return False

        self._delete_asset_files(asset)
        session.delete(asset)
        session.commit()
        return True

    def delete_generation(self, session: Session, generation_id: int) -> bool:
        """Delete a generation row together with all of its assets and files.

        Each asset's image, sidecar and thumbnail is removed from storage, the
        generation's failure sidecar (if any) is removed, and the row itself is
        deleted via cascade. Returns ``True`` if the generation was deleted,
        ``False`` if it was not found.
        """
        generation = crud.get_generation(session, generation_id, with_assets=True)
        if not generation:
            return False

        base_dir = self._base_dir_from_snapshot(
            generation.storage_template_snapshot_json
        )

        for asset in generation.assets:
            self._delete_asset_files(asset, base_dir=base_dir)

        if generation.failure_sidecar_path:
            self.storage_service.delete_relative_file(
                base_dir, generation.failure_sidecar_path
            )

        session.delete(generation)
        session.commit()
        return True

    def _delete_asset_files(
        self, asset: Asset, *, base_dir: Path | None = None
    ) -> None:
        """Best-effort removal of the on-disk files associated with *asset*.

        The originating ``base_dir`` is taken from the asset's generation
        snapshot when available. Missing files are silently ignored so a
        partially-cleaned asset row still completes its database delete.
        """
        if not asset.generation:
            return

        resolved_base_dir = base_dir or self._base_dir_from_snapshot(
            asset.generation.storage_template_snapshot_json
        )

        for relative_path in (
            asset.thumbnail_path,
            asset.sidecar_path,
            asset.file_path,
        ):
            if not relative_path:
                continue
            try:
                self.storage_service.delete_relative_file(
                    resolved_base_dir, relative_path
                )
            except (FileNotFoundError, ValueError):
                # File is already gone or the recorded path is unsafe; ignore.
                continue

    async def run_generation_job(self, generation_id: int) -> None:
        """Execute the generation job: call the provider, save files, and update the DB status."""
        with SessionLocal() as session:
            generation = crud.get_generation(session, generation_id)
            if not generation:
                return
            if generation.status == "cancelled":
                return
            if generation.status != "queued":
                return

            generation.status = "running"
            generation.error = None
            session.commit()

            created_files: list[str] = []
            base_dir = self._base_dir_from_snapshot(
                generation.storage_template_snapshot_json
            )
            ensure_dir(base_dir)

            try:
                self._raise_if_cancelled(session, generation_id)
                provider_request = self._provider_request_from_generation(generation)
                provider_request = self._prepare_provider_request(session, provider_request)
                self._raise_if_cancelled(session, generation_id)
                result = await self.registry.generate(
                    generation.provider, provider_request
                )
                self._raise_if_cancelled(session, generation_id)
                if not result.images:
                    raise ProviderError("Provider returned no images")

                storage_template = str(
                    generation.storage_template_snapshot_json.get(
                        "template", self.settings.default_storage_template
                    )
                )
                output_format = (
                    str(generation.request_snapshot_json.get("output_format", "png"))
                    .lower()
                    .lstrip(".")
                )
                upscale_provider = str(
                    generation.request_snapshot_json.get("upscale_provider") or ""
                ).strip().lower()
                upscale_model = str(
                    generation.request_snapshot_json.get("upscale_model") or ""
                ).strip()
                upscale_topaz_model_id = self._parse_optional_int(
                    generation.request_snapshot_json.get("upscale_topaz_model_id")
                )
                upscale_enabled = bool(upscale_provider)

                if upscale_enabled and upscale_provider == "local":
                    if not self.upscale_service:
                        raise ProviderError("Upscaling service is not available")
                    if not self.upscale_service.is_available():
                        raise ProviderError("Upscaling is not configured on this server")
                elif upscale_enabled and upscale_provider == "fal":
                    if not self.fal_upscale_service:
                        raise ProviderError("FAL.ai upscaling service is not available")
                    fal_api_key = (
                        self.model_config_service.get_default_api_key("fal")
                        if self.model_config_service
                        else None
                    )
                    if not fal_api_key:
                        raise ProviderError(
                            "FAL.ai API key is not configured. Set it in Admin → Upscaling."
                        )

                if upscale_enabled:
                    request_snapshot = dict(generation.request_snapshot_json or {})
                    request_snapshot["upscaling_active"] = True
                    generation.request_snapshot_json = request_snapshot
                    session.commit()
                category_ids = self._parse_int_list(
                    generation.request_snapshot_json.get("category_ids")
                )
                categories = crud.list_categories_by_ids(session, category_ids)

                for idx, image in enumerate(result.images, start=1):
                    self._raise_if_cancelled(session, generation_id)
                    image_data = image.data
                    image_width = image.width
                    image_height = image.height
                    image_mime = image.mime
                    upscale_meta = None
                    if upscale_enabled and upscale_provider == "local" and self.upscale_service:
                        (
                            image_data,
                            image_width,
                            image_height,
                            image_mime,
                        ) = self.upscale_service.upscale_bytes(
                            image.data,
                            output_format,
                            upscale_model,
                        )
                        upscale_meta = {
                            "model": upscale_model,
                            "tool": "realesrgan",
                        }
                    elif upscale_enabled and upscale_provider == "fal" and self.fal_upscale_service:
                        topaz_config = None
                        topaz_params: dict[str, Any] = {}
                        topaz_model_identifier = upscale_model or None
                        if upscale_topaz_model_id is not None and upscale_topaz_model_id > 0:
                            topaz_config = crud.get_topaz_upscale_model(
                                session, upscale_topaz_model_id
                            )
                            if not topaz_config:
                                raise ProviderError("Selected Topaz upscale model no longer exists")
                            if not topaz_config.is_enabled:
                                raise ProviderError("Selected Topaz upscale model is disabled")
                            topaz_model_identifier = topaz_config.model_identifier
                            if isinstance(topaz_config.params_json, dict):
                                topaz_params = dict(topaz_config.params_json)

                        fal_api_key = (
                            self.model_config_service.get_default_api_key("fal")
                            if self.model_config_service
                            else None
                        ) or ""
                        (
                            image_data,
                            image_width,
                            image_height,
                            image_mime,
                        ) = await self.fal_upscale_service.upscale_bytes(
                            image.data,
                            output_format,
                            fal_api_key,
                            model_identifier=topaz_model_identifier,
                            model_params=topaz_params,
                        )
                        upscale_meta = {
                            "model": topaz_model_identifier or "fal-ai/topaz/upscale/image",
                            "tool": "fal",
                            "topaz_model_id": upscale_topaz_model_id,
                            "topaz_model_name": topaz_config.name if topaz_config else None,
                            "topaz_params": topaz_params,
                        }
                    (
                        image_data,
                        image_width,
                        image_height,
                        image_mime,
                    ) = self._normalize_image_for_output(
                        data=image_data,
                        output_format=output_format,
                        fallback_mime=image_mime,
                        fallback_width=image_width,
                        fallback_height=image_height,
                    )
                    rendered_rel_path = self.storage_service.render_relative_path(
                        template=storage_template,
                        profile_name=generation.profile_name,
                        prompt_user=generation.prompt_user,
                        generation_id=generation.id,
                        idx=idx,
                        ext=output_format,
                    )
                    rel_path = rendered_rel_path
                    abs_path = self.storage_service.resolve_managed_path(
                        base_dir, rel_path
                    )
                    self.storage_service.write_bytes_atomic(abs_path, image_data)
                    created_files.append(rel_path.as_posix())

                    # If this is a style generation, copy to style path
                    if idx == 1 and generation.request_snapshot_json.get("is_style_generation"):
                        style_id = generation.request_snapshot_json.get("style_id")
                        if style_id:
                            style = crud.get_style(session, style_id)
                            if style:
                                style_dir = self.settings.data_dir / "styles"
                                ensure_dir(style_dir)
                                style_image_path = style_dir / f"{style_id}.webp"
                                # We can reuse image_data directly or write from file
                                self.storage_service.write_bytes_atomic(style_image_path, image_data)
                                crud.update_style(session, style, image_path=f"styles/{style_id}.webp")

                    thumb_rel = self.thumbnail_service.create_thumbnail(
                        base_dir, rel_path
                    )
                    created_files.append(thumb_rel.as_posix())

                    sidecar_payload = self._build_asset_sidecar_payload(
                        generation=generation,
                        asset_index=idx,
                        image_rel=rel_path.as_posix(),
                        thumbnail_rel=thumb_rel.as_posix(),
                        provider_meta=image.meta,
                        raw_meta=result.raw_meta,
                        image_width=image_width,
                        image_height=image_height,
                        image_mime=image_mime,
                    )
                    sidecar_rel = self.sidecar_service.write_asset_sidecar(
                        base_dir, rel_path, sidecar_payload
                    )
                    created_files.append(sidecar_rel.as_posix())

                    session.add(
                        Asset(
                            generation_id=generation.id,
                            file_path=rel_path.as_posix(),
                            sidecar_path=sidecar_rel.as_posix(),
                            thumbnail_path=thumb_rel.as_posix(),
                            width=image_width,
                            height=image_height,
                            mime=image_mime,
                            categories=list(categories),
                            meta_json={
                                "provider_meta": image.meta,
                                "raw_meta": result.raw_meta,
                                "prompt_final": generation.prompt_final,
                                "upscale": upscale_meta,
                            },
                        )
                    )

                self._raise_if_cancelled(session, generation_id)

                # Final check: refresh and ensure not cancelled before committing success
                session.refresh(generation)
                if generation.status == "cancelled":
                    raise GenerationCancelledError("Canceled by user during finalization.")

                generation.status = "succeeded"
                generation.error = None
                generation.failure_sidecar_path = None
                generation.finished_at = datetime.now(UTC)
                session.commit()
            except GenerationCancelledError as exc:
                session.rollback()
                generation = crud.get_generation(session, generation_id)
                if not generation:
                    return

                for rel in reversed(created_files):
                    try:
                        self.storage_service.delete_relative_file(base_dir, rel)
                    except Exception:
                        pass

                generation.status = "cancelled"
                generation.error = self._error_message_from_exception(exc)
                generation.failure_sidecar_path = None
                generation.finished_at = datetime.now(UTC)
                session.commit()
            except Exception as exc:
                session.rollback()
                generation = crud.get_generation(session, generation_id)
                if not generation or generation.status == "cancelled":
                    return

                for rel in reversed(created_files):
                    try:
                        self.storage_service.delete_relative_file(base_dir, rel)
                    except Exception:
                        pass

                # Reload the storage snapshot after rollback to get base_dir
                storage_snapshot = generation.storage_template_snapshot_json
                failure_base_dir = self._base_dir_from_snapshot(storage_snapshot)
                error_message = self._error_message_from_exception(exc)

                generation.status = "failed"
                generation.error = error_message
                generation.finished_at = datetime.now(UTC)

                failure_payload = self._build_failure_sidecar_payload(generation, exc)
                try:
                    failure_rel = self.sidecar_service.write_failure_sidecar(
                        failure_base_dir,
                        generation.profile_name,
                        generation.id,
                        failure_payload,
                    )
                    generation.failure_sidecar_path = failure_rel.as_posix()
                except Exception:
                    generation.failure_sidecar_path = None

                session.commit()

    def _raise_if_cancelled(self, session: Session, generation_id: int) -> None:
        """Raise ``GenerationCancelledError`` if the generation has been cancelled."""
        generation = session.scalar(
            select(Generation).where(Generation.id == generation_id)
        )
        if generation and generation.status == "cancelled":
            raise GenerationCancelledError("Generation was cancelled by user")

    def _provider_request_from_generation(self, generation: Generation) -> ProviderGenerationRequest:
        """Build a provider request from a generation row's stored snapshots."""
        profile_snapshot = generation.profile_snapshot_json or {}
        request_data = generation.request_snapshot_json or {}
        model_config = (
            self.model_config_service.get_model_config(profile_snapshot.get("model_config_id"))
            if profile_snapshot.get("model_config_id") and self.model_config_service
            else None
        )
        model = str(profile_snapshot.get("model") or "").strip()
        if not model:
            raise ProviderError("Generation request has no model specified")

        api_key: str | None = None
        if self.model_config_service:
            if model_config and getattr(model_config, "use_custom_api_key", False):
                api_key = self.model_config_service.get_api_key(model_config.id)
            else:
                api_key = self.model_config_service.get_default_api_key(
                    generation.provider
                )

        if not api_key:
            raise ProviderError(
                f"No API key configured for provider {generation.provider}. "
                "Please configure an API key for this model in Admin settings."
            )

        input_images: list[ProviderInputImage] = []
        raw_input_images = request_data.get("input_images")
        if isinstance(raw_input_images, list):
            for item in raw_input_images:
                if not isinstance(item, dict):
                    continue
                b64_value = item.get("b64")
                mime = item.get("mime")
                if not isinstance(b64_value, str) or not isinstance(mime, str):
                    continue
                try:
                    image_bytes = base64.b64decode(b64_value)
                except Exception:
                    continue
                input_images.append(ProviderInputImage(data=image_bytes, mime=mime))
        expand_data = request_data.get("expand")
        expand_spec = self._expand_spec_from_snapshot(expand_data)
        return ProviderGenerationRequest(
            prompt=generation.prompt_final,
            width=request_data.get("width"),
            height=request_data.get("height"),
            n_images=int(request_data.get("n_images") or 1),
            seed=request_data.get("seed"),
            output_format=str(request_data.get("output_format") or "png"),
            model=model,
            api_key=api_key,
            params=request_data.get("params_json") or {},
            input_images=input_images,
            mode=str(request_data.get("mode") or "generate").strip().lower(),
            expand=expand_spec,
        )

    def _prepare_provider_request(
        self,
        session: Session,
        request: ProviderGenerationRequest,
    ) -> ProviderGenerationRequest:
        """Return a provider request with expand artifacts prepared when needed."""
        if request.mode != "expand":
            return request
        if not isinstance(request.expand, ExpandSpec):
            raise ProviderError("Expand request is missing its expand specification")
        source_asset_id = request.expand.source_asset_id
        if source_asset_id is None or source_asset_id <= 0:
            raise ProviderError("Expand request is missing the source asset")
        asset = crud.get_asset(session, source_asset_id, with_generation=True)
        if not asset or not asset.generation:
            raise ProviderError("Expand source asset was not found")
        absolute_path = self.asset_absolute_path(asset, which="file")
        if not absolute_path.exists():
            raise ProviderError("Expand source asset file is missing")
        source_bytes = absolute_path.read_bytes()
        try:
            artifacts = ExpandService.prepare(source_bytes, request.expand)
        except Exception as exc:
            raise ProviderError(str(exc)) from exc
        params = dict(request.params or {})
        params.update(expand_to_provider_params(artifacts))
        prompt = request.prompt.strip() if request.prompt else ""
        continuation_prompt = (request.expand.continuation_prompt or "").strip()
        if continuation_prompt:
            prompt = continuation_prompt
        prompt = self._build_expand_prompt(prompt)
        return ProviderGenerationRequest(
            prompt=prompt,
            width=artifacts.target_width,
            height=artifacts.target_height,
            n_images=request.n_images,
            seed=request.seed,
            output_format=request.output_format,
            model=request.model,
            api_key=request.api_key,
            params=params,
            input_images=[
                ProviderInputImage(data=artifacts.padded.data, mime="image/png"),
                ProviderInputImage(data=artifacts.mask_bytes, mime="image/png"),
            ],
            mode=request.mode,
            expand=request.expand,
        )

    def _build_expand_prompt(self, prompt: str) -> str:
        """Return a stricter prompt for edge expansion requests."""
        user_prompt = (prompt or "").strip()
        instructions = (
            "Extend the provided image only into the transparent border areas. "
            "Preserve the original image content, composition, subjects, colors, lighting, "
            "camera angle, and style exactly inside the existing non-transparent region. "
            "Do not redraw, replace, or alter the original image area. "
            "Generate new content only for the missing outer edges so it continues the scene naturally."
        )
        if user_prompt:
            return f"{instructions}\n\nAdditional edge guidance: {user_prompt}"
        return instructions

    def _base_dir_from_snapshot(self, snapshot: dict[str, Any] | None) -> Path:
        candidate = (snapshot or {}).get("base_dir")
        if candidate:
            return Path(str(candidate)).resolve()
        return self.settings.default_base_dir.resolve()

    def asset_absolute_path(self, asset: Asset, which: str = "file") -> Path:
        """Return the absolute path for an asset's image or thumbnail file.

        Args:
            asset: The Asset record to resolve.
            which: Which file to resolve - "file" for the original image, "thumb" for the thumbnail.

        Returns:
            The resolved absolute Path to the file.

        Raises:
            ValueError: If the asset has no generation or the path cannot be resolved.
        """
        if not asset.generation:
            raise ValueError(f"Asset {asset.id} has no associated generation")

        base_dir = self._base_dir_from_snapshot(asset.generation.storage_template_snapshot_json)

        if which == "thumb":
            rel_path = asset.thumbnail_path
        else:
            rel_path = asset.file_path

        if not rel_path:
            raise ValueError(f"Asset {asset.id} has no {which} path")

        return self.storage_service.resolve_managed_path(base_dir, rel_path)

    def _build_asset_sidecar_payload(
        self,
        *,
        generation: Generation,
        asset_index: int,
        image_rel: str,
        thumbnail_rel: str,
        provider_meta: dict[str, Any],
        raw_meta: dict[str, Any],
        image_width: int,
        image_height: int,
        image_mime: str,
    ) -> dict[str, Any]:
        # Build request snapshot without API key (security)
        request_snapshot = copy.deepcopy(generation.request_snapshot_json or {})
        # Remove any base64 encoded images from request to keep file size manageable
        if "input_images" in request_snapshot:
            sanitized_images = []
            for img in request_snapshot.get("input_images", []):
                if isinstance(img, dict):
                    sanitized_img = {
                        "name": img.get("name", ""),
                        "mime": img.get("mime", ""),
                        # Omit b64 data to keep sidecar file small
                    }
                    sanitized_images.append(sanitized_img)
            request_snapshot["input_images"] = sanitized_images

        # Build response snapshot with provider metadata
        response_snapshot = {
            "provider_meta": provider_meta,
            "raw_meta": raw_meta,
            "image": {
                "width": image_width,
                "height": image_height,
                "mime": image_mime,
            },
        }

        return {
            "type": "asset_success",
            "generated_at": datetime.now(UTC).isoformat(),
            "generation_id": generation.id,
            "asset_index": asset_index,
            "image_path": image_rel,
            "thumbnail_path": thumbnail_rel,
            "image": {
                "width": image_width,
                "height": image_height,
                "mime": image_mime,
            },
            "provider_meta": provider_meta,
            "raw_meta": raw_meta,
            "profile_snapshot_json": generation.profile_snapshot_json,
            "storage_template_snapshot_json": generation.storage_template_snapshot_json,
            "request_snapshot_json": request_snapshot,
            "response_snapshot_json": response_snapshot,
        }

    def _build_failure_sidecar_payload(
        self, generation: Generation, exc: Exception
    ) -> dict[str, Any]:
        return {
            "type": "generation_failure",
            "failed_at": datetime.now(UTC).isoformat(),
            "generation_id": generation.id,
            "profile_name": generation.profile_name,
            "provider": generation.provider,
            "model": generation.model,
            "error": self._error_message_from_exception(exc),
            "profile_snapshot_json": generation.profile_snapshot_json,
            "storage_template_snapshot_json": generation.storage_template_snapshot_json,
            "request_snapshot_json": generation.request_snapshot_json,
        }

    def _compose_prompt(self, base_prompt: str, prompt_user: str) -> str:
        base = (base_prompt or "").strip()
        user = (prompt_user or "").strip()
        if base and user:
            return f"{base}\n{user}"
        return base or user

    def _truncate_error(self, value: str, max_len: int = 2048) -> str:
        return value[:max_len]

    def _error_message_from_exception(self, exc: BaseException) -> str:
        """Return a stable, non-empty error message for persisted job failures."""
        text = str(exc).strip()
        if text:
            return self._truncate_error(text)

        # Fallback for exceptions that stringify to an empty string.
        exception_name = exc.__class__.__name__ or "Exception"
        args_text = " ".join(str(value).strip() for value in getattr(exc, "args", ()) if str(value).strip())
        if args_text:
            return self._truncate_error(f"{exception_name}: {args_text}")
        return self._truncate_error(f"{exception_name}: Unknown error")

    def _normalize_image_for_output(
        self,
        *,
        data: bytes,
        output_format: str,
        fallback_mime: str,
        fallback_width: int,
        fallback_height: int,
    ) -> tuple[bytes, int, int, str]:
        if not data:
            raise ProviderError("No image data was provided")

        try:
            with Image.open(BytesIO(data)) as source:
                normalized = ImageOps.exif_transpose(source)
                width, height = normalized.size
                target = self._normalized_output_format(output_format)
                pil_format = self._pil_format_from_output(target)
                if pil_format == "JPEG" and normalized.mode not in {"RGB", "L"}:
                    normalized = normalized.convert("RGB")

                buffer = BytesIO()
                normalized.save(buffer, format=pil_format)
                return (
                    buffer.getvalue(),
                    int(width),
                    int(height),
                    self._mime_from_output(target),
                )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Failed to process image: {exc}") from exc

    def _normalized_output_format(self, value: str) -> str:
        raw = (value or "png").strip().lower().lstrip(".")
        if raw in {"jpg", "jpeg"}:
            return "jpeg"
        if raw in {"png", "webp"}:
            return raw
        return "png"

    def _pil_format_from_output(self, output_format: str) -> str:
        if output_format == "jpeg":
            return "JPEG"
        if output_format == "webp":
            return "WEBP"
        return "PNG"

    def _mime_from_output(self, output_format: str) -> str:
        if output_format == "jpeg":
            return "image/jpeg"
        if output_format == "webp":
            return "image/webp"
        return "image/png"

    def _parse_optional_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _serialize_expand_spec(self, value: Any) -> dict[str, Any] | None:
        """Return a JSON-serializable expand spec snapshot."""
        if not isinstance(value, ExpandSpec):
            return None
        return {
            "top": int(value.top),
            "right": int(value.right),
            "bottom": int(value.bottom),
            "left": int(value.left),
            "fill": str(value.fill or "transparent"),
            "continuation_prompt": (
                str(value.continuation_prompt).strip()
                if isinstance(value.continuation_prompt, str) and str(value.continuation_prompt).strip()
                else None
            ),
            "source_asset_id": self._parse_optional_int(value.source_asset_id),
        }

    def _expand_spec_from_snapshot(self, value: Any) -> ExpandSpec | None:
        """Rebuild an ``ExpandSpec`` from stored snapshot data."""
        if not isinstance(value, dict):
            return None
        return ExpandSpec(
            top=int(value.get("top") or 0),
            right=int(value.get("right") or 0),
            bottom=int(value.get("bottom") or 0),
            left=int(value.get("left") or 0),
            fill=str(value.get("fill") or "transparent"),
            continuation_prompt=(
                str(value.get("continuation_prompt")).strip()
                if isinstance(value.get("continuation_prompt"), str)
                and str(value.get("continuation_prompt")).strip()
                else None
            ),
            source_asset_id=self._parse_optional_int(value.get("source_asset_id")),
        )

    def _parse_int_list(self, value: Any) -> list[int]:
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        parsed: list[int] = []
        for item in value:
            try:
                parsed.append(int(item))
            except (TypeError, ValueError):
                continue
        return sorted({item for item in parsed if item > 0})
