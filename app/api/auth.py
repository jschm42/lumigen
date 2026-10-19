"""Auth REST API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user, raise_http, user_service
from app.config import get_settings
from app.db import crud
from app.db.engine import get_session
from app.services.app_settings_service import AppSettingsService
from app.services.user_service import ADMIN_ROLE, UserServiceError

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
app_settings_service = AppSettingsService()


def get_current_user_from_request(request: Request, session: Session):
    """Retrieve current authenticated user from session cookie."""
    return get_optional_user(request, session)


async def _read_payload(request: Request) -> dict[str, Any]:
    """Return the request body as a dict, supporting JSON and form submissions."""
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            payload = await request.json()
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}
    form = await request.form()
    return {key: value for key, value in form.items()}


@router.get("/status")
def auth_status(request: Request, session: Session = Depends(get_session)) -> dict[str, Any]:
    """Return authentication status, current user, onboarding state and UI settings."""
    users_exist = crud.count_users(session) > 0
    user = get_current_user_from_request(request, session)
    return {
        "authenticated": user is not None,
        "user": user_service.serialize_user(user) if user else None,
        "needs_onboarding": not users_exist,
        "app_version": settings.app_version,
        "ui_settings": app_settings_service.get_ui_settings(session) if user else {},
        "password_min_length": max(8, settings.password_min_length),
    }


@router.post("/login")
async def auth_login(
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Authenticate a user by username or e-mail and start a session."""
    payload = await _read_payload(request)
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    remember_raw = payload.get("remember_me", False)
    remember_me = remember_raw in (True, "true", "1", "on")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    user = user_service.authenticate(session, username, password)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    request.session.clear()
    user_service.start_session(request.session, user)
    request.session["remember_me"] = remember_me
    user_service.record_login(session, user)
    return {"success": True, "user": user_service.serialize_user(user)}


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
    if crud.count_users(session) > 0:
        raise HTTPException(status_code=400, detail="Onboarding already completed")

    payload = await _read_payload(request)
    try:
        user = user_service.create_user(
            session,
            username=str(payload.get("username", "")),
            password=str(payload.get("password", "")),
            email=str(payload.get("email", "") or "") or None,
            role=ADMIN_ROLE,
        )
    except UserServiceError as exc:
        raise raise_http(exc) from exc

    user_service.start_session(request.session, user)
    user_service.record_login(session, user)
    return {"success": True, "user": user_service.serialize_user(user)}


@router.post("/password/forgot")
async def auth_forgot_password(
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Request a password reset link for a username or e-mail address.

    The response is identical whether or not the account exists.
    """
    payload = await _read_payload(request)
    identifier = str(payload.get("identifier") or payload.get("username") or "").strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="Please enter your username or e-mail address.")

    user_service.request_password_reset(session, identifier, base_url=str(request.base_url))
    return {
        "success": True,
        "message": (
            "If an account matches, a reset link has been sent. Without e-mail delivery, "
            "ask your administrator for the link."
        ),
    }


@router.post("/password/validate-token")
async def auth_validate_reset_token(
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return whether a password reset token is still usable."""
    payload = await _read_payload(request)
    row = user_service.get_valid_reset_token(session, str(payload.get("token", "")))
    return {"valid": row is not None}


@router.post("/password/reset")
async def auth_reset_password(
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Set a new password using a reset token; all existing sessions are invalidated."""
    payload = await _read_payload(request)
    try:
        user_service.reset_password(
            session,
            str(payload.get("token", "")),
            str(payload.get("new_password", "")),
        )
    except UserServiceError as exc:
        raise raise_http(exc) from exc
    request.session.clear()
    return {"success": True}
