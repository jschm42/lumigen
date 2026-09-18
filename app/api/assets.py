"""Assets & Gallery REST API routes."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
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

    setattr(asset, "rating", rating if rating > 0 else None)
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
    """Delete a single asset and its associated files."""
    from app.api.generation import generation_service

    if not generation_service.delete_asset(session, asset_id):
        # Fallback to direct DB deletion if asset row exists without generation
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
    """Bulk delete multiple assets by IDs and clean up their files."""
    from app.api.generation import generation_service

    asset_ids = payload.get("asset_ids", [])
    if not asset_ids:
        return {"success": True, "deleted_count": 0}

    deleted_count = 0
    for raw_id in asset_ids:
        try:
            aid = int(raw_id)
        except (ValueError, TypeError):
            continue

        if generation_service.delete_asset(session, aid):
            deleted_count += 1
        else:
            # Fallback to direct DB deletion if asset row exists without generation
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
    """Bulk assign categories to multiple assets with replace or append mode."""
    asset_ids = payload.get("asset_ids", [])
    category_ids = payload.get("category_ids", [])
    mode = str(payload.get("mode") or "replace").strip().lower()
    if not asset_ids:
        return {"success": True}

    cats = crud.list_categories_by_ids(session, category_ids) if category_ids else []
    for aid in asset_ids:
        asset = crud.get_asset(session, aid)
        if asset:
            if mode == "append":
                existing_ids = {c.id for c in asset.categories}
                for c in cats:
                    if c.id not in existing_ids:
                        asset.categories.append(c)
            else:
                asset.categories = list(cats)
    session.commit()
    return {"success": True}


@router.post("/{asset_id}/upscale")
def upscale_asset(
    asset_id: int,
    background_tasks: BackgroundTasks,
    payload: dict[str, Any] | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Upscale an existing asset using the configured FAL upscale model."""
    from app.api.generation import generation_service, model_config_service
    from app.db.models import Generation

    asset = crud.get_asset(session, asset_id, with_generation=True)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")

    # 1. Check upscale model configuration
    req_model_id = None
    if payload:
        raw_id = payload.get("topaz_model_id") or payload.get("model_id")
        if raw_id is not None:
            try:
                req_model_id = int(raw_id)
            except (ValueError, TypeError):
                req_model_id = None

    topaz_config = None
    if req_model_id:
        topaz_config = crud.get_topaz_upscale_model(session, req_model_id)
    if not topaz_config:
        topaz_config = crud.get_default_topaz_upscale_model(session)

    if not topaz_config or not topaz_config.is_enabled:
        raise HTTPException(
            status_code=400,
            detail="No upscale model configured. Please configure a FAL upscale model in Admin -> Upscaling.",
        )

    # 2. Check FAL API key
    fal_key = model_config_service.get_default_api_key("fal")
    if not fal_key:
        raise HTTPException(
            status_code=400,
            detail="FAL.ai API key is not configured. Please add your FAL API key in Admin -> API Keys.",
        )

    # 3. Create an upscale Generation record
    orig_gen = asset.generation
    orig_req_snapshot = orig_gen.request_snapshot_json if orig_gen else {}
    profile_snapshot = orig_gen.profile_snapshot_json if orig_gen else {}
    storage_snapshot = orig_gen.storage_template_snapshot_json if orig_gen else {
        "template": settings.default_storage_template,
        "base_dir": settings.default_base_dir,
    }

    prompt_user = orig_gen.prompt_user if orig_gen else f"Upscale Asset #{asset.id}"
    prompt_final = orig_gen.prompt_final if orig_gen else prompt_user

    chat_session_id = orig_req_snapshot.get("chat_session_id") or orig_req_snapshot.get("conversation", "")
    req_snapshot = {
        **orig_req_snapshot,
        "chat_session_id": chat_session_id,
        "source_asset_id": asset.id,
        "is_upscale": True,
        "upscale_model": topaz_config.model_identifier,
        "upscale_topaz_model_id": topaz_config.id,
        "output_format": "png",
    }

    generation = Generation(
        profile_id=orig_gen.profile_id if orig_gen else None,
        profile_name=orig_gen.profile_name if orig_gen else "Upscale",
        prompt_user=prompt_user,
        prompt_final=prompt_final,
        provider="fal",
        model=topaz_config.model_identifier,
        status="queued",
        error=None,
        profile_snapshot_json=profile_snapshot,
        storage_template_snapshot_json=storage_snapshot,
        request_snapshot_json=req_snapshot,
    )
    crud.create_generation(session, generation)

    generation_service.enqueue_upscale(
        background_tasks,
        generation.id,
        source_asset_id=asset.id,
        upscale_model_id=topaz_config.id,
    )

    return {
        "job_id": generation.id,
        "status": generation.status,
    }

