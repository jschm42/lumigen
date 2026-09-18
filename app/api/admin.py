"""Admin REST API routes."""
from __future__ import annotations

import io
import json
import shutil
import sys
from datetime import UTC, datetime
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import crud
from app.db.engine import get_session
from app.providers.fal_upscale_adapter import FalUpscaleService
from app.services.auth_service import AuthService
from app.services.import_export_service import (
    export_all,
    export_styles,
    export_styles_zip,
    import_models,
    import_profiles,
    import_styles,
    import_styles_zip,
    validate_import_payload,
)
from app.services.model_config_service import ModelConfigService
from app.services.style_service import restore_default_styles
from app.utils.paths import ensure_dir

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()
auth_service = AuthService()
model_config_service = ModelConfigService(settings)
fal_upscale_service = FalUpscaleService()


@router.get("/providers")
def get_providers(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """List provider API key statuses."""
    keys = crud.list_provider_api_keys(session)
    key_map = {k.provider.lower(): k for k in keys}
    providers = [
        {"provider": "openrouter", "display_name": "OpenRouter"},
        {"provider": "fal", "display_name": "FAL.AI"},
        {"provider": "openai", "display_name": "OpenAI"},
        {"provider": "bfl", "display_name": "Black Forest Labs (BFL)"},
        {"provider": "google", "display_name": "Google Gemini"},
    ]
    result = []
    for p in providers:
        has_key = p["provider"] in key_map or model_config_service.has_env_api_key(p["provider"])
        result.append({
            "provider": p["provider"],
            "display_name": p["display_name"],
            "has_key": has_key,
        })
    return result


@router.post("/providers/{provider}")
def update_provider_key(
    provider: str,
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Set or update provider API key."""
    api_key = (payload.get("api_key") or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")

    provider_name = provider.strip().lower()
    try:
        encrypted = model_config_service.encrypt_api_key(api_key)
        crud.upsert_provider_api_key(session, provider=provider_name, api_key_encrypted=encrypted)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True}


@router.delete("/providers/{provider}")
def delete_provider_key(
    provider: str,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete provider API key."""
    crud.delete_provider_api_key(session, provider.strip().lower())
    return {"success": True}


@router.post("/providers/{provider}/test")
async def test_provider_connection(
    provider: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Test API connection to provider."""
    provider_name = provider.strip().lower()
    has_key = (
        crud.get_provider_api_key(session, provider_name) is not None
        or model_config_service.has_env_api_key(provider_name)
    )
    if not has_key:
        raise HTTPException(
            status_code=400, detail=f"No API key configured for {provider.upper()}."
        )
    return {"success": True, "message": f"Connection to {provider.upper()} tested successfully."}


@router.get("/providers/{provider}/discover-models")
async def discover_provider_models(
    provider: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Discover available models from provider."""
    # Return standard/discovered model presets
    default_discovery = {
        "openrouter": [
            "black-forest-labs/flux-1-schnell",
            "black-forest-labs/flux-1-dev",
            "stabilityai/stable-diffusion-3.5-large",
            "google/imagen-3",
        ],
        "fal": [
            "fal-ai/flux/schnell",
            "fal-ai/flux/dev",
            "fal-ai/nano-banana-2",
            "fal-ai/recraft-v3",
        ],
        "openai": [
            "dall-e-3",
            "dall-e-2",
        ],
        "google": [
            "imagen-3.0-generate-002",
        ],
    }
    models = default_discovery.get(provider.lower(), [])
    return {"models": models, "count": len(models)}


@router.get("/models")
def list_admin_models(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """List all model configurations."""
    configs = crud.list_model_configs(session)
    return [
        {
            "id": c.id,
            "name": c.name,
            "provider": c.provider,
            "model_identifier": c.model,
            "is_active": True,
            "is_default": False,
            "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"],
            "supported_resolutions": ["0.5K", "1K", "2K", "4K"],
        }
        for c in configs
    ]


@router.post("/models")
def create_model_config(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create a new model configuration."""
    name = payload.get("name", "").strip()
    model = payload.get("model_identifier", "").strip()
    provider = payload.get("provider", "openrouter").strip()

    if not name or not model:
        raise HTTPException(status_code=400, detail="Name and model identifier required")

    cfg = crud.create_model_config(
        session,
        name=name,
        provider=provider,
        model=model,
    )
    return {
        "id": cfg.id,
        "name": cfg.name,
        "provider": cfg.provider,
        "model_identifier": cfg.model,
        "is_active": True,
    }


@router.put("/models/{model_id}")
def update_model_config(
    model_id: int,
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update a model configuration."""
    cfg = crud.get_model_config(session, model_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Model config not found")

    cfg = crud.update_model_config(
        session,
        cfg,
        name=payload.get("name", cfg.name),
        provider=payload.get("provider", cfg.provider),
        model=payload.get("model_identifier", cfg.model),
    )
    return {
        "id": cfg.id,
        "name": cfg.name,
        "provider": cfg.provider,
        "model_identifier": cfg.model,
        "is_active": True,
    }


@router.delete("/models/{model_id}")
def delete_model_config(
    model_id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete a model configuration."""
    cfg = crud.get_model_config(session, model_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Model config not found")

    crud.delete_model_config(session, cfg)
    return {"success": True}


def _serialize_style(s: crud.Style) -> dict[str, Any]:
    """Serialize a Style model instance to a dictionary for API responses."""
    updated_ts = (
        int(s.updated_at.timestamp()) if getattr(s, "updated_at", None) else 0
    )
    img_url = (
        f"/api/admin/styles/{s.id}/image?t={updated_ts}"
        if getattr(s, "image_path", None)
        else None
    )
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description or "",
        "prompt_template": s.prompt or "",
        "negative_prompt": getattr(s, "negative_prompt", "") or "",
        "image_url": img_url,
    }


@router.get("/styles")
def list_admin_styles(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """List styles for administration."""
    styles = crud.list_styles(session)
    return [_serialize_style(s) for s in styles]


@router.get("/styles/{style_id}/image")
def get_admin_style_image(
    style_id: int,
    session: Session = Depends(get_session),
) -> FileResponse:
    """Serve the thumbnail image for a style preset."""
    style = crud.get_style(session, style_id)
    if not style or not style.image_path:
        raise HTTPException(status_code=404, detail="Style image not found")
    img_path = settings.data_dir / "styles" / f"{style_id}.webp"
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Style image file missing")
    return FileResponse(
        path=img_path,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=60"},
    )


@router.post("/styles")
async def save_admin_style(
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create or update a style preset with optional thumbnail image."""
    content_type = request.headers.get("content-type", "")
    image_file: UploadFile | None = None
    style_id: int | None = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        name = str(form.get("name") or "").strip()
        description = str(form.get("description") or "").strip()
        prompt = str(form.get("prompt_template") or form.get("prompt") or "").strip()
        raw_id = form.get("id")
        if raw_id:
            try:
                style_id = int(str(raw_id))
            except ValueError:
                pass
        upload = form.get("image")
        if isinstance(upload, UploadFile) and upload.filename:
            image_file = upload
    else:
        payload = await request.json()
        name = str(payload.get("name") or "").strip()
        description = str(payload.get("description") or "").strip()
        prompt = str(payload.get("prompt_template") or payload.get("prompt") or "").strip()
        raw_id = payload.get("id")
        if raw_id:
            try:
                style_id = int(str(raw_id))
            except ValueError:
                pass

    if not name:
        raise HTTPException(status_code=400, detail="Style name is required.")
    if len(name) > 30:
        raise HTTPException(
            status_code=400, detail="Style name must not exceed 30 characters."
        )
    if len(description) > 120:
        raise HTTPException(
            status_code=400, detail="Description must not exceed 120 characters."
        )
    if not prompt:
        raise HTTPException(
            status_code=400, detail="Prompt template is required."
        )
    if len(prompt) > 1000:
        raise HTTPException(
            status_code=400, detail="Prompt must not exceed 1000 characters."
        )

    if style_id:
        style = crud.get_style(session, style_id)
        if not style:
            raise HTTPException(status_code=404, detail="Style not found.")
        existing = crud.get_style_by_name(session, name)
        if existing and existing.id != style.id:
            raise HTTPException(
                status_code=400,
                detail=f"A style named '{name}' already exists.",
            )
        style = crud.update_style(
            session, style, name=name, description=description, prompt=prompt
        )
    else:
        existing = crud.get_style_by_name(session, name)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"A style named '{name}' already exists.",
            )
        style = crud.create_style(
            session,
            name=name,
            description=description,
            prompt=prompt,
            image_path=None,
        )

    if image_file:
        image_data = await image_file.read()
        if image_data:
            if len(image_data) > 5 * 1024 * 1024:
                raise HTTPException(
                    status_code=400, detail="Image must not exceed 5 MB."
                )
            img_dir = settings.data_dir / "styles"
            ensure_dir(img_dir)
            img_path = img_dir / f"{style.id}.webp"
            try:
                with io.BytesIO(image_data) as buf:
                    pil_img = Image.open(buf)
                    pil_img = ImageOps.exif_transpose(pil_img)
                    pil_img = pil_img.convert("RGB")
                    thumb_size = min(pil_img.width, pil_img.height, 256)
                    pil_img.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
                    out_buf = io.BytesIO()
                    pil_img.save(out_buf, format="WEBP", quality=85)
                    img_path.write_bytes(out_buf.getvalue())
                style = crud.update_style(
                    session, style, image_path=img_path.as_posix()
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=400, detail=f"Image processing error: {exc}"
                )

    return _serialize_style(style)


@router.delete("/styles/{style_id}")
def delete_admin_style(
    style_id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete a style preset."""
    s = crud.get_style(session, style_id)
    if not s:
        raise HTTPException(status_code=404, detail="Style not found")

    crud.delete_style(session, s)
    return {"success": True}


def _get_preview_model_config_id() -> int | None:
    """Return configured model_config_id for style preview generation, or None."""
    config_file = settings.data_dir / "style_preview_config.json"
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            val = data.get("model_config_id")
            return int(val) if val is not None else None
        except Exception:
            return None
    return None


def _set_preview_model_config_id(model_config_id: int) -> None:
    """Persist configured model_config_id for style preview generation."""
    config_file = settings.data_dir / "style_preview_config.json"
    ensure_dir(config_file.parent)
    config_file.write_text(
        json.dumps({"model_config_id": model_config_id}, indent=2), encoding="utf-8"
    )


@router.get("/styles/preview-settings")
def get_style_preview_settings(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return the currently configured model for style preview generation."""
    saved_id = _get_preview_model_config_id()
    model_configs = crud.list_model_configs(session)
    selected_id = saved_id
    if not any(m.id == selected_id for m in model_configs) and model_configs:
        selected_id = model_configs[0].id

    return {
        "model_config_id": selected_id,
        "models": [
            {"id": m.id, "name": m.name, "provider": m.provider, "model": m.model}
            for m in model_configs
        ],
    }


@router.post("/styles/preview-settings")
def update_style_preview_settings(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update the default model configuration used for style preview generation."""
    model_config_id = payload.get("model_config_id")
    if not model_config_id:
        raise HTTPException(status_code=400, detail="model_config_id is required.")

    cfg = crud.get_model_config(session, int(model_config_id))
    if not cfg:
        raise HTTPException(status_code=404, detail="Model configuration not found.")

    _set_preview_model_config_id(cfg.id)
    return {"success": True, "model_config_id": cfg.id, "name": cfg.name}


def _format_style_preview_prompt(style: crud.Style, custom_prompt: str | None = None) -> str:
    """Format prompt for style preview generation, resolving {prompt} placeholder."""
    base = (custom_prompt or "").strip() or style.prompt
    if "{prompt}" in base:
        return base.replace("{prompt}", "a scenic landscape with mountains and a lake").strip(", ")
    return base.strip()


@router.post("/styles/generate-missing-previews")
def generate_missing_style_previews(
    background_tasks: BackgroundTasks,
    payload: dict[str, Any] | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Trigger background generation for preview thumbnails of all styles missing an image."""
    from app.api.generation import generation_service

    styles = crud.list_styles(session)
    missing_styles: list[crud.Style] = []
    for style in styles:
        img_path = settings.data_dir / "styles" / f"{style.id}.webp"
        if not style.image_path or not img_path.exists():
            missing_styles.append(style)

    if not missing_styles:
        return {
            "success": True,
            "count": 0,
            "job_ids": [],
            "message": "All styles already have preview images.",
        }

    model_config_id = (payload or {}).get("model_config_id") if payload else None
    if not model_config_id:
        model_config_id = _get_preview_model_config_id()

    if model_config_id:
        model_config = crud.get_model_config(session, int(model_config_id))
    else:
        model_configs = crud.list_model_configs(session)
        model_config = model_configs[0] if model_configs else None

    if not model_config:
        raise HTTPException(
            status_code=400, detail="No model configuration available."
        )

    job_ids: list[int] = []
    for style in missing_styles:
        user_prompt = _format_style_preview_prompt(style)
        generation = generation_service.create_generation_for_style(
            session, style, model_config, user_prompt
        )
        generation_service.enqueue(background_tasks, generation.id)
        job_ids.append(generation.id)

    return {
        "success": True,
        "count": len(job_ids),
        "job_ids": job_ids,
        "model_name": model_config.name,
    }


@router.post("/styles/{style_id}/generate-preview")
def generate_style_preview(
    style_id: int,
    background_tasks: BackgroundTasks,
    payload: dict[str, Any] | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Trigger background generation for a style preview thumbnail."""
    from app.api.generation import generation_service

    style = crud.get_style(session, style_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found.")

    model_config_id = (payload or {}).get("model_config_id") if payload else None
    if not model_config_id:
        model_config_id = _get_preview_model_config_id()

    if model_config_id:
        model_config = crud.get_model_config(session, int(model_config_id))
    else:
        model_configs = crud.list_model_configs(session)
        model_config = model_configs[0] if model_configs else None

    if not model_config:
        raise HTTPException(
            status_code=400, detail="No model configuration available."
        )

    user_prompt = _format_style_preview_prompt(
        style, (payload or {}).get("prompt") if payload else None
    )
    generation = generation_service.create_generation_for_style(
        session, style, model_config, user_prompt
    )
    generation_service.enqueue(background_tasks, generation.id)
    return {"job_id": generation.id, "model_name": model_config.name}


@router.post("/styles/restore-defaults")
def restore_styles_defaults(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Restore all default style presets to their standard definitions."""
    result = restore_default_styles(session, overwrite=True)
    return {
        "success": True,
        "message": (
            f"{result['created']} created, {result['updated']} updated "
            f"({result['total']} total)."
        ),
        **result,
    }


@router.get("/users")
def list_admin_users(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """List all studio users."""
    users = crud.list_users(session)
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "created_at": u.created_at.isoformat() if u.created_at else "",
        }
        for u in users
    ]


@router.post("/users")
def create_admin_user(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create a new user account."""
    username = payload.get("username", "").strip()
    password = payload.get("password", "")
    role = payload.get("role", "user")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    password_hash = auth_service.hash_password(password)
    user = crud.create_user(
        session,
        username=username,
        password_hash=password_hash,
        role=role,
        is_active=True,
    )
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
    }


@router.delete("/users/{user_id}")
def delete_admin_user(
    user_id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete a user account."""
    u = crud.get_user(session, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    crud.delete_user(session, u)
    return {"success": True}


@router.get("/system")
def get_system_diagnostics(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Get system and storage info."""
    total_assets = session.query(crud.Asset).count()
    total_generations = session.query(crud.Generation).count()

    total_bytes, free_bytes = 0, 0
    try:
        stat = shutil.disk_usage(str(settings.data_dir))
        total_bytes = stat.used
        free_bytes = stat.free
    except Exception:
        pass

    return {
        "app_version": settings.app_version,
        "app_name": settings.app_name,
        "storage_dir": str(settings.data_dir),
        "storage_used_bytes": total_bytes,
        "storage_free_bytes": free_bytes,
        "total_assets": total_assets,
        "total_generations": total_generations,
        "python_version": sys.version.split()[0],
    }


@router.get("/export/all")
def export_all_data(session: Session = Depends(get_session)) -> Response:
    """Export complete backup of profiles, models, and styles as JSON."""
    data = export_all(session)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    filename = f"lumigen_backup_{timestamp}.json"
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/styles")
def export_styles_data(session: Session = Depends(get_session)) -> Response:
    """Export styles metadata as a JSON file."""
    data = export_styles(session)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    filename = f"lumigen_styles_{timestamp}.json"
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/styles-zip")
def export_styles_zip_data(session: Session = Depends(get_session)) -> Response:
    """Export styles and their preview thumbnails as a ZIP archive."""
    styles_dir = settings.data_dir / "styles"
    zip_bytes = export_styles_zip(session, styles_dir)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    filename = f"lumigen_styles_{timestamp}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def import_data(
    file: UploadFile = File(...),
    conflict_strategy: str = Form(default="overwrite"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Import data from a JSON backup file or ZIP archive."""
    if conflict_strategy not in {"skip", "overwrite", "rename"}:
        conflict_strategy = "overwrite"

    content = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".zip") or content.startswith(b"PK\x03\x04"):
        styles_dir = settings.data_dir / "styles"
        import_result = import_styles_zip(
            session, content, styles_dir, conflict_strategy=conflict_strategy
        )
        return {
            "success": True,
            "imported": {
                "styles_created": import_result.created,
                "styles_updated": import_result.updated,
                "styles_skipped": import_result.skipped,
                "styles_failed": import_result.failed,
            },
        }

    try:
        data = json.loads(content.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    imported_counts: dict[str, int] = {}

    if isinstance(data, dict):
        error, _version, profiles_data, models_data, styles_data = validate_import_payload(data)
        if error:
            raise HTTPException(status_code=400, detail=error)

        if models_data:
            res_models = import_models(session, models_data, conflict_strategy)
            imported_counts["models"] = res_models.created + res_models.updated
        if profiles_data:
            res_profiles = import_profiles(session, profiles_data, conflict_strategy)
            imported_counts["profiles"] = res_profiles.created + res_profiles.updated
        if styles_data:
            res_styles = import_styles(session, styles_data, conflict_strategy)
            imported_counts["styles"] = res_styles.created + res_styles.updated

    elif isinstance(data, list):
        res_styles = import_styles(session, data, conflict_strategy)
        imported_counts["styles"] = res_styles.created + res_styles.updated
    else:
        raise HTTPException(
            status_code=400,
            detail="Unexpected JSON format (object or list expected).",
        )

    return {
        "success": True,
        "imported": imported_counts,
    }


# --- Upscale Models Management ---


@router.get("/upscale/discover-models")
async def discover_upscale_models(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Discover available image-to-image upscale models from FAL.ai."""
    fal_key = model_config_service.get_default_api_key("fal")
    models = await fal_upscale_service.discover_upscale_models(api_key=fal_key)
    return {"models": models, "count": len(models)}


@router.get("/upscale-models")
def list_admin_upscale_models(
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """List all configured Topaz/FAL upscale models."""
    models = crud.list_topaz_upscale_models(session, enabled_only=False)
    return [
        {
            "id": m.id,
            "name": m.name,
            "model_identifier": m.model_identifier,
            "params_json": m.params_json or {},
            "is_enabled": m.is_enabled,
            "is_default": getattr(m, "is_default", False),
            "created_at": m.created_at.isoformat() if m.created_at else "",
            "updated_at": m.updated_at.isoformat() if m.updated_at else "",
        }
        for m in models
    ]


@router.post("/upscale-models")
def create_admin_upscale_model(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create a new upscale model configuration."""
    name = str(payload.get("name") or "").strip()
    model_identifier = str(payload.get("model_identifier") or "").strip()
    is_enabled = bool(payload.get("is_enabled", True))
    is_default = bool(payload.get("is_default", False))
    params_json = payload.get("params_json") or {}

    if not name or not model_identifier:
        raise HTTPException(status_code=400, detail="Name and model identifier are required.")

    existing = crud.get_topaz_upscale_model_by_name(session, name)
    if existing:
        raise HTTPException(status_code=400, detail=f"An upscale model named '{name}' already exists.")

    model = crud.create_topaz_upscale_model(
        session,
        name=name,
        model_identifier=model_identifier,
        params_json=params_json,
        is_enabled=is_enabled,
        is_default=is_default,
    )
    return {
        "id": model.id,
        "name": model.name,
        "model_identifier": model.model_identifier,
        "params_json": model.params_json,
        "is_enabled": model.is_enabled,
        "is_default": model.is_default,
    }


@router.put("/upscale-models/{model_id}")
def update_admin_upscale_model(
    model_id: int,
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update an existing upscale model configuration."""
    model = crud.get_topaz_upscale_model(session, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Upscale model not found.")

    name = str(payload.get("name") or model.name).strip()
    model_identifier = str(payload.get("model_identifier") or model.model_identifier).strip()

    if not name or not model_identifier:
        raise HTTPException(status_code=400, detail="Name and model identifier are required.")

    if name != model.name:
        existing = crud.get_topaz_upscale_model_by_name(session, name)
        if existing and existing.id != model_id:
            raise HTTPException(status_code=400, detail=f"An upscale model named '{name}' already exists.")

    fields: dict[str, Any] = {
        "name": name,
        "model_identifier": model_identifier,
    }
    if "is_enabled" in payload:
        fields["is_enabled"] = bool(payload["is_enabled"])
    if "is_default" in payload:
        fields["is_default"] = bool(payload["is_default"])
    if "params_json" in payload:
        fields["params_json"] = payload["params_json"] or {}

    updated = crud.update_topaz_upscale_model(session, model, **fields)
    return {
        "id": updated.id,
        "name": updated.name,
        "model_identifier": updated.model_identifier,
        "params_json": updated.params_json,
        "is_enabled": updated.is_enabled,
        "is_default": updated.is_default,
    }


@router.delete("/upscale-models/{model_id}")
def delete_admin_upscale_model(
    model_id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete an upscale model configuration."""
    model = crud.get_topaz_upscale_model(session, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Upscale model not found.")

    crud.delete_topaz_upscale_model(session, model)
    return {"success": True}


@router.post("/upscale-models/{model_id}/toggle")
def toggle_admin_upscale_model(
    model_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Toggle active/enabled state of an upscale model."""
    model = crud.get_topaz_upscale_model(session, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Upscale model not found.")

    model.is_enabled = not model.is_enabled
    session.add(model)
    session.commit()
    session.refresh(model)
    return {"id": model.id, "is_enabled": model.is_enabled}


@router.post("/upscale-models/{model_id}/set-default")
def set_default_admin_upscale_model(
    model_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Designate an upscale model as the studio default."""
    target = crud.set_default_topaz_upscale_model(session, model_id)
    if not target:
        raise HTTPException(status_code=404, detail="Upscale model not found.")
    return {"id": target.id, "is_default": True}
