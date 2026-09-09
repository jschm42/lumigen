"""Categories REST API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import crud
from app.db.engine import get_session
from app.db.models import Category

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
def list_categories(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """Return all categories with associated asset and profile counts."""
    cats = crud.list_categories(session)
    return [
        {
            "id": c.id,
            "name": c.name,
            "asset_count": len(c.assets),
            "profile_count": len(c.profiles),
        }
        for c in cats
    ]


@router.post("")
def create_category(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create a new category and return its details."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    existing = session.scalar(select(Category).where(Category.name == name))
    if existing:
        raise HTTPException(status_code=409, detail="A category with this name already exists")

    cat = crud.create_category(session, name=name)
    return {
        "id": cat.id,
        "name": cat.name,
        "asset_count": 0,
        "profile_count": 0,
    }


@router.put("/{category_id}")
def update_category(
    category_id: int,
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update a category name."""
    cat = crud.get_category(session, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    existing = session.scalar(
        select(Category).where(Category.name == name, Category.id != category_id)
    )
    if existing:
        raise HTTPException(status_code=409, detail="A category with this name already exists")

    crud.update_category(session, cat, name=name)
    return {
        "id": cat.id,
        "name": cat.name,
        "asset_count": len(cat.assets),
        "profile_count": len(cat.profiles),
    }


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete a category by its ID."""
    cat = crud.get_category(session, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    crud.delete_category(session, cat)
    return {"success": True}
