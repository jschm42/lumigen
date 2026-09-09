"""Sessions REST API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.assets import serialize_asset
from app.db import crud
from app.db.engine import get_session
from app.db.models import Generation

router = APIRouter(prefix="/sessions", tags=["sessions"])


def generation_session_token(generation: Generation) -> str:
    """Extract or derive the session token from a Generation record."""
    snapshot = generation.request_snapshot_json or {}
    if snapshot.get("chat_hidden") or snapshot.get("chat_deleted"):
        return ""
    raw_token = snapshot.get("chat_session_id") or snapshot.get("conversation")
    if isinstance(raw_token, str):
        token = raw_token.strip()
        if token:
            return token
    return ""


@router.get("")
def list_sessions(
    q: str = Query(default=""),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List all chat sessions / artbooks with summary stats."""
    db_sessions = crud.list_chat_sessions(session)
    all_generations = session.query(Generation).all()
    generations_by_session: dict[str, list[Generation]] = {}
    for g in all_generations:
        tok = generation_session_token(g)
        generations_by_session.setdefault(tok, []).append(g)

    # Lazily ensure any generation sessions have a ChatSession row in the database
    existing_tokens = {s.chat_session_id for s in db_sessions if s.chat_session_id}
    created_any = False
    for tok, gens in generations_by_session.items():
        if tok and tok.startswith("session:") and tok not in existing_tokens:
            first_prompt = gens[0].prompt_user or gens[0].prompt_final or "Neue Session"
            raw_prompt = first_prompt.strip().replace("\r\n", " ").replace("\n", " ")
            cleaned_title = raw_prompt[:40].rsplit(" ", 1)[0] if len(raw_prompt) > 40 else raw_prompt
            cleaned_title = cleaned_title.strip() or "Neue Session"
            new_s = crud.create_chat_session(
                session,
                chat_session_id=tok,
                title=cleaned_title,
            )
            db_sessions.append(new_s)
            existing_tokens.add(tok)
            created_any = True

    if created_any:
        from datetime import datetime
        db_sessions.sort(key=lambda s: s.updated_at or s.created_at or datetime.min, reverse=True)

    result = []
    q_lower = q.lower().strip()

    for s in db_sessions:
        if not s.chat_session_id or not s.chat_session_id.startswith("session:"):
            continue
        if q_lower and q_lower not in (s.title or "").lower():
            continue

        generations = generations_by_session.get(s.chat_session_id, [])
        gen_count = len(generations)
        asset_count = sum(len(g.assets) for g in generations)

        cover_url = None
        cover_id = getattr(s, "cover_asset_id", None)
        if cover_id:
            cover_url = f"/assets/{cover_id}/thumb"
        elif generations and generations[0].assets:
            cover_url = f"/assets/{generations[0].assets[0].id}/thumb"

        result.append({
            "id": s.id,
            "session_token": s.chat_session_id,
            "title": s.title or "Unbenannte Session",
            "created_at": s.created_at.isoformat() if s.created_at else "",
            "updated_at": s.updated_at.isoformat() if s.updated_at else "",
            "cover_asset_id": cover_id,
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
    all_generations = (
        session.query(Generation)
        .order_by(Generation.created_at.asc())
        .all()
    )
    generations = [g for g in all_generations if generation_session_token(g) == session_token]

    gen_list = []
    for g in generations:
        req_snapshot = g.request_snapshot_json or {}
        progress = 100 if g.status == "succeeded" else (0 if g.status == "failed" else 50)
        assets_list = [serialize_asset(a, g) for a in g.assets]

        gen_list.append({
            "id": g.id,
            "status": g.status,
            "progress": progress,
            "error_message": g.error,
            "prompt": g.prompt_user or g.prompt_final,
            "negative_prompt": req_snapshot.get("negative_prompt", ""),
            "session_token": session_token,
            "created_at": g.created_at.isoformat() if g.created_at else "",
            "completed_at": g.finished_at.isoformat() if g.finished_at else None,
            "model_name": g.model,
            "provider": g.provider,
            "aspect_ratio": req_snapshot.get("aspect_ratio", "1:1"),
            "resolution": req_snapshot.get("resolution", "1K"),
            "seed": req_snapshot.get("seed"),
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


@router.delete("")
@router.post("/delete-all")
def delete_all_sessions(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Delete all chat sessions and clear session linkages from generations."""
    db_sessions = crud.list_chat_sessions(session)
    count = len(db_sessions)
    for s in db_sessions:
        crud.delete_chat_session(session, s)

    all_generations = session.query(Generation).all()
    for g in all_generations:
        snapshot = dict(g.request_snapshot_json or {})
        if "chat_session_id" in snapshot or "chat_session_title" in snapshot or "conversation" in snapshot:
            snapshot["chat_hidden"] = True
            snapshot["chat_deleted"] = True
            snapshot.pop("chat_session_id", None)
            snapshot.pop("chat_session_title", None)
            snapshot.pop("conversation", None)
            g.request_snapshot_json = snapshot
            session.add(g)

    session.commit()
    return {"success": True, "deleted_count": count}


@router.delete("/{session_token}")
def delete_session(
    session_token: str,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete a session."""
    chat_session = crud.get_chat_session(session, session_token)
    if chat_session:
        crud.delete_chat_session(session, chat_session)

    all_generations = session.query(Generation).all()
    for g in all_generations:
        if generation_session_token(g) == session_token:
            snapshot = dict(g.request_snapshot_json or {})
            snapshot["chat_hidden"] = True
            snapshot["chat_deleted"] = True
            snapshot.pop("chat_session_id", None)
            snapshot.pop("chat_session_title", None)
            snapshot.pop("conversation", None)
            g.request_snapshot_json = snapshot
            session.add(g)
    session.commit()
    return {"success": True}


@router.post("/{session_token}/pin")
def toggle_session_pin(
    session_token: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Toggle pin status of a session."""
    chat_session = crud.get_chat_session(session, session_token)
    if not chat_session:
        chat_session = crud.create_chat_session(session, chat_session_id=session_token, title="Session")

    current_pin = getattr(chat_session, "is_pinned", False)
    setattr(chat_session, "is_pinned", not current_pin)
    session.commit()
    return {"success": True, "is_pinned": chat_session.is_pinned}
