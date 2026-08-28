"""Auth REST API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import crud
from app.db.engine import get_session
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
auth_service = AuthService()


def get_current_user_from_request(request: Request, session: Session):
    """Retrieve current authenticated user from session cookie."""
    user_id = request.session.get("user_id")
    if isinstance(user_id, int):
        user = crud.get_user(session, user_id)
        if user and user.is_active:
            return user
    return None


@router.get("/status")
def auth_status(request: Request, session: Session = Depends(get_session)) -> dict[str, Any]:
    """Return authentication status, current user, and onboarding state."""
    users_exist = crud.count_users(session) > 0
    user = get_current_user_from_request(request, session)
    return {
        "authenticated": user is not None,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        } if user else None,
        "needs_onboarding": not users_exist,
        "app_version": settings.app_version,
    }


@router.post("/login")
async def auth_login(
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Authenticate a user and start session."""
    # Support both JSON payload and form data
    if request.headers.get("content-type", "").startswith("application/json"):
        payload = await request.json()
        username = payload.get("username", "").strip()
        password = payload.get("password", "")
    else:
        form = await request.form()
        username = str(form.get("username", "")).strip()
        password = str(form.get("password", ""))

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    user = crud.get_user_by_username(session, username)
    if not user or not user.is_active or not auth_service.verify_password(password, user.password_hash):
        raise HTTPException(status_code=400, detail="Ungültige Anmeldedaten")

    request.session["user_id"] = user.id
    request.session["user_role"] = user.role
    return {
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        },
    }


@router.post("/logout")
def auth_logout(request: Request) -> dict[str, bool]:
    """Clear user session."""
    request.session.clear()
    return {"success": True}


@router.post("/setup")
async def auth_setup(
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Initial admin onboarding setup."""
    users_exist = crud.count_users(session) > 0
    if users_exist:
        raise HTTPException(status_code=400, detail="Onboarding already completed")

    if request.headers.get("content-type", "").startswith("application/json"):
        payload = await request.json()
        username = payload.get("username", "").strip()
        password = payload.get("password", "")
    else:
        form = await request.form()
        username = str(form.get("username", "")).strip()
        password = str(form.get("password", ""))

    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    password_hash = auth_service.hash_password(password)
    user = crud.create_user(
        session,
        username=username,
        password_hash=password_hash,
        role="admin",
        is_active=True,
    )
    request.session["user_id"] = user.id
    request.session["user_role"] = user.role
    return {
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        },
    }
