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

    if content_type.startswith("application/json"):
        payload = await request.json()
        prompt = payload.get("prompt", "").strip()
        negative_prompt = payload.get("negative_prompt")
        profile_id = payload.get("profile_id")
        model_config_id = payload.get("model_config_id")
        aspect_ratio = payload.get("aspect_ratio", "1:1")
        resolution = payload.get("resolution", "1K")
        seed = payload.get("seed")
        conversation = payload.get("conversation", "")
        style_id = payload.get("style_id")
    else:
        form = await request.form()
        prompt = str(form.get("prompt", "")).strip()
        negative_prompt = str(form.get("negative_prompt")) if form.get("negative_prompt") else None
        profile_id = int(form.get("profile_id")) if form.get("profile_id") else None
        model_config_id = int(form.get("model_config_id")) if form.get("model_config_id") else None
        aspect_ratio = str(form.get("aspect_ratio", "1:1"))
        resolution = str(form.get("resolution", "1K"))
        seed = str(form.get("seed")) if form.get("seed") else None
        conversation = str(form.get("conversation", ""))
        style_id = str(form.get("style_id")) if form.get("style_id") else None

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
        # Fallback profile
        profile = crud.create_profile(
            session,
            name="Default",
            aspect_ratio="1:1",
            resolution="1K",
        )

    overrides: dict[str, Any] = {}
    conversation_value = (conversation or "").strip()
    if not conversation_value:
        from app.main import build_chat_session_token
        conversation_value = build_chat_session_token()
    overrides["chat_session_id"] = conversation_value

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

    if aspect_ratio:
        overrides["aspect_ratio"] = aspect_ratio
    if resolution:
        overrides["resolution"] = resolution
    if seed is not None and seed != "":
        try:
            overrides["seed"] = int(seed)
        except ValueError:
            pass

    if negative_prompt:
        overrides["negative_prompt"] = negative_prompt

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
    }


@router.get("/jobs/{generation_id}/status")
def get_job_status(
    generation_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get the current status, progress, and assets for a generation job."""
    gen = crud.get_generation(session, generation_id)
    if not gen:
        raise HTTPException(status_code=404, detail="Generation job not found")

    assets_list = []
    for a in gen.assets:
        assets_list.append({
            "id": a.id,
            "slug": a.slug,
            "prompt": a.prompt,
            "negative_prompt": a.negative_prompt,
            "seed": a.seed,
            "aspect_ratio": a.aspect_ratio,
            "resolution": a.resolution,
            "provider": a.provider,
            "model": a.model,
            "created_at": a.created_at.isoformat() if a.created_at else "",
            "is_favorite": getattr(a, "is_favorite", False),
            "rating": getattr(a, "rating", 0) or 0,
            "thumbnail_url": f"/assets/{a.id}/thumb",
            "image_url": f"/assets/{a.id}/file",
            "download_url": f"/assets/{a.id}/download",
        })

    return {
        "id": gen.id,
        "status": gen.status,
        "progress": gen.progress,
        "error_message": gen.error_message,
        "prompt": gen.prompt,
        "negative_prompt": gen.negative_prompt,
        "session_token": gen.chat_session_id,
        "created_at": gen.created_at.isoformat() if gen.created_at else "",
        "completed_at": gen.completed_at.isoformat() if gen.completed_at else None,
        "model_name": gen.model,
        "provider": gen.provider,
        "aspect_ratio": gen.aspect_ratio,
        "resolution": gen.resolution,
        "seed": gen.seed,
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
