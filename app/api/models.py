"""Models REST API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import crud
from app.db.engine import get_session

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/active")
def list_active_models(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """Return all active ModelConfigs for generation."""
    configs = crud.list_model_configs(session)
    result = []
    for cfg in configs:
        if cfg.is_active:
            result.append({
                "id": cfg.id,
                "name": cfg.name,
                "provider": cfg.provider,
                "model_identifier": cfg.model,
                "is_active": cfg.is_active,
                "is_default": getattr(cfg, "is_default", False),
                "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"],
                "supported_resolutions": ["0.5K", "1K", "2K", "4K"],
            })
    return result
