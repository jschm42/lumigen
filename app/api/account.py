"""Self-service account REST API (own profile and password)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import raise_http, require_user, user_service
from app.db import crud
from app.db.engine import get_session
from app.db.models import User
from app.services.user_service import UserServiceError

router = APIRouter(prefix="/account", tags=["account"])

_PROFILE_FIELDS = ("username", "email", "display_name")

MAX_GALLERY_PRESETS = 30
_PRESET_FILTER_KEYS = (
    "q",
    "min_rating",
    "unrated",
    "time_preset",
    "date_from",
    "date_to",
    "category_ids",
    "profile_name",
    "provider",
    "model",
    "collapse_stacks",
)


def _presets_key(user: User) -> str:
    return f"gallery_presets:{user.id}"


def _clean_preset(raw: Any) -> dict[str, Any]:
    """Validate one preset and keep only known filter keys."""
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="Invalid preset.")
    name = str(raw.get("name", "")).strip()
    if not name or len(name) > 40:
        raise HTTPException(status_code=400, detail="Preset names must be 1-40 characters.")
    preset_id = str(raw.get("id", "")).strip()[:40] or name
    filters = raw.get("filters") if isinstance(raw.get("filters"), dict) else {}
    return {
        "id": preset_id,
        "name": name,
        "filters": {key: filters[key] for key in _PRESET_FILTER_KEYS if key in filters},
    }


@router.get("")
def get_account(user: User = Depends(require_user)) -> dict[str, Any]:
    """Return the profile of the logged-in user."""
    return user_service.serialize_user(user)


@router.patch("")
def update_account(
    payload: dict[str, Any],
    request: Request,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update username, e-mail and/or display name of the logged-in user."""
    fields = {key: payload[key] for key in _PROFILE_FIELDS if key in payload}
    db_user = session.merge(user)
    try:
        updated = user_service.update_profile(session, db_user, fields)
    except UserServiceError as exc:
        raise raise_http(exc) from exc
    request.session["username"] = updated.username
    return user_service.serialize_user(updated)


@router.get("/gallery-presets")
def get_gallery_presets(
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Return the saved gallery filter presets of the logged-in user."""
    stored = crud.get_app_setting(session, _presets_key(user), [])
    return stored if isinstance(stored, list) else []


@router.put("/gallery-presets")
def save_gallery_presets(
    payload: list[Any],
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Replace the logged-in user's gallery filter presets (max. 30)."""
    if len(payload) > MAX_GALLERY_PRESETS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_GALLERY_PRESETS} presets are allowed.")
    presets = [_clean_preset(item) for item in payload]
    crud.set_app_setting(session, _presets_key(user), presets)
    return presets


@router.post("/password")
def change_account_password(
    payload: dict[str, Any],
    request: Request,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Change the logged-in user's password.

    Other sessions of the user are signed out; the current session stays valid.
    """
    db_user = session.merge(user)
    try:
        updated = user_service.change_password(
            session,
            db_user,
            current_password=str(payload.get("current_password", "")),
            new_password=str(payload.get("new_password", "")),
        )
    except UserServiceError as exc:
        raise raise_http(exc) from exc
    user_service.start_session(request.session, updated)
    return {"success": True}
