"""Shared FastAPI dependencies for authentication and authorization."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.engine import get_session
from app.db.models import User
from app.services.user_service import ADMIN_ROLE, UserService, UserServiceError

user_service = UserService(get_settings())


def get_optional_user(request: Request, session: Session) -> User | None:
    """Return the active user bound to the request session, or ``None``."""
    return user_service.resolve_session_user(session, request.session)


def require_user(request: Request, session: Session = Depends(get_session)) -> User:
    """Dependency that returns the logged-in user or raises 401."""
    user = get_optional_user(request, session)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(request: Request, session: Session = Depends(get_session)) -> User:
    """Dependency that returns the logged-in admin or raises 401/403."""
    user = require_user(request, session)
    if user.role != ADMIN_ROLE:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def raise_http(exc: UserServiceError) -> HTTPException:
    """Translate a ``UserServiceError`` into an ``HTTPException``."""
    return HTTPException(status_code=exc.status_code, detail=exc.message)
