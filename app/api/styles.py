"""Styles REST API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import crud
from app.db.engine import get_session

router = APIRouter(prefix="/styles", tags=["styles"])


@router.get("")
def list_styles(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """Return all style presets."""
    styles = crud.list_styles(session)
    result = []
    for s in styles:
        result.append({
            "id": s.id,
            "name": s.name,
            "description": s.description or "",
            "prompt_template": s.prompt or "",
            "negative_prompt": getattr(s, "negative_prompt", "") or "",
            "image_url": f"/admin/styles/{s.id}/image" if getattr(s, "image_path", None) else None,
            "is_custom": True,
            "category": "General",
        })
    return result
