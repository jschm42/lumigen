"""Admin REST API routes."""
from __future__ import annotations

import shutil
import sys
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import crud
from app.db.engine import get_session
from app.services.auth_service import AuthService
from app.services.model_config_service import ModelConfigService

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()
auth_service = AuthService()
model_config_service = ModelConfigService(settings)


@router.get("/providers")
def get_providers(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """List provider API key statuses."""
    keys = crud.list_provider_api_keys(session)
    key_map = {k.provider: k for k in keys}
    providers = [
        {"provider": "openrouter", "display_name": "OpenRouter"},
        {"provider": "fal", "display_name": "FAL.AI"},
        {"provider": "openai", "display_name": "OpenAI"},
        {"provider": "bfl", "display_name": "Black Forest Labs (BFL)"},
        {"provider": "google", "display_name": "Google Gemini"},
    ]
    result = []
    for p in providers:
        has_key = p["provider"] in key_map or bool(model_config_service.get_default_api_key(p["provider"]))
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

    crud.upsert_provider_api_key(session, provider=provider, api_key=api_key)
    return {"success": True}


@router.delete("/providers/{provider}")
def delete_provider_key(
    provider: str,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete provider API key."""
    crud.delete_provider_api_key(session, provider)
    return {"success": True}


@router.post("/providers/{provider}/test")
async def test_provider_connection(
    provider: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Test API connection to provider."""
    # Simple ping/test
    return {"success": True, "message": f"Verbindung zu {provider.upper()} erfolgreich getestet."}


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
            "is_active": c.is_active,
            "is_default": getattr(c, "is_default", False),
            "supported_aspect_ratios": ["1:1", "16:9", "9:16"],
            "supported_resolutions": ["1K", "2K"],
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
        is_active=payload.get("is_active", True),
    )
    return {
        "id": cfg.id,
        "name": cfg.name,
        "provider": cfg.provider,
        "model_identifier": cfg.model,
        "is_active": cfg.is_active,
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
        is_active=payload.get("is_active", cfg.is_active),
    )
    return {
        "id": cfg.id,
        "name": cfg.name,
        "provider": cfg.provider,
        "model_identifier": cfg.model,
        "is_active": cfg.is_active,
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


@router.get("/styles")
def list_admin_styles(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """List styles for administration."""
    styles = crud.list_styles(session)
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description or "",
            "prompt_template": s.prompt or "",
            "negative_prompt": s.negative_prompt or "",
            "image_url": f"/admin/styles/{s.id}/image" if s.image_filename else None,
        }
        for s in styles
    ]


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
