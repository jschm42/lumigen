"""Models REST API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import crud
from app.db.engine import get_session

router = APIRouter(prefix="/models", tags=["models"])

# Aspect ratios / resolutions offered by every provider in the studio UI.
_ALL_ASPECT_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"]
_ALL_RESOLUTIONS = ["0.5K", "1K", "2K", "4K"]
# Video models only accept the resolutions their provider supports.
_VIDEO_RESOLUTIONS = ["720p", "1080p"]


@router.get("/active")
def list_active_models(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """Return all active ModelConfigs for generation, annotated with their media type."""
    from app.api.generation import provider_registry

    configs = crud.list_model_configs(session)
    result = []
    for cfg in configs:
        media_type = provider_registry.media_type_for(cfg.provider, cfg.model)
        is_video = media_type == "video"
        result.append({
            "id": cfg.id,
            "name": cfg.name,
            "provider": cfg.provider,
            "model_identifier": cfg.model,
            "media_type": media_type,
            "capabilities": ["video"] if is_video else ["image"],
            "is_active": True,
            "is_default": False,
            "supported_aspect_ratios": list(_ALL_ASPECT_RATIOS),
            "supported_resolutions": list(_VIDEO_RESOLUTIONS if is_video else _ALL_RESOLUTIONS),
        })
    return result
