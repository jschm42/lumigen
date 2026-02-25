from __future__ import annotations

import base64
import copy
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import crud
from app.db.engine import SessionLocal
from app.db.models import Asset, Generation, Profile
from app.providers.base import (
    ProviderError,
    ProviderGenerationRequest,
    ProviderInputImage,
)
from app.providers.registry import ProviderRegistry
from app.services.model_config_service import ModelConfigService
from app.services.sidecar_service import SidecarService
from app.services.storage_service import StorageService
from app.services.thumbnail_service import ThumbnailService
from app.services.upscale_service import UpscaleService
from app.utils.paths import ensure_dir


class GenerationCancelledError(ProviderError):
    pass


class GenerationService:
    def __init__(
        self,
        settings: Settings,
        registry: ProviderRegistry,
        storage_service: StorageService,
        thumbnail_service: ThumbnailService,
        sidecar_service: SidecarService,
        model_config_service: ModelConfigService | None = None,
        upscale_service: UpscaleService | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.storage_service = storage_service
        self.thumbnail_service = thumbnail_service
        self.sidecar_service = sidecar_service
        self.model_config_service = model_config_service
        self.upscale_service = upscale_service

    def create_generation_from_profile(
        self,
        session: Session,
        profile: Profile,
        prompt_user: str,
        overrides: Optional[dict[str, Any]] = None,
    ) -> Generation:
        prompt_final = self._compose_prompt(profile.base_prompt, prompt_user)
        storage_template = profile.storage_template
        if storage_template is None:
            raise ValueError("Profile has no storage template")
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
        upscale_model_override = effective_overrides.get("upscale_model")
        if isinstance(upscale_model_override, str) and upscale_model_override.strip():
            upscale_model = upscale_model_override.strip()
        else:
            upscale_model = str(profile.upscale_model or "").strip() or None
        input_images = effective_overrides.get("input_images")
        chat_session_id = str(effective_overrides.get("chat_session_id") or "").strip()
        profile_category_ids = [item.id for item in profile.categories]
        category_ids = self._parse_int_list(
            effective_overrides.get("category_ids", profile_category_ids)
        )

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
            "upscale_model": profile.upscale_model,
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
            "prompt_final": prompt_final,
            "chat_session_id": chat_session_id or None,
            "width": width,
            "height": height,
            "n_images": max(1, n_images),
            "seed": seed,
            "upscale_model": upscale_model,
            "output_format": profile.output_format,
            "provider": profile.provider,
            "model": profile.model,
            "model_config_id": profile.model_config_id,
            "params_json": params_json,
            "category_ids": category_ids,
            "input_images": input_images or [],
            "overrides": {
                "width": "width" in effective_overrides,
                "height": "height" in effective_overrides,
                "n_images": "n_images" in effective_overrides,
                "seed": "seed" in effective_overrides,
                "params_json": "params_json" in effective_overrides,
                "upscale_model": "upscale_model" in effective_overrides,
                "category_ids": "category_ids" in effective_overrides,
                "input_images": "input_images" in effective_overrides,
                "chat_session_id": "chat_session_id" in effective_overrides,
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

    def create_generation_from_snapshot(
        self, session: Session, source: Generation
    ) -> Generation:
        profile_snapshot = copy.deepcopy(source.profile_snapshot_json or {})
        storage_snapshot = copy.deepcopy(source.storage_template_snapshot_json or {})
        request_snapshot = copy.deepcopy(source.request_snapshot_json or {})

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
        background_tasks.add_task(self.run_generation_job, generation_id)

    def cancel_generation(
        self, session: Session, generation_id: int
    ) -> Optional[Generation]:
        generation = crud.get_generation(session, generation_id, with_assets=True)
        if not generation:
            return None

        if generation.status in {"succeeded", "failed", "cancelled"}:
            return generation

        generation.status = "cancelled"
        generation.error = "Cancelled by user."
        generation.failure_sidecar_path = None
        generation.finished_at = datetime.utcnow()
        session.commit()
        session.refresh(generation)
        return generation

    async def run_generation_job(self, generation_id: int) -> None:
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
                self._raise_if_cancelled(session, generation_id)
                result = await self.registry.generate(
                    generation.provider, provider_request
                )
                self._raise_if_cancelled(session, generation_id)
                if not result.images:
                    raise ProviderError("Provider returned zero images")

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
                upscale_model = str(
                    generation.request_snapshot_json.get("upscale_model") or ""
                ).strip()
                upscale_enabled = bool(upscale_model)
                if upscale_enabled and not self.upscale_service:
                    raise ProviderError("Upscale service is not available.")
                if upscale_enabled and not self.upscale_service.is_available():
                    raise ProviderError("Upscaler is not configured on this server.")
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
                    if upscale_enabled and self.upscale_service:
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
                generation.status = "succeeded"
                generation.error = None
                generation.failure_sidecar_path = None
                generation.finished_at = datetime.utcnow()
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
                generation.error = self._truncate_error(str(exc))
                generation.failure_sidecar_path = None
                generation.finished_at = datetime.utcnow()
                session.commit()
            except Exception as exc:
                session.rollback()
                generation = crud.get_generation(session, generation_id)
                if not generation:
                    return

                for rel in reversed(created_files):
                    try:
                        self.storage_service.delete_relative_file(base_dir, rel)
                    except Exception:
                        pass

                # Reload the storage snapshot after rollback to get base_dir
                storage_snapshot = generation.storage_template_snapshot_json
                failure_base_dir = self._base_dir_from_snapshot(storage_snapshot)

                generation.status = "failed"
                generation.error = self._truncate_error(str(exc))
                generation.finished_at = datetime.utcnow()

                failure_payload = self._build_failure_sidecar_payload(generation, exc)
                try:
                    failure_rel = self.sidecar_service.write_failure_sidecar(
                        failure_base_dir,
                        generation.profile_name,
                        generation.id,
                        failure_payload,
                    )
                    generation.failure_sidecar_path = failure_rel.as_posix()
                except Exception as sidecar_exc:
                    generation.failure_sidecar_path = None
                    # Log the error for debugging but don't add to generation.error
                    # since we already have the main error
                    logging.getLogger(__name__).error(
                        f"Failed to write failure sidecar for generation {generation.id}: {sidecar_exc}"
                    )

                session.commit()

    def _raise_if_cancelled(self, session: Session, generation_id: int) -> None:
        generation = crud.get_generation(session, generation_id)
        if not generation:
            raise GenerationCancelledError("Generation no longer exists.")
        session.refresh(generation)
        if generation.status == "cancelled":
            raise GenerationCancelledError("Cancelled by user.")

    def delete_asset(self, session: Session, asset_id: int) -> bool:
        asset = crud.get_asset(session, asset_id, with_generation=True)
        if not asset or not asset.generation:
            return False

        base_dir = self._base_dir_from_snapshot(
            asset.generation.storage_template_snapshot_json
        )
        for rel in (asset.file_path, asset.thumbnail_path, asset.sidecar_path):
            self.storage_service.delete_relative_file(base_dir, rel)

        session.delete(asset)
        session.commit()
        return True

    def delete_generation(self, session: Session, generation_id: int) -> bool:
        generation = crud.get_generation(session, generation_id, with_assets=True)
        if not generation:
            return False

        base_dir = self._base_dir_from_snapshot(
            generation.storage_template_snapshot_json
        )
        for asset in list(generation.assets):
            for rel in (asset.file_path, asset.thumbnail_path, asset.sidecar_path):
                self.storage_service.delete_relative_file(base_dir, rel)

        if generation.failure_sidecar_path:
            self.storage_service.delete_relative_file(
                base_dir, generation.failure_sidecar_path
            )

        session.delete(generation)
        session.commit()
        return True

    def asset_absolute_path(self, asset: Asset, which: str = "file") -> Path:
        generation = asset.generation
        if not generation:
            raise ValueError("Asset has no associated generation")
        base_dir = self._base_dir_from_snapshot(
            generation.storage_template_snapshot_json
        )
        rel = asset.file_path if which == "file" else asset.thumbnail_path
        return self.storage_service.resolve_managed_path(base_dir, rel)

    def _provider_request_from_generation(
        self, generation: Generation
    ) -> ProviderGenerationRequest:
        request_data = generation.request_snapshot_json or {}
        
        # Validate model is set
        model = str(request_data.get("model") or generation.model or "").strip()
        if not model:
            raise ProviderError(
                "Model configuration error: Model not specified. "
                "Please check the profile's model configuration in Admin settings."
            )
        
        # Get API key - check model config to decide which key to use
        api_key = None
        model_config_id = self._parse_optional_int(request_data.get("model_config_id"))
        provider = str(request_data.get("provider") or generation.provider or "").strip()
        
        if model_config_id is not None and self.model_config_service:
            # Get the model config to check if custom API key is enabled
            config = self.model_config_service.get_model_config(model_config_id)
            
            if config and config.use_custom_api_key:
                # Use custom API key if enabled
                api_key = self.model_config_service.get_api_key(model_config_id)
            else:
                # Fall back to environment variable
                if provider:
                    api_key = self.model_config_service.get_default_api_key(provider)
        elif provider and self.model_config_service:
            # No model config, try to use env variable directly
            api_key = self.model_config_service.get_default_api_key(provider)
        
        # Validate API key is available
        if not api_key:
            raise ProviderError(
                "Model configuration error: API key not found. "
                "Please configure the API key for this model in Admin settings."
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
        )

    def _base_dir_from_snapshot(self, snapshot: Optional[dict[str, Any]]) -> Path:
        candidate = (snapshot or {}).get("base_dir")
        if candidate:
            return Path(str(candidate)).resolve()
        return self.settings.default_base_dir.resolve()

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
            "generated_at": datetime.utcnow().isoformat(),
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
            "failed_at": datetime.utcnow().isoformat(),
            "generation_id": generation.id,
            "profile_name": generation.profile_name,
            "provider": generation.provider,
            "model": generation.model,
            "error": self._truncate_error(str(exc)),
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
            raise ProviderError("No image data provided")

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
            raise ProviderError(f"Cannot process image: {exc}") from exc

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

    def _parse_optional_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

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
