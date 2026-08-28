"""Assets & Gallery REST API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import crud
from app.db.engine import get_session
from app.services.storage_service import StorageService

router = APIRouter(prefix="/assets", tags=["assets"])
settings = get_settings()
storage_service = StorageService(max_slug_length=settings.max_slug_length)


@router.get("")
def list_assets(
    q: str = Query(default=""),
    profile_name: str = Query(default=""),
    provider: str = Query(default=""),
    min_rating: int | None = Query(default=None),
    unrated: bool = Query(default=False),
    time_preset: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    category_ids: str = Query(default=""),
    artbook_token: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=40, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Filter and paginate assets for the gallery view."""
    parsed_cat_ids = []
    if category_ids:
        try:
            parsed_cat_ids = [int(x.strip()) for x in category_ids.split(",") if x.strip()]
        except ValueError:
            parsed_cat_ids = []

    assets, total = crud.list_assets_filtered(
        session,
        profile_name=profile_name or None,
        provider=provider or None,
        search_query=q or None,
        min_rating=min_rating,
        unrated_only=unrated,
        category_ids=parsed_cat_ids or None,
        time_preset=time_preset or None,
        date_from=date_from or None,
        date_to=date_to or None,
        artbook_token=artbook_token or None,
        offset=(page - 1) * page_size,
        limit=page_size,
    )

    result = []
    for a in assets:
        result.append({
            "id": a.id,
            "slug": a.slug,
            "prompt": a.prompt,
            "negative_prompt": a.negative_prompt,
            "seed": a.seed,
            "aspect_ratio": a.aspect_ratio,
            "resolution": a.resolution,
            "provider": a.provider,
            "model": a.model,
            "generation_id": a.generation_id,
            "created_at": a.created_at.isoformat() if a.created_at else "",
            "is_favorite": getattr(a, "is_favorite", False),
            "rating": getattr(a, "rating", 0) or 0,
            "thumbnail_url": f"/assets/{a.id}/thumb",
            "image_url": f"/assets/{a.id}/file",
            "download_url": f"/assets/{a.id}/download",
            "category_ids": [c.id for c in a.categories] if hasattr(a, "categories") else [],
        })

    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "assets": result,
        "total": total,
        "page": page,
        "total_pages": total_pages,
    }


@router.get("/{asset_id}")
def get_asset(
    asset_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get single asset metadata and properties."""
    asset = crud.get_asset(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    sidecar_data = asset.meta_json or {}

    return {
        "id": asset.id,
        "slug": asset.slug,
        "prompt": asset.prompt,
        "negative_prompt": asset.negative_prompt,
        "seed": asset.seed,
        "aspect_ratio": asset.aspect_ratio,
        "resolution": asset.resolution,
        "provider": asset.provider,
        "model": asset.model,
        "generation_id": asset.generation_id,
        "created_at": asset.created_at.isoformat() if asset.created_at else "",
        "is_favorite": getattr(asset, "is_favorite", False),
        "rating": getattr(asset, "rating", 0) or 0,
        "thumbnail_url": f"/assets/{asset.id}/thumb",
        "image_url": f"/assets/{asset.id}/file",
        "download_url": f"/assets/{asset.id}/download",
        "metadata": sidecar_data,
        "category_ids": [c.id for c in asset.categories] if hasattr(asset, "categories") else [],
    }


@router.post("/{asset_id}/rate")
def rate_asset(
    asset_id: int,
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update asset star rating (1-5)."""
    rating = int(payload.get("rating", 0))
    rating = max(0, min(5, rating))
    asset = crud.get_asset(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    setattr(asset, "rating", rating)
    session.commit()
    return {"success": True, "rating": rating}


@router.post("/{asset_id}/favorite")
def toggle_favorite(
    asset_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Toggle asset favorite status."""
    asset = crud.get_asset(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    current = getattr(asset, "is_favorite", False)
    setattr(asset, "is_favorite", not current)
    session.commit()
    return {"success": True, "is_favorite": not current}


@router.delete("/{asset_id}")
def delete_asset(
    asset_id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete a single asset."""
    asset = crud.get_asset(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    crud.delete_asset(session, asset)
    return {"success": True}


@router.post("/bulk-delete")
def bulk_delete_assets(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Bulk delete multiple assets by IDs."""
    asset_ids = payload.get("asset_ids", [])
    if not asset_ids:
        return {"success": True, "deleted_count": 0}

    deleted_count = 0
    for aid in asset_ids:
        asset = crud.get_asset(session, aid)
        if asset:
            crud.delete_asset(session, asset)
            deleted_count += 1

    return {"success": True, "deleted_count": deleted_count}
