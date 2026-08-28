"""Sessions REST API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import crud
from app.db.engine import get_session
from app.db.models import Generation

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
def list_sessions(
    q: str = Query(default=""),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List all chat sessions / artbooks with summary stats."""
    db_sessions = crud.list_chat_sessions(session)
    result = []
    q_lower = q.lower().strip()

    for s in db_sessions:
        if q_lower and q_lower not in (s.title or "").lower():
            continue

        generations = (
            session.query(Generation)
            .filter(Generation.chat_session_id == s.chat_session_id)
            .all()
        )
        gen_count = len(generations)
        asset_count = sum(len(g.assets) for g in generations)

        cover_url = None
        if s.cover_asset_id:
            cover_url = f"/assets/{s.cover_asset_id}/thumb"
        elif generations and generations[0].assets:
            cover_url = f"/assets/{generations[0].assets[0].id}/thumb"

        result.append({
            "id": s.id,
            "session_token": s.chat_session_id,
            "title": s.title or "Unbenannte Session",
            "created_at": s.created_at.isoformat() if s.created_at else "",
            "updated_at": s.updated_at.isoformat() if s.updated_at else "",
            "cover_asset_id": s.cover_asset_id,
            "cover_asset_url": cover_url,
            "generation_count": gen_count,
            "asset_count": asset_count,
            "last_llm_model": getattr(s, "last_llm_model", None),
            "last_model_config_id": getattr(s, "last_model_config_id", None),
            "is_pinned": getattr(s, "is_pinned", False),
        })

    return {
        "sessions": result,
        "total": len(result),
    }


@router.get("/{session_token}")
def get_session_history(
    session_token: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get generations history for a specific session."""
    chat_session = crud.get_chat_session(session, session_token)
    generations = (
        session.query(Generation)
        .filter(Generation.chat_session_id == session_token)
        .order_by(Generation.created_at.asc())
        .all()
    )

    gen_list = []
    for g in generations:
        assets_list = []
        for a in g.assets:
            assets_list.append({
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
            })

        gen_list.append({
            "id": g.id,
            "status": g.status,
            "progress": g.progress,
            "error_message": g.error_message,
            "prompt": g.prompt,
            "negative_prompt": g.negative_prompt,
            "session_token": g.chat_session_id,
            "created_at": g.created_at.isoformat() if g.created_at else "",
            "completed_at": g.completed_at.isoformat() if g.completed_at else None,
            "model_name": g.model,
            "provider": g.provider,
            "aspect_ratio": g.aspect_ratio,
            "resolution": g.resolution,
            "seed": g.seed,
            "assets": assets_list,
        })

    return {
        "session": {
            "id": chat_session.id if chat_session else 0,
            "session_token": session_token,
            "title": chat_session.title if chat_session else "Session",
        },
        "generations": gen_list,
    }


@router.patch("/{session_token}/rename")
def rename_session(
    session_token: str,
    payload: dict[str, Any],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Rename a session."""
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")

    chat_session = crud.get_chat_session(session, session_token)
    if not chat_session:
        chat_session = crud.create_chat_session(session, chat_session_id=session_token, title=title)
    else:
        chat_session.title = title
        session.commit()

    return {
        "success": True,
        "session": {
            "id": chat_session.id,
            "session_token": chat_session.chat_session_id,
            "title": chat_session.title,
        },
    }


@router.delete("/{session_token}")
def delete_session(
    session_token: str,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete a session and all its generations."""
    crud.delete_chat_session(session, session_token)
    return {"success": True}


@router.post("/{session_token}/pin")
def toggle_session_pin(
    session_token: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Toggle pin on a session."""
    chat_session = crud.get_chat_session(session, session_token)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")

    new_pin = not getattr(chat_session, "is_pinned", False)
    setattr(chat_session, "is_pinned", new_pin)
    session.commit()
    return {"success": True, "is_pinned": new_pin}
