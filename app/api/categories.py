"""Categories REST API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import crud
from app.db.engine import get_session

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
def list_categories(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """Return all categories."""
    cats = crud.list_categories(session)
    return [{"id": c.id, "name": c.name} for c in cats]


@router.post("")
def create_category(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create a new category."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    cat = crud.create_category(session, name=name)
    return {"id": cat.id, "name": cat.name}
