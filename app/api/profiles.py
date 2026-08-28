"""Profiles REST API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import crud
from app.db.engine import get_session

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("")
def list_profiles(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """List all profiles."""
    profiles = crud.list_profiles(session)
    result = []
    for p in profiles:
        result.append({
            "id": p.id,
            "name": p.name,
            "description": p.description or "",
            "system_prompt": getattr(p, "prompt_prefix", "") or "",
            "negative_prompt": p.negative_prompt or "",
            "default_aspect_ratio": p.aspect_ratio or "1:1",
            "default_resolution": getattr(p, "resolution", "1K"),
            "default_model_config_id": getattr(p, "model_config_id", None),
            "created_at": p.created_at.isoformat() if p.created_at else "",
        })
    return result


@router.get("/{profile_id}")
def get_profile(
    profile_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get single profile details."""
    p = crud.get_profile(session, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {
        "id": p.id,
        "name": p.name,
        "description": p.description or "",
        "system_prompt": getattr(p, "prompt_prefix", "") or "",
        "negative_prompt": p.negative_prompt or "",
        "default_aspect_ratio": p.aspect_ratio or "1:1",
        "default_resolution": getattr(p, "resolution", "1K"),
        "default_model_config_id": getattr(p, "model_config_id", None),
        "created_at": p.created_at.isoformat() if p.created_at else "",
    }


@router.post("")
def create_profile(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create a new profile."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    p = crud.create_profile(
        session,
        name=name,
        description=payload.get("description", ""),
        prompt_prefix=payload.get("system_prompt", ""),
        negative_prompt=payload.get("negative_prompt", ""),
        aspect_ratio=payload.get("default_aspect_ratio", "1:1"),
        resolution=payload.get("default_resolution", "1K"),
        model_config_id=payload.get("default_model_config_id"),
    )
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "system_prompt": getattr(p, "prompt_prefix", ""),
        "negative_prompt": p.negative_prompt,
        "default_aspect_ratio": p.aspect_ratio,
        "default_resolution": getattr(p, "resolution", "1K"),
        "default_model_config_id": getattr(p, "model_config_id", None),
    }


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

    p = crud.update_profile(
        session,
        p,
        name=payload.get("name", p.name),
        description=payload.get("description", p.description),
        prompt_prefix=payload.get("system_prompt", getattr(p, "prompt_prefix", "")),
        negative_prompt=payload.get("negative_prompt", p.negative_prompt),
        aspect_ratio=payload.get("default_aspect_ratio", p.aspect_ratio),
        resolution=payload.get("default_resolution", getattr(p, "resolution", "1K")),
        model_config_id=payload.get("default_model_config_id", getattr(p, "model_config_id", None)),
    )
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "system_prompt": getattr(p, "prompt_prefix", ""),
        "negative_prompt": p.negative_prompt,
        "default_aspect_ratio": p.aspect_ratio,
        "default_resolution": getattr(p, "resolution", "1K"),
        "default_model_config_id": getattr(p, "model_config_id", None),
    }


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
