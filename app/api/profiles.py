"""Profiles REST API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import crud
from app.db.engine import get_session
from app.db.models import Profile

router = APIRouter(prefix="/profiles", tags=["profiles"])
settings = get_settings()


def serialize_profile(p: Profile) -> dict[str, Any]:
    """Serialize Profile instance to clean dictionary for frontend consumption."""
    params = p.params_json or {}
    return {
        "id": p.id,
        "name": p.name,
        "description": params.get("description", ""),
        "system_prompt": p.base_prompt or "",
        "negative_prompt": p.negative_prompt or "",
        "default_aspect_ratio": p.aspect_ratio or "1:1",
        "default_resolution": params.get("resolution", "1K"),
        "default_model_config_id": p.model_config_id,
        "upscale_provider": p.upscale_provider,
        "upscale_model": p.upscale_model,
        "upscale_topaz_model_id": p.upscale_topaz_model_id,
        "category_ids": [c.id for c in p.categories] if hasattr(p, "categories") and p.categories else [],
        "created_at": p.created_at.isoformat() if p.created_at else "",
    }


@router.get("")
def list_profiles(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """List all profiles."""
    profiles = crud.list_profiles(session)
    return [serialize_profile(p) for p in profiles]


@router.get("/{profile_id}")
def get_profile(
    profile_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get single profile details."""
    p = crud.get_profile(session, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return serialize_profile(p)


def resolve_default_storage_template_id(session: Session) -> int:
    """Resolve or create default storage template ID."""
    storage_templates = crud.list_storage_templates(session)
    if storage_templates:
        default_template = next((item for item in storage_templates if item.name == "default"), None)
        return (default_template or storage_templates[0]).id
    template = crud.ensure_default_storage_template(
        session, settings.default_base_dir, settings.default_storage_template
    )
    return template.id


@router.post("")
def create_profile(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create a new profile."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    model_cfg_id = payload.get("default_model_config_id")
    provider = None
    model = None
    parsed_model_cfg_id = None

    if model_cfg_id is not None and model_cfg_id != "":
        try:
            parsed_model_cfg_id = int(model_cfg_id)
            cfg = crud.get_model_config(session, parsed_model_cfg_id)
            if cfg:
                provider = cfg.provider
                model = cfg.model
        except (ValueError, TypeError):
            parsed_model_cfg_id = None

    storage_template_id = resolve_default_storage_template_id(session)

    params = {
        "description": payload.get("description", ""),
        "resolution": payload.get("default_resolution", "1K"),
    }

    p = crud.create_profile(
        session,
        name=name,
        provider=provider,
        model=model,
        model_config_id=parsed_model_cfg_id,
        base_prompt=(payload.get("system_prompt") or "").strip() or None,
        negative_prompt=(payload.get("negative_prompt") or "").strip() or None,
        aspect_ratio=payload.get("default_aspect_ratio", "1:1"),
        params_json=params,
        storage_template_id=storage_template_id,
    )
    return serialize_profile(p)


@router.put("/{profile_id}")
def update_profile(
    profile_id: int,
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update an existing profile."""
    p = crud.get_profile(session, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    model_cfg_id = payload.get("default_model_config_id")
    provider = p.provider
    model = p.model
    parsed_model_cfg_id = None

    if model_cfg_id is not None and model_cfg_id != "":
        try:
            parsed_model_cfg_id = int(model_cfg_id)
            cfg = crud.get_model_config(session, parsed_model_cfg_id)
            if cfg:
                provider = cfg.provider
                model = cfg.model
            else:
                provider = None
                model = None
        except (ValueError, TypeError):
            parsed_model_cfg_id = None
    elif model_cfg_id is None:
        parsed_model_cfg_id = None
        provider = None
        model = None

    params = p.params_json or {}
    if "description" in payload:
        params["description"] = payload.get("description", "")
    if "default_resolution" in payload:
        params["resolution"] = payload.get("default_resolution", "1K")

    base_prompt_val = payload.get("system_prompt", p.base_prompt)
    if isinstance(base_prompt_val, str):
        base_prompt_val = base_prompt_val.strip() or None

    negative_prompt_val = payload.get("negative_prompt", p.negative_prompt)
    if isinstance(negative_prompt_val, str):
        negative_prompt_val = negative_prompt_val.strip() or None

    p = crud.update_profile(
        session,
        p,
        name=payload.get("name", p.name),
        provider=provider,
        model=model,
        model_config_id=parsed_model_cfg_id,
        base_prompt=base_prompt_val,
        negative_prompt=negative_prompt_val,
        aspect_ratio=payload.get("default_aspect_ratio", p.aspect_ratio),
        params_json=params,
    )
    return serialize_profile(p)


@router.delete("/{profile_id}")
def delete_profile(
    profile_id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete a profile."""
    p = crud.get_profile(session, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    crud.delete_profile(session, p)
    return {"success": True}
