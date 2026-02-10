from __future__ import annotations

import base64
import copy
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Optional

from fastapi import BackgroundTasks
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
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.storage_service = storage_service
        self.thumbnail_service = thumbnail_service
        self.sidecar_service = sidecar_service
        self.model_config_service = model_config_service

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

        negative_prompt = profile.negative_prompt
        if "negative_prompt" in effective_overrides:
            negative_prompt = effective_overrides.get("negative_prompt")

        width = effective_overrides.get("width", profile.width)
        height = effective_overrides.get("height", profile.height)
        aspect_ratio = effective_overrides.get("aspect_ratio", profile.aspect_ratio)
        n_images = int(effective_overrides.get("n_images", profile.n_images) or 1)
        seed = effective_overrides.get("seed", profile.seed)
        gallery_folder_id = effective_overrides.get("gallery_folder_id")
        gallery_folder_path = effective_overrides.get("gallery_folder_path")
        input_images = effective_overrides.get("input_images")

        profile_snapshot = {
            "id": profile.id,
            "name": profile.name,
            "provider": profile.provider,
            "model": profile.model,
            "model_config_id": profile.model_config_id,
            "base_prompt": profile.base_prompt,
            "negative_prompt": profile.negative_prompt,
            "width": profile.width,
            "height": profile.height,
            "aspect_ratio": profile.aspect_ratio,
            "n_images": profile.n_images,
            "seed": profile.seed,
            "output_format": profile.output_format,
            "params_json": profile.params_json or {},
            "storage_template_id": profile.storage_template_id,
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
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "n_images": max(1, n_images),
            "seed": seed,
            "output_format": profile.output_format,
            "provider": profile.provider,
            "model": profile.model,
            "model_config_id": profile.model_config_id,
            "params_json": profile.params_json or {},
            "gallery_folder_id": gallery_folder_id,
            "gallery_folder_path": gallery_folder_path,
            "input_images": input_images or [],
            "overrides": {
                "negative_prompt": "negative_prompt" in effective_overrides,
                "width": "width" in effective_overrides,
                "height": "height" in effective_overrides,
                "aspect_ratio": "aspect_ratio" in effective_overrides,
                "n_images": "n_images" in effective_overrides,
                "seed": "seed" in effective_overrides,
                "gallery_folder_id": "gallery_folder_id" in effective_overrides,
                "gallery_folder_path": "gallery_folder_path" in effective_overrides,
                "input_images": "input_images" in effective_overrides,
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
                folder_path = self._resolve_gallery_folder_path(session, generation)

                for idx, image in enumerate(result.images, start=1):
                    self._raise_if_cancelled(session, generation_id)
                    rendered_rel_path = self.storage_service.render_relative_path(
                        template=storage_template,
                        profile_name=generation.profile_name,
                        prompt_user=generation.prompt_user,
                        generation_id=generation.id,
                        idx=idx,
                        ext=output_format,
                    )
                    rel_path = (
                        Path(folder_path) / rendered_rel_path.name
                        if folder_path
                        else rendered_rel_path
                    )
                    abs_path = self.storage_service.resolve_managed_path(
                        base_dir, rel_path
                    )
                    self.storage_service.write_bytes_atomic(abs_path, image.data)
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
                        image_width=image.width,
                        image_height=image.height,
                        image_mime=image.mime,
                    )
                    sidecar_rel = self.sidecar_service.write_asset_sidecar(
                        base_dir, rel_path, sidecar_payload
                    )
                    created_files.append(sidecar_rel.as_posix())

                    session.add(
                        Asset(
                            generation_id=generation.id,
                            gallery_folder_id=self._parse_optional_int(
                                generation.request_snapshot_json.get(
                                    "gallery_folder_id"
                                )
                            ),
                            file_path=rel_path.as_posix(),
                            sidecar_path=sidecar_rel.as_posix(),
                            thumbnail_path=thumb_rel.as_posix(),
                            width=image.width,
                            height=image.height,
                            mime=image.mime,
                            meta_json={
                                "provider_meta": image.meta,
                                "raw_meta": result.raw_meta,
                                "prompt_final": generation.prompt_final,
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

                generation.status = "failed"
                generation.error = self._truncate_error(str(exc))
                generation.finished_at = datetime.utcnow()

                failure_payload = self._build_failure_sidecar_payload(generation, exc)
                try:
                    failure_rel = self.sidecar_service.write_failure_sidecar(
                        base_dir,
                        generation.profile_name,
                        generation.id,
                        failure_payload,
                    )
                    generation.failure_sidecar_path = failure_rel.as_posix()
                except Exception as sidecar_exc:
                    generation.failure_sidecar_path = None
                    generation.error = self._truncate_error(
                        f"{generation.error}; failure-sidecar-write={sidecar_exc}"
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
        api_key = None
        model_config_id = self._parse_optional_int(request_data.get("model_config_id"))
        if model_config_id is not None and self.model_config_service:
            api_key = self.model_config_service.get_api_key(model_config_id)
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
            negative_prompt=request_data.get("negative_prompt"),
            width=request_data.get("width"),
            height=request_data.get("height"),
            aspect_ratio=request_data.get("aspect_ratio"),
            n_images=int(request_data.get("n_images") or 1),
            seed=request_data.get("seed"),
            output_format=str(request_data.get("output_format") or "png"),
            model=str(request_data.get("model") or generation.model),
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
            "request_snapshot_json": generation.request_snapshot_json,
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

    def _parse_optional_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _resolve_gallery_folder_path(
        self, session: Session, generation: Generation
    ) -> Optional[str]:
        request = generation.request_snapshot_json or {}
        normalized = self._normalize_folder_path(request.get("gallery_folder_path"))
        if normalized:
            return normalized

        folder_id = self._parse_optional_int(request.get("gallery_folder_id"))
        if folder_id is None:
            return None
        folder = crud.get_gallery_folder(session, folder_id)
        if not folder:
            return None
        return self._normalize_folder_path(folder.path)

    def _normalize_folder_path(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        raw = str(value).strip().replace("\\", "/").strip("/")
        if not raw:
            return None
        posix_path = PurePosixPath(raw)
        if posix_path.is_absolute() or ".." in posix_path.parts:
            return None
        parts = [
            part.strip() for part in posix_path.parts if part.strip() and part != "."
        ]
        if not parts:
            return None
        return PurePosixPath(*parts).as_posix()
