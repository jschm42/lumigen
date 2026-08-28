"""Assets & Gallery REST API routes."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import crud
from app.db.engine import get_session
from app.db.models import Asset, Generation
from app.services.gallery_service import GalleryService
from app.services.storage_service import StorageService

router = APIRouter(prefix="/assets", tags=["assets"])
settings = get_settings()
storage_service = StorageService(max_slug_length=settings.max_slug_length)
gallery_service = GalleryService()


def serialize_asset(a: Asset, gen: Generation | None = None) -> dict[str, Any]:
    """Serialize an Asset model instance into a JSON-ready dictionary."""
    meta = a.meta_json or {}
    generation = gen or getattr(a, "generation", None)
    req_snapshot = (generation.request_snapshot_json or {}) if generation else {}

    prompt = meta.get("prompt") or (generation.prompt_user if generation else "")
    negative_prompt = meta.get("negative_prompt") or req_snapshot.get("negative_prompt", "")
    seed = meta.get("seed") if meta.get("seed") is not None else req_snapshot.get("seed")
    aspect_ratio = meta.get("aspect_ratio") or req_snapshot.get("aspect_ratio", "1:1")
    resolution = meta.get("resolution") or req_snapshot.get("resolution", "1K")
    provider = meta.get("provider") or (generation.provider if generation else "")
    model = meta.get("model") or (generation.model if generation else "")
    slug = meta.get("slug") or (Path(a.file_path).stem if a.file_path else f"asset-{a.id}")
    rating = a.rating or 0

    return {
        "id": a.id,
        "slug": slug,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": seed,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "provider": provider,
        "model": model,
        "generation_id": a.generation_id,
        "width": a.width,
        "height": a.height,
        "mime": a.mime,
        "rating": rating,
        "is_favorite": rating >= 4,
        "created_at": a.created_at.isoformat() if a.created_at else "",
        "thumbnail_url": f"/assets/{a.id}/thumb",
        "image_url": f"/assets/{a.id}/file",
        "download_url": f"/assets/{a.id}/download",
        "category_ids": [c.id for c in a.categories] if hasattr(a, "categories") and a.categories else [],
        "metadata": meta,
    }


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

    created_after: datetime | None = None
    created_before: datetime | None = None
    if time_preset:
        now = datetime.now()
        if time_preset == "today":
            created_after = datetime.combine(now.date(), datetime.min.time())
        elif time_preset == "yesterday":
            created_after = datetime.combine((now - timedelta(days=1)).date(), datetime.min.time())
            created_before = datetime.combine((now - timedelta(days=1)).date(), datetime.max.time())
        elif time_preset in ("last_7_days", "week"):
            created_after = now - timedelta(days=7)
        elif time_preset in ("last_30_days", "month"):
            created_after = now - timedelta(days=30)
        elif time_preset in ("last_year", "year"):
            created_after = now - timedelta(days=365)

    if date_from:
        try:
            d = date.fromisoformat(date_from)
            created_after = datetime.combine(d, datetime.min.time())
        except Exception:
            pass
    if date_to:
        try:
            d = date.fromisoformat(date_to)
            created_before = datetime.combine(d, datetime.max.time())
        except Exception:
            pass

    page_data = gallery_service.list_assets(
        session,
        page=page,
        page_size=page_size,
        profile_name=profile_name or None,
        provider=provider or None,
        prompt_query=q or None,
        category_ids=parsed_cat_ids or None,
        min_rating=min_rating if not unrated else None,
        unrated_only=unrated,
        created_after=created_after,
        created_before=created_before,
    )

    result = [serialize_asset(a) for a in page_data.items]
    return {
        "assets": result,
        "total": page_data.total,
        "page": page_data.page,
        "total_pages": page_data.pages,
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

    return serialize_asset(asset)


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


@router.put("/{asset_id}/categories")
def update_asset_categories(
    asset_id: int,
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update categories assigned to a single asset."""
    asset = crud.get_asset(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    category_ids = payload.get("category_ids", [])
    cats = crud.list_categories_by_ids(session, category_ids)
    asset.categories = list(cats)
    session.commit()
    return {
        "success": True,
        "categories": [{"id": c.id, "name": c.name} for c in asset.categories],
    }


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


@router.post("/bulk-categorize")
def bulk_categorize_assets(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Bulk assign categories to multiple assets."""
    asset_ids = payload.get("asset_ids", [])
    category_ids = payload.get("category_ids", [])
    if not asset_ids or not category_ids:
        return {"success": True}

    cats = crud.list_categories_by_ids(session, category_ids)
    for aid in asset_ids:
        asset = crud.get_asset(session, aid)
        if asset:
            asset.categories = list(cats)
    session.commit()
    return {"success": True}
