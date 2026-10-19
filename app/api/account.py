"""Self-service account REST API (own profile and password)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import raise_http, require_user, user_service
from app.db.engine import get_session
from app.db.models import User
from app.services.user_service import UserServiceError

router = APIRouter(prefix="/account", tags=["account"])

_PROFILE_FIELDS = ("username", "email", "display_name")


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
