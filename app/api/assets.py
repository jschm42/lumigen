"""Assets & Gallery REST API routes."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

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


def _clean_up_stacks(session: Session, affected_stack_ids: set[str]) -> None:
    """Clean up stacks after removal/deletion: dissolves single-item stacks and reindexes orders."""
    session.flush()
    for sid in affected_stack_ids:
        if not sid:
            continue
        remaining = list(
            session.scalars(
                select(Asset)
                .where(Asset.stack_id == sid)
                .order_by(Asset.stack_order.asc(), Asset.created_at.desc())
            ).all()
        )
        if len(remaining) <= 1:
            for rem in remaining:
                rem.stack_id = None
                rem.stack_order = 0
        else:
            for idx, rem in enumerate(remaining):
                rem.stack_order = idx
    session.flush()


def serialize_asset(
    a: Asset,
    gen: Generation | None = None,
    *,
    include_stack_items: bool = True,
) -> dict[str, Any]:
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

    stack_id = getattr(a, "stack_id", None)
    stack_order = getattr(a, "stack_order", 0) or 0
    stack_items_raw = getattr(a, "_stack_items", None)
    stack_count = getattr(a, "_stack_count", None)
    if stack_count is None:
        stack_count = len(stack_items_raw) if stack_items_raw else (1 if not stack_id else 1)

    stack_items: list[dict[str, Any]] = []
    if include_stack_items and stack_id and stack_items_raw:
        stack_items = [
            serialize_asset(item, include_stack_items=False)
            for item in stack_items_raw
        ]

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
        "stack_id": stack_id,
        "stack_order": stack_order,
        "stack_count": stack_count,
        "stack_items": stack_items,
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
    collapse_stacks: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=40, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Filter and paginate assets for the gallery view."""
    category_ids_str = category_ids if isinstance(category_ids, str) else ""
    parsed_cat_ids = []
    if category_ids_str:
        try:
            parsed_cat_ids = [int(x.strip()) for x in category_ids_str.split(",") if x.strip()]
        except ValueError:
            parsed_cat_ids = []

    time_preset_val = time_preset if isinstance(time_preset, str) else ""
    date_from_val = date_from if isinstance(date_from, str) else ""
    date_to_val = date_to if isinstance(date_to, str) else ""
    collapse_val = collapse_stacks if isinstance(collapse_stacks, bool) else True
    page_val = page if isinstance(page, int) else 1
    page_size_val = page_size if isinstance(page_size, int) else 40
    q_val = q if isinstance(q, str) else ""
    profile_val = profile_name if isinstance(profile_name, str) else ""
    provider_val = provider if isinstance(provider, str) else ""
    min_rating_val = min_rating if isinstance(min_rating, int) else None
    unrated_val = unrated if isinstance(unrated, bool) else False

    created_after: datetime | None = None
    created_before: datetime | None = None
    if time_preset_val:
        now = datetime.now()
        if time_preset_val == "today":
            created_after = datetime.combine(now.date(), datetime.min.time())
        elif time_preset_val == "yesterday":
            created_after = datetime.combine((now - timedelta(days=1)).date(), datetime.min.time())
            created_before = datetime.combine((now - timedelta(days=1)).date(), datetime.max.time())
        elif time_preset_val in ("last_7_days", "week"):
            created_after = now - timedelta(days=7)
        elif time_preset_val in ("last_30_days", "month"):
            created_after = now - timedelta(days=30)
        elif time_preset_val in ("last_year", "year"):
            created_after = now - timedelta(days=365)

    if date_from_val:
        try:
            d = date.fromisoformat(date_from_val)
            created_after = datetime.combine(d, datetime.min.time())
        except Exception:
            pass
    if date_to_val:
        try:
            d = date.fromisoformat(date_to_val)
            created_before = datetime.combine(d, datetime.max.time())
        except Exception:
            pass

    page_data = gallery_service.list_assets(
        session,
        page=page_val,
        page_size=page_size_val,
        profile_name=profile_val or None,
        provider=provider_val or None,
        prompt_query=q_val or None,
        category_ids=parsed_cat_ids or None,
        min_rating=min_rating_val if not unrated_val else None,
        unrated_only=unrated_val,
        created_after=created_after,
        created_before=created_before,
        collapse_stacks=collapse_val,
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

    if asset.stack_id:
        sibling_stmt = (
            select(Asset)
            .where(Asset.stack_id == asset.stack_id)
            .options(selectinload(Asset.generation), selectinload(Asset.categories))
            .order_by(Asset.stack_order.asc(), Asset.created_at.desc())
        )
        siblings = list(session.scalars(sibling_stmt).all())
        setattr(asset, "_stack_items", siblings)
        setattr(asset, "_stack_count", len(siblings))

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

    asset = crud.get_asset(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    stack_id = asset.stack_id

    if not generation_service.delete_asset(session, asset_id):
        # Fallback to direct DB deletion if asset row exists without generation
        crud.delete_asset(session, asset)

    if stack_id:
        _clean_up_stacks(session, {stack_id})
        session.commit()

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
    affected_stacks: set[str] = set()
    for raw_id in asset_ids:
        try:
            aid = int(raw_id)
        except (ValueError, TypeError):
            continue

        asset = crud.get_asset(session, aid)
        if not asset:
            continue
        if asset.stack_id:
            affected_stacks.add(asset.stack_id)

        if generation_service.delete_asset(session, aid):
            deleted_count += 1
        else:
            # Fallback to direct DB deletion if asset row exists without generation
            crud.delete_asset(session, asset)
            deleted_count += 1

    if affected_stacks:
        _clean_up_stacks(session, affected_stacks)
        session.commit()

    return {"success": True, "deleted_count": deleted_count}


@router.post("/stack")
def stack_assets(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Group multiple assets into a photo stack."""
    asset_ids = payload.get("asset_ids", [])
    if not isinstance(asset_ids, list) or len(asset_ids) < 2:
        raise HTTPException(status_code=400, detail="At least two assets are required to create a stack.")

    int_ids: list[int] = []
    for aid in asset_ids:
        try:
            int_ids.append(int(aid))
        except (ValueError, TypeError):
            continue

    if len(int_ids) < 2:
        raise HTTPException(status_code=400, detail="Invalid asset IDs.")

    assets = list(session.scalars(select(Asset).where(Asset.id.in_(int_ids))).all())
    if len(assets) < 2:
        raise HTTPException(status_code=404, detail="Selected assets could not be found.")

    asset_map = {a.id: a for a in assets}
    ordered_assets = [asset_map[aid] for aid in int_ids if aid in asset_map]

    # Check if any selected asset is already in a stack
    existing_stack_id = next((a.stack_id for a in ordered_assets if a.stack_id), None)
    target_stack_id = existing_stack_id or f"stk_{uuid.uuid4().hex[:12]}"

    existing_siblings: list[Asset] = []
    if existing_stack_id:
        existing_siblings = list(
            session.scalars(
                select(Asset)
                .where(Asset.stack_id == existing_stack_id)
                .order_by(Asset.stack_order.asc(), Asset.created_at.desc())
            ).all()
        )

    # Combine ordered selection and any other existing siblings
    combined = list(ordered_assets)
    for ex in existing_siblings:
        if ex not in combined:
            combined.append(ex)

    for idx, a in enumerate(combined):
        a.stack_id = target_stack_id
        a.stack_order = idx

    session.commit()
    return {
        "success": True,
        "stack_id": target_stack_id,
        "count": len(combined),
    }


@router.post("/unstack")
def unstack_assets(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Dissolve a stack or remove specific assets from their stack."""
    stack_id = payload.get("stack_id")
    asset_ids = payload.get("asset_ids", [])

    affected_stack_ids: set[str] = set()
    if stack_id:
        affected_stack_ids.add(str(stack_id))
        stmt = select(Asset).where(Asset.stack_id == str(stack_id))
        for a in session.scalars(stmt):
            a.stack_id = None
            a.stack_order = 0
    elif asset_ids:
        int_ids: list[int] = []
        for aid in asset_ids:
            try:
                int_ids.append(int(aid))
            except (ValueError, TypeError):
                continue
        if int_ids:
            assets = list(session.scalars(select(Asset).where(Asset.id.in_(int_ids))).all())
            for a in assets:
                if a.stack_id:
                    affected_stack_ids.add(a.stack_id)
                a.stack_id = None
                a.stack_order = 0

    if affected_stack_ids:
        _clean_up_stacks(session, affected_stack_ids)
    session.commit()
    return {"success": True}


@router.post("/{asset_id}/stack-cover")
def set_stack_cover(
    asset_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Promote an asset to be the cover (top) of its stack."""
    asset = crud.get_asset(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not asset.stack_id:
        raise HTTPException(status_code=400, detail="Asset is not part of a stack")

    siblings = list(
        session.scalars(
            select(Asset)
            .where(Asset.stack_id == asset.stack_id)
            .order_by(Asset.stack_order.asc(), Asset.created_at.desc())
        ).all()
    )
    other_siblings = [s for s in siblings if s.id != asset.id]
    asset.stack_order = 0
    for idx, other in enumerate(other_siblings, start=1):
        other.stack_order = idx

    session.commit()
    return {"success": True, "asset_id": asset.id}


@router.get("/stacks/{stack_id}")
def get_stack_assets(
    stack_id: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return all assets belonging to a stack ordered by stack_order."""
    stmt = (
        select(Asset)
        .where(Asset.stack_id == stack_id)
        .options(selectinload(Asset.generation), selectinload(Asset.categories))
        .order_by(Asset.stack_order.asc(), Asset.created_at.desc())
    )
    assets = list(session.scalars(stmt).all())
    return {
        "stack_id": stack_id,
        "count": len(assets),
        "assets": [serialize_asset(a, include_stack_items=False) for a in assets],
    }


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

