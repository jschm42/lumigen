"""User account management: validation, profile updates, passwords and reset tokens."""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
from collections.abc import MutableMapping
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import crud
from app.db.models import PasswordResetToken, User
from app.services.auth_service import AuthService
from app.services.mail_service import MailService

logger = logging.getLogger(__name__)

ADMIN_ROLE = "admin"
USER_ROLE = "user"
VALID_ROLES = frozenset({ADMIN_ROLE, USER_ROLE})

_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,49}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserServiceError(Exception):
    """Raised for user-facing validation or permission errors.

    ``status_code`` maps directly to the HTTP status the API layer should return.
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _as_utc(value: datetime | None) -> datetime | None:
    """Return *value* as an aware UTC datetime (SQLite drops tzinfo on read)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def hash_reset_token(raw_token: str) -> str:
    """Return the hex SHA-256 digest used to store a reset token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class UserService:
    """Business logic for user accounts shared by the auth, account and admin APIs."""

    def __init__(
        self,
        settings: Settings,
        auth_service: AuthService | None = None,
        mail_service: MailService | None = None,
    ) -> None:
        self.settings = settings
        self.auth_service = auth_service or AuthService()
        self.mail_service = mail_service or MailService(settings)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def validate_username(self, username: str | None) -> str:
        """Return the trimmed username or raise if it is not 3-50 safe characters."""
        value = (username or "").strip()
        if not _USERNAME_RE.match(value):
            raise UserServiceError(
                "Username must be 3-50 characters and may only contain letters, "
                "digits, dots, dashes and underscores."
            )
        return value

    def normalize_email(self, email: str | None) -> str | None:
        """Return a lower-cased e-mail address, ``None`` for blank input, or raise if invalid."""
        value = (email or "").strip().lower()
        if not value:
            return None
        if len(value) > 254 or not _EMAIL_RE.match(value):
            raise UserServiceError("Please enter a valid e-mail address.")
        return value

    def normalize_display_name(self, display_name: str | None) -> str | None:
        """Return the trimmed display name or ``None``; raise if longer than 80 characters."""
        value = (display_name or "").strip()
        if not value:
            return None
        if len(value) > 80:
            raise UserServiceError("Display name must be at most 80 characters.")
        return value

    def validate_password(self, password: str | None) -> str:
        """Raise unless *password* satisfies the configured minimum length."""
        value = password or ""
        min_length = max(8, int(self.settings.password_min_length))
        if len(value.strip()) < min_length:
            raise UserServiceError(f"Password must be at least {min_length} characters.")
        if len(value) > 256:
            raise UserServiceError("Password must be at most 256 characters.")
        return value

    def validate_role(self, role: str | None) -> str:
        """Return a normalized role or raise if it is unknown."""
        value = (role or USER_ROLE).strip().lower()
        if value not in VALID_ROLES:
            raise UserServiceError("Role must be either 'admin' or 'user'.")
        return value

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    @staticmethod
    def serialize_user(user: User) -> dict[str, Any]:
        """Return the public JSON representation of *user* (never includes secrets)."""
        created_at = _as_utc(user.created_at)
        last_login_at = _as_utc(user.last_login_at)
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "is_active": bool(user.is_active),
            "created_at": created_at.isoformat() if created_at else None,
            "last_login_at": last_login_at.isoformat() if last_login_at else None,
        }

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------
    @staticmethod
    def start_session(session_data: MutableMapping[str, Any], user: User) -> None:
        """Write the auth keys for *user* into a Starlette session mapping."""
        session_data["user_id"] = user.id
        session_data["user_role"] = user.role
        session_data["username"] = user.username
        session_data["session_version"] = int(user.session_version or 0)

    @staticmethod
    def session_matches_user(session_data: MutableMapping[str, Any] | dict[str, Any], user: User) -> bool:
        """Return ``True`` if the session was issued for the user's current credentials."""
        raw = session_data.get("session_version", 0)
        try:
            version = int(raw or 0)
        except (TypeError, ValueError):
            return False
        return version == int(user.session_version or 0)

    def resolve_session_user(
        self, db: Session, session_data: MutableMapping[str, Any] | dict[str, Any]
    ) -> User | None:
        """Return the active user referenced by a session mapping, or ``None``."""
        user_id = session_data.get("user_id")
        if not isinstance(user_id, int):
            return None
        user = crud.get_user(db, user_id)
        if not user or not user.is_active:
            return None
        if not self.session_matches_user(session_data, user):
            return None
        return user

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def find_by_identifier(self, db: Session, identifier: str) -> User | None:
        """Look up a user by exact username, then case-insensitive username, then e-mail."""
        value = (identifier or "").strip()
        if not value:
            return None
        user = crud.get_user_by_username(db, value)
        if user is None:
            user = crud.get_user_by_username_ci(db, value)
        if user is None and "@" in value:
            user = crud.get_user_by_email(db, value)
        return user

    def authenticate(self, db: Session, identifier: str, password: str) -> User | None:
        """Return the active user for *identifier*/*password*, or ``None`` if invalid."""
        user = self.find_by_identifier(db, identifier)
        if user is None:
            # Burn comparable time so response timing does not reveal valid usernames.
            self.auth_service.verify_password(password, _DUMMY_HASH)
            return None
        if not user.is_active:
            return None
        if not self.auth_service.verify_password(password, user.password_hash):
            return None
        return user

    def record_login(self, db: Session, user: User) -> None:
        """Store the current time as the user's last successful login."""
        crud.update_user(db, user, last_login_at=datetime.now(UTC))

    # ------------------------------------------------------------------
    # Account management
    # ------------------------------------------------------------------
    def _ensure_unique(
        self, db: Session, *, username: str | None, email: str | None, exclude_id: int | None
    ) -> None:
        if username is not None:
            existing = crud.get_user_by_username_ci(db, username)
            if existing is not None and existing.id != exclude_id:
                raise UserServiceError("This username is already taken.", status_code=409)
        if email is not None:
            existing = crud.get_user_by_email(db, email)
            if existing is not None and existing.id != exclude_id:
                raise UserServiceError("This e-mail address is already in use.", status_code=409)

    def create_user(
        self,
        db: Session,
        *,
        username: str,
        password: str,
        role: str = USER_ROLE,
        email: str | None = None,
        display_name: str | None = None,
        is_active: bool = True,
    ) -> User:
        """Validate input and create a new user account."""
        clean_username = self.validate_username(username)
        clean_email = self.normalize_email(email)
        clean_display = self.normalize_display_name(display_name)
        clean_role = self.validate_role(role)
        self.validate_password(password)
        self._ensure_unique(db, username=clean_username, email=clean_email, exclude_id=None)
        try:
            return crud.create_user(
                db,
                username=clean_username,
                password_hash=self.auth_service.hash_password(password),
                role=clean_role,
                is_active=bool(is_active),
                email=clean_email,
                display_name=clean_display,
            )
        except IntegrityError as exc:
            db.rollback()
            raise UserServiceError("Username or e-mail is already in use.", status_code=409) from exc

    def update_profile(self, db: Session, user: User, fields: dict[str, Any]) -> User:
        """Update the self-service profile fields present in *fields*.

        Supported keys: ``username``, ``email``, ``display_name``. Keys that are absent
        are left unchanged; an empty ``email`` or ``display_name`` clears the value.
        """
        updates: dict[str, Any] = {}
        if "username" in fields:
            updates["username"] = self.validate_username(fields.get("username"))
        if "email" in fields:
            updates["email"] = self.normalize_email(fields.get("email"))
        if "display_name" in fields:
            updates["display_name"] = self.normalize_display_name(fields.get("display_name"))
        if not updates:
            return user
        self._ensure_unique(
            db,
            username=updates.get("username"),
            email=updates.get("email"),
            exclude_id=user.id,
        )
        try:
            return crud.update_user(db, user, **updates)
        except IntegrityError as exc:
            db.rollback()
            raise UserServiceError("Username or e-mail is already in use.", status_code=409) from exc

    def admin_update_user(
        self, db: Session, *, acting_user: User | None, user: User, fields: dict[str, Any]
    ) -> User:
        """Apply admin changes (profile fields, ``role``, ``is_active``) with safety guards.

        Admins cannot demote or deactivate themselves, and the last active admin can never
        lose admin rights or be deactivated.
        """
        updates: dict[str, Any] = {}
        if "role" in fields:
            updates["role"] = self.validate_role(fields.get("role"))
        if "is_active" in fields:
            updates["is_active"] = bool(fields.get("is_active"))

        is_self = acting_user is not None and acting_user.id == user.id
        loses_admin = user.role == ADMIN_ROLE and (
            updates.get("role", user.role) != ADMIN_ROLE or updates.get("is_active", user.is_active) is False
        )
        if loses_admin:
            if is_self:
                raise UserServiceError("You cannot remove your own admin access or deactivate yourself.")
            if user.is_active and crud.count_admin_users(db, active_only=True) <= 1:
                raise UserServiceError("At least one active administrator is required.")
        if is_self and updates.get("is_active") is False:
            raise UserServiceError("You cannot deactivate your own account.")

        user = self.update_profile(db, user, fields)
        if updates:
            if updates.get("is_active") is False or updates.get("role", user.role) != user.role:
                # Force re-login so role/active changes take effect immediately.
                updates["session_version"] = int(user.session_version or 0) + 1
            user = crud.update_user(db, user, **updates)
        return user

    def delete_user(self, db: Session, *, acting_user: User | None, user: User) -> None:
        """Delete *user* unless it is the acting admin or the last active admin."""
        if acting_user is not None and acting_user.id == user.id:
            raise UserServiceError("You cannot delete your own account.")
        if user.role == ADMIN_ROLE and user.is_active and crud.count_admin_users(db, active_only=True) <= 1:
            raise UserServiceError("At least one active administrator is required.")
        crud.delete_user(db, user)

    def set_password(self, db: Session, user: User, new_password: str) -> User:
        """Replace the user's password and invalidate all existing sessions."""
        self.validate_password(new_password)
        return crud.update_user(
            db,
            user,
            password_hash=self.auth_service.hash_password(new_password),
            session_version=int(user.session_version or 0) + 1,
        )

    def change_password(
        self, db: Session, user: User, *, current_password: str, new_password: str
    ) -> User:
        """Change the password after verifying *current_password*."""
        if not self.auth_service.verify_password(current_password, user.password_hash):
            raise UserServiceError("Current password is incorrect.")
        if (current_password or "").strip() == (new_password or "").strip():
            raise UserServiceError("The new password must differ from the current one.")
        return self.set_password(db, user, new_password)

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------
    def create_reset_token(self, db: Session, user: User) -> tuple[str, datetime]:
        """Create a single-use reset token for *user* and return ``(raw_token, expires_at)``.

        Only the token hash is stored; earlier unused tokens of the user are invalidated.
        """
        raw_token = secrets.token_urlsafe(32)
        ttl = max(5, int(self.settings.password_reset_token_ttl_minutes))
        expires_at = datetime.now(UTC) + timedelta(minutes=ttl)
        crud.create_password_reset_token(
            db, user=user, token_hash=hash_reset_token(raw_token), expires_at=expires_at
        )
        return raw_token, expires_at

    def build_reset_url(self, base_url: str, raw_token: str) -> str:
        """Return the absolute SPA URL that lets the user choose a new password."""
        root = (self.settings.public_base_url or base_url or "").rstrip("/")
        return f"{root}/reset-password?token={raw_token}"

    def request_password_reset(self, db: Session, identifier: str, *, base_url: str) -> None:
        """Issue a reset token for the account matching *identifier* (username or e-mail).

        Always returns silently so callers cannot probe which accounts exist. The link is
        e-mailed when SMTP is configured and the user has an address; otherwise it is
        written to the server log for the operator.
        """
        user = self.find_by_identifier(db, identifier)
        if user is None or not user.is_active:
            return

        latest = crud.latest_password_reset_token(db, user.id)
        cooldown = max(0, int(self.settings.password_reset_request_cooldown_seconds))
        latest_created = _as_utc(latest.created_at) if latest else None
        if latest_created and (datetime.now(UTC) - latest_created).total_seconds() < cooldown:
            return

        raw_token, expires_at = self.create_reset_token(db, user)
        reset_url = self.build_reset_url(base_url, raw_token)
        ttl_minutes = max(5, int(self.settings.password_reset_token_ttl_minutes))

        delivered = False
        if user.email:
            delivered = self.mail_service.send(
                to=user.email,
                subject=f"{self.settings.app_name}: reset your password",
                body=(
                    f"Hello {user.display_name or user.username},\n\n"
                    "a password reset was requested for your account. Open the link below "
                    f"within {ttl_minutes} minutes to choose a new password:\n\n"
                    f"{reset_url}\n\n"
                    "If you did not request this, you can ignore this e-mail.\n"
                ),
            )
        if not delivered:
            logger.warning(
                "Password reset requested for user '%s'. No e-mail delivery available; "
                "reset link (valid until %s UTC): %s",
                user.username,
                expires_at.strftime("%Y-%m-%d %H:%M"),
                reset_url,
            )

    def get_valid_reset_token(self, db: Session, raw_token: str) -> PasswordResetToken | None:
        """Return the stored token if it exists, is unused, unexpired and its user is active."""
        value = (raw_token or "").strip()
        if not value or len(value) > 256:
            return None
        row = crud.get_password_reset_token(db, hash_reset_token(value))
        if row is None or row.used_at is not None:
            return None
        expires_at = _as_utc(row.expires_at)
        if expires_at is None or expires_at <= datetime.now(UTC):
            return None
        if row.user is None or not row.user.is_active:
            return None
        return row

    def reset_password(self, db: Session, raw_token: str, new_password: str) -> User:
        """Set a new password using a valid reset token and consume the token."""
        row = self.get_valid_reset_token(db, raw_token)
        if row is None:
            raise UserServiceError("This reset link is invalid or has expired.")
        self.validate_password(new_password)
        user = row.user
        row.used_at = datetime.now(UTC)
        db.add(row)
        db.commit()
        return self.set_password(db, user, new_password)


_DUMMY_HASH = AuthService().hash_password(secrets.token_urlsafe(16))
