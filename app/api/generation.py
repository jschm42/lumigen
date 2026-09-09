"""Generation REST API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import crud
from app.db.engine import get_session
from app.providers.fal_upscale_adapter import FalUpscaleService
from app.providers.registry import ProviderRegistry
from app.services.enhancement_service import EnhancementService
from app.services.generation_service import GenerationService
from app.services.model_config_service import ModelConfigService
from app.services.sidecar_service import SidecarService
from app.services.storage_service import StorageService
from app.services.thumbnail_service import ThumbnailService
from app.services.upscale_service import UpscaleService

router = APIRouter(tags=["generation"])
settings = get_settings()

storage_service = StorageService(max_slug_length=settings.max_slug_length)
thumbnail_service = ThumbnailService(storage_service, max_px=settings.thumb_max_px)
sidecar_service = SidecarService(storage_service)
model_config_service = ModelConfigService(settings)
enhancement_service = EnhancementService(settings, model_config_service)
upscale_service = UpscaleService(settings)
fal_upscale_service = FalUpscaleService()
provider_registry = ProviderRegistry(settings)

generation_service = GenerationService(
    settings=settings,
    registry=provider_registry,
    storage_service=storage_service,
    thumbnail_service=thumbnail_service,
    sidecar_service=sidecar_service,
    model_config_service=model_config_service,
    upscale_service=upscale_service,
    fal_upscale_service=fal_upscale_service,
)


@router.post("/generate")
async def api_generate_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Submit a prompt generation job and return the job_id."""
    content_type = request.headers.get("content-type", "")

    input_files: list[Any] = []
    if content_type.startswith("application/json"):
        payload = await request.json()
        prompt = payload.get("prompt", "").strip()
        negative_prompt = payload.get("negative_prompt")
        profile_id = payload.get("profile_id")
        model_config_id = payload.get("model_config_id")
        aspect_ratio = payload.get("aspect_ratio", "1:1")
        resolution = payload.get("resolution", "1K")
        image_size = payload.get("image_size", "")
        fal_aspect_ratio = payload.get("fal_aspect_ratio", "")
        fal_resolution = payload.get("fal_resolution", "")
        google_aspect_ratio = payload.get("google_aspect_ratio", "")
        google_resolution = payload.get("google_resolution", "")
        width = payload.get("width")
        height = payload.get("height")
        n_images = payload.get("n_images")
        seed = payload.get("seed")
        conversation = payload.get("conversation", "")
        style_id = payload.get("style_id")
        upscale_model = payload.get("upscale_model", "__profile__")
        input_image_asset_id = payload.get("asset_id") or payload.get("input_image_asset_id")
    else:
        form = await request.form()
        prompt = str(form.get("prompt", "")).strip()
        negative_prompt = str(form.get("negative_prompt")) if form.get("negative_prompt") else None
        profile_id = int(form.get("profile_id")) if form.get("profile_id") else None
        model_config_id = int(form.get("model_config_id")) if form.get("model_config_id") else None
        aspect_ratio = str(form.get("aspect_ratio", "1:1"))
        resolution = str(form.get("resolution", "1K"))
        image_size = str(form.get("image_size", ""))
        fal_aspect_ratio = str(form.get("fal_aspect_ratio", ""))
        fal_resolution = str(form.get("fal_resolution", ""))
        google_aspect_ratio = str(form.get("google_aspect_ratio", ""))
        google_resolution = str(form.get("google_resolution", ""))
        width = form.get("width")
        height = form.get("height")
        n_images = form.get("n_images")
        seed = str(form.get("seed")) if form.get("seed") else None
        conversation = str(form.get("conversation", ""))
        style_id = str(form.get("style_id")) if form.get("style_id") else None
        upscale_model = str(form.get("upscale_model", "__profile__"))
        input_image_asset_id = form.get("asset_id") or form.get("input_image_asset_id")

        # Collect uploaded image files from form
        for key in ("images", "input_images"):
            files = form.getlist(key)
            for f in files:
                if hasattr(f, "filename") and f.filename:
                    input_files.append(f)

    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    if style_id:
        try:
            s_obj = crud.get_style(session, int(style_id))
            if s_obj and s_obj.prompt:
                prompt = s_obj.prompt.replace("{prompt}", prompt) if "{prompt}" in s_obj.prompt else f"{prompt}, {s_obj.prompt}"
            if s_obj and s_obj.negative_prompt:
                negative_prompt = f"{negative_prompt or ''}, {s_obj.negative_prompt}".strip(", ")
        except (ValueError, TypeError):
            pass

    profile = None
    if profile_id:
        profile = crud.get_profile(session, profile_id)
    if not profile:
        profiles = crud.list_profiles(session)
        profile = profiles[0] if profiles else None

    if not profile:
        profile = crud.create_profile(
            session,
            name="Default",
            aspect_ratio="1:1",
            resolution="1K",
        )

    overrides: dict[str, Any] = {}
    import base64

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.db.models import Asset
    from app.main import (
        MAX_INPUT_IMAGES,
        _sanitize_mime_type,
        _session_input_base_dir,
        apply_fal_image_config,
        apply_google_image_config,
        apply_openrouter_image_config,
        build_chat_session_token,
    )

    conversation_value = (conversation or "").strip()
    if not conversation_value:
        conversation_value = build_chat_session_token()
    overrides["chat_session_id"] = conversation_value

    chat_session = crud.get_chat_session(session, conversation_value)
    if not chat_session:
        raw_prompt = prompt.strip().replace("\r\n", " ").replace("\n", " ")
        cleaned_title = raw_prompt[:40].rsplit(" ", 1)[0] if len(raw_prompt) > 40 else raw_prompt
        cleaned_title = cleaned_title.strip() or "Neue Session"
        crud.create_chat_session(
            session,
            chat_session_id=conversation_value,
            title=cleaned_title,
            last_profile_id=profile.id if profile else None,
            last_model_config_id=model_config_id,
        )

    if model_config_id:
        model_cfg = crud.get_model_config(session, model_config_id)
        if model_cfg:
            overrides["model_config_id"] = model_cfg.id
            overrides["provider"] = model_cfg.provider
            overrides["model"] = model_cfg.model
    elif getattr(profile, "model_config_id", None):
        model_cfg = crud.get_model_config(session, profile.model_config_id)
        if model_cfg:
            overrides["model_config_id"] = model_cfg.id
            overrides["provider"] = model_cfg.provider
            overrides["model"] = model_cfg.model

    provider_value = str(overrides.get("provider") or profile.provider or "").strip().lower()

    # Process and encode input images
    encoded_images: list[dict[str, str]] = []

    # 1. DB-persisted session input images
    session_input_images = crud.list_session_input_images(session, conversation_value)
    for row in session_input_images:
        if row.source_type == "asset" and row.asset_id:
            asset = session.scalar(
                select(Asset)
                .options(selectinload(Asset.generation))
                .where(Asset.id == row.asset_id)
            )
            if not asset or not asset.generation:
                continue
            absolute_path = generation_service.asset_absolute_path(asset, which="file")
            if absolute_path.exists():
                with open(absolute_path, "rb") as f_img:
                    encoded_images.append({
                        "name": row.file_name or f"asset_{asset.id}",
                        "mime": row.mime_type or asset.mime,
                        "b64": base64.b64encode(f_img.read()).decode("ascii"),
                    })
        elif row.source_type == "uploaded" and row.original_file_path:
            try:
                absolute_path = storage_service.resolve_managed_path(
                    _session_input_base_dir(),
                    row.original_file_path,
                )
                if absolute_path.exists():
                    with open(absolute_path, "rb") as f_img:
                        encoded_images.append({
                            "name": row.file_name or "input",
                            "mime": _sanitize_mime_type(row.mime_type),
                            "b64": base64.b64encode(f_img.read()).decode("ascii"),
                        })
            except ValueError:
                pass

    def _parse_int(val: Any) -> int | None:
        if val is None or val == "":
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    # 2. Asset ID from form/json
    parsed_asset_id = _parse_int(input_image_asset_id)
    if parsed_asset_id:
        asset = session.scalar(
            select(Asset)
            .options(selectinload(Asset.generation))
            .where(Asset.id == parsed_asset_id)
        )
        if asset and asset.generation:
            absolute_path = generation_service.asset_absolute_path(asset, which="file")
            if absolute_path.exists():
                with open(absolute_path, "rb") as f_img:
                    encoded_images.append({
                        "name": f"asset_{asset.id}",
                        "mime": asset.mime,
                        "b64": base64.b64encode(f_img.read()).decode("ascii"),
                    })

    # 3. Direct uploaded files
    for upload in input_files:
        content_type = (getattr(upload, "content_type", None) or "").lower()
        if not content_type.startswith("image/"):
            continue
        file_bytes = await upload.read()
        if file_bytes:
            encoded_images.append({
                "name": getattr(upload, "filename", "input") or "input",
                "mime": content_type,
                "b64": base64.b64encode(file_bytes).decode("ascii"),
            })

    if encoded_images:
        overrides["input_images"] = encoded_images[:MAX_INPUT_IMAGES]

    # Provider specific sizing & dimension overrides
    if provider_value == "openrouter":
        params_json_copy = dict(profile.params_json or {})
        params_json_with_overrides = apply_openrouter_image_config(
            params_json=params_json_copy,
            provider=provider_value,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            allow_clear=False,
        )
        overrides["params_json"] = params_json_with_overrides
    elif provider_value == "fal":
        params_json_copy = dict(profile.params_json or {})
        params_json_with_overrides = apply_fal_image_config(
            params_json=params_json_copy,
            provider=provider_value,
            fal_aspect_ratio=fal_aspect_ratio,
            fal_resolution=fal_resolution or resolution,
            allow_clear=False,
        )
        overrides["params_json"] = params_json_with_overrides
    elif provider_value == "google":
        params_json_copy = dict(profile.params_json or {})
        params_json_with_overrides = apply_google_image_config(
            params_json=params_json_copy,
            provider=provider_value,
            google_aspect_ratio=google_aspect_ratio or aspect_ratio,
            google_resolution=google_resolution or resolution,
            allow_clear=False,
        )
        overrides["params_json"] = params_json_with_overrides
    else:
        # Standard custom width / height
        w_val = _parse_int(width)
        h_val = _parse_int(height)
        if w_val and w_val > 0:
            overrides["width"] = w_val
        if h_val and h_val > 0:
            overrides["height"] = h_val

    if aspect_ratio:
        overrides["aspect_ratio"] = aspect_ratio
    if resolution:
        overrides["resolution"] = resolution

    n_images_val = _parse_int(n_images)
    if n_images_val is not None:
        overrides["n_images"] = max(1, min(8, n_images_val))

    if seed is not None and seed != "":
        parsed_seed = _parse_int(seed)
        if parsed_seed is not None:
            overrides["seed"] = parsed_seed

    if negative_prompt:
        overrides["negative_prompt"] = negative_prompt

    # Upscale overrides
    upscale_choice = (upscale_model or "__profile__").strip()
    if upscale_choice == "__none__":
        overrides["upscale_provider"] = None
        overrides["upscale_model"] = None
        overrides["upscale_topaz_model_id"] = None
    elif upscale_choice == "fal":
        overrides["upscale_provider"] = "fal"
        overrides["upscale_model"] = None
        overrides["upscale_topaz_model_id"] = None
    elif upscale_choice.startswith("falm:") or upscale_choice.startswith("topaz:"):
        fal_model_id = _parse_int(upscale_choice.split(":", 1)[1])
        if fal_model_id:
            fal_model = crud.get_topaz_upscale_model(session, fal_model_id)
            if fal_model and fal_model.is_enabled:
                overrides["upscale_provider"] = "fal"
                overrides["upscale_model"] = fal_model.model_identifier
                overrides["upscale_topaz_model_id"] = fal_model.id
    elif upscale_choice.startswith("local:"):
        local_model = upscale_choice.split(":", 1)[1]
        if upscale_service.is_available():
            overrides["upscale_provider"] = "local"
            overrides["upscale_model"] = local_model

    generation = generation_service.create_generation_from_profile(
        session,
        profile,
        prompt,
        overrides=overrides or None,
    )
    generation_service.enqueue(background_tasks, generation.id)

    return {
        "job_id": generation.id,
        "status": generation.status,
        "session_token": conversation_value,
    }


@router.get("/jobs/{generation_id}/status")
def get_job_status(
    generation_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get the current status, progress, and assets for a generation job."""
    from app.api.assets import serialize_asset

    gen = crud.get_generation(session, generation_id)
    if not gen:
        raise HTTPException(status_code=404, detail="Generation job not found")

    req_snapshot = gen.request_snapshot_json or {}
    assets_list = [serialize_asset(a, gen) for a in gen.assets]
    progress = 100 if gen.status == "succeeded" else (0 if gen.status == "failed" else 50)

    return {
        "id": gen.id,
        "status": gen.status,
        "progress": progress,
        "error_message": gen.error,
        "prompt": gen.prompt_user or gen.prompt_final,
        "negative_prompt": req_snapshot.get("negative_prompt", ""),
        "session_token": req_snapshot.get("chat_session_id") or req_snapshot.get("conversation", ""),
        "created_at": gen.created_at.isoformat() if gen.created_at else "",
        "completed_at": gen.finished_at.isoformat() if gen.finished_at else None,
        "model_name": gen.model,
        "provider": gen.provider,
        "aspect_ratio": req_snapshot.get("aspect_ratio", "1:1"),
        "resolution": req_snapshot.get("resolution", "1K"),
        "seed": req_snapshot.get("seed"),
        "assets": assets_list,
    }


@router.post("/enhance-prompt")
async def api_enhance_prompt(
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """AI Prompt Enhancement endpoint."""
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        payload = await request.json()
        prompt = payload.get("prompt", "").strip()
        llm_model = payload.get("llm_model", "gemini-2.5-flash")
    else:
        form = await request.form()
        prompt = str(form.get("prompt", "")).strip()
        llm_model = str(form.get("llm_model", "gemini-2.5-flash"))

    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    try:
        enhanced = await enhancement_service.enhance_prompt(
            session=session,
            prompt=prompt,
            model_identifier=llm_model,
        )
        return {
            "enhanced_prompt": enhanced,
        }
    except Exception:
        # Graceful fallback enhancement if provider key is not yet set
        enhanced_fallback = f"{prompt}, highly detailed, cinematic lighting, masterpiece, 8k resolution"
        return {
            "enhanced_prompt": enhanced_fallback,
        }


@router.get("/upscale-models")
def list_upscale_models(
    session: Session = Depends(get_session),
) -> list[dict[str, str]]:
    """Return list of all available upscale models for overrides dropdown."""
    results: list[dict[str, str]] = [
        {"value": "__none__", "label": "Kein Upscaling"},
        {"value": "fal", "label": "FAL.ai Standard"},
    ]
    # Enabled Topaz/FAL models
    topaz_models = crud.list_topaz_upscale_models(session, enabled_only=True)
    for m in topaz_models:
        results.append({
            "value": f"falm:{m.id}",
            "label": f"{m.name} (FAL)",
        })
    # Local models
    local_models = upscale_service.list_available_models()
    if local_models:
        for m in local_models:
            results.append({
                "value": f"local:{m}",
                "label": f"{m} (Lokal)",
            })
    else:
        results.append({
            "value": "local:RealESRGAN_x4plus",
            "label": "Real-ESRGAN x4plus (Lokal)",
        })
    return results

