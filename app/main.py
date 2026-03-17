from __future__ import annotations

import base64
import copy
import hmac
import json
import logging
import os
import secrets
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import uvicorn
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import get_settings
from app.db import crud
from app.db.engine import SessionLocal, get_session, init_db
from app.db.models import Asset, Generation, User
from app.providers.base import ProviderError
from app.providers.fal_upscale_adapter import FalUpscaleService
from app.providers.registry import ProviderRegistry
from app.services.auth_service import AuthService
from app.services.enhancement_service import EnhancementService
from app.services.gallery_service import GalleryService
from app.services.generation_service import GenerationService
from app.services.model_config_service import ModelConfigService
from app.services.sidecar_service import SidecarService
from app.services.storage_service import StorageService
from app.services.thumbnail_service import ThumbnailService
from app.services.upscale_service import UpscaleService
from app.utils.jsonutil import dumps_json
from app.utils.paths import ensure_dir
from app.utils.slugify import slugify

settings = get_settings()

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

MAX_INPUT_IMAGES = 5
MAX_CATEGORY_NAME_LENGTH = 30
MAX_PROFILE_NAME_LENGTH = 50
MAX_MODEL_CONFIG_NAME_LENGTH = 50
MAX_FAL_MODEL_IDENTIFIER_LENGTH = 160
MAX_UPLOAD_BYTES = (
    settings.max_upload_size_mb * 1024 * 1024
    if settings.max_upload_size_mb is not None
    else None
)
ADMIN_SECTIONS = {"models", "dimensions", "categories", "enhancement", "about"}
ADMIN_USER_SECTIONS = {"models", "dimensions", "categories", "enhancement", "apikeys", "upscaling", "users", "about"}
ADMIN_ROLE = "admin"
USER_ROLE = "user"
APP_COPYRIGHT_TEXT = "(c) 2026 by Jean Schmitz"
OPENROUTER_ALLOWED_ASPECT_RATIOS = {
    "1:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
}
OPENROUTER_ALLOWED_IMAGE_SIZES = {"1K", "2K", "4K"}
FAL_ALLOWED_ASPECT_RATIOS = {
    "auto",
    "21:9",
    "16:9",
    "3:2",
    "4:3",
    "5:4",
    "1:1",
    "4:5",
    "3:4",
    "2:3",
    "9:16",
    "4:1",
    "1:4",
    "8:1",
    "1:8",
}
FAL_ALLOWED_RESOLUTIONS = {"0.5K", "1K", "2K", "4K"}
FAL_IMAGE_SIZE_TO_ASPECT_RATIO = {
    "square_hd": "1:1",
    "square": "1:1",
    "portrait_4_3": "3:4",
    "portrait_16_9": "9:16",
    "landscape_4_3": "4:3",
    "landscape_16_9": "16:9",
}


def parse_proxy_trusted_hosts(raw: str) -> str | list[str]:
    value = (raw or "").strip()
    if not value:
        return "127.0.0.1"
    if value == "*":
        return "*"
    hosts = [item.strip() for item in value.split(",") if item.strip()]
    if not hosts:
        return "127.0.0.1"
    return hosts


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    ensure_dir(settings.data_dir)
    ensure_dir(settings.default_base_dir)
    init_db()
    with SessionLocal() as session:
        crud.ensure_default_storage_template(
            session,
            base_dir=settings.default_base_dir,
            template=settings.default_storage_template,
        )
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
if settings.proxy_headers_enabled:
    app.add_middleware(
        ProxyHeadersMiddleware,
        trusted_hosts=parse_proxy_trusted_hosts(settings.proxy_headers_trusted_hosts),
    )
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=settings.session_https_only,
)

template_dir = Path(__file__).resolve().parent / "web" / "templates"
static_dir = Path(__file__).resolve().parent / "web" / "static"

templates = Jinja2Templates(directory=str(template_dir))
templates.env.globals["app_version"] = settings.app_version
templates.env.filters["dict"] = dict


def static_url(path: str) -> str:
    normalized = path.lstrip("/")
    base_url = str(app.url_path_for("static", path=normalized))
    file_path = static_dir / normalized
    try:
        version = int(file_path.stat().st_mtime)
    except OSError:
        return base_url
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}v={version}"


templates.env.globals["static_url"] = static_url

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

storage_service = StorageService(max_slug_length=settings.max_slug_length)
thumbnail_service = ThumbnailService(storage_service, max_px=settings.thumb_max_px)
sidecar_service = SidecarService(storage_service)
model_config_service = ModelConfigService(settings)
enhancement_service = EnhancementService(settings, model_config_service)
upscale_service = UpscaleService(settings)
fal_upscale_service = FalUpscaleService()
provider_registry = ProviderRegistry(settings)
generation_service = GenerationService(
    settings=settings,
    registry=provider_registry,
    storage_service=storage_service,
    thumbnail_service=thumbnail_service,
    sidecar_service=sidecar_service,
    model_config_service=model_config_service,
    upscale_service=upscale_service,
    fal_upscale_service=fal_upscale_service,
)
gallery_service = GalleryService(default_page_size=settings.default_page_size)
auth_service = AuthService()


def has_bootstrapped_users(session: Session) -> bool:
    return crud.count_admin_users(session, active_only=False) > 0


def get_session_user_id(request: Request) -> int | None:
    raw = request.session.get("user_id")
    if isinstance(raw, int):
        return raw
    return None


def get_current_user(request: Request, session: Session) -> User | None:
    user_id = get_session_user_id(request)
    if not user_id:
        return None
    user = crud.get_user(session, user_id)
    if not user or not user.is_active:
        return None
    return user


def clear_auth_session(request: Request) -> None:
    request.session.pop("user_id", None)
    request.session.pop("user_role", None)
    request.session.pop("username", None)


def start_auth_session(request: Request, user: User) -> None:
    request.session["user_id"] = user.id
    request.session["user_role"] = user.role
    request.session["username"] = user.username


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    issued_at = request.session.get("csrf_issued_at")
    now = int(datetime.now(UTC).timestamp())
    if isinstance(token, str) and token and isinstance(issued_at, int):
        if now - issued_at <= settings.csrf_token_ttl_seconds:
            return token
    token = secrets.token_urlsafe(32)
    request.session["csrf_token"] = token
    request.session["csrf_issued_at"] = now
    return token


templates.env.globals["ensure_csrf_token"] = ensure_csrf_token


def is_csrf_valid(request: Request, provided: str | None) -> bool:
    expected = request.session.get("csrf_token")
    if not isinstance(expected, str) or not expected:
        return False
    candidate = (provided or "").strip()
    if not candidate:
        return False
    return hmac.compare_digest(expected, candidate)


def current_user_is_admin(request: Request) -> bool:
    return str(request.session.get("user_role") or "").strip().lower() == ADMIN_ROLE


def read_session_cookie_payload(request: Request) -> dict[str, Any]:
    cookie_value = request.cookies.get(settings.session_cookie_name)
    if not cookie_value:
        return {}
    signer = TimestampSigner(str(settings.session_secret_key))
    try:
        unsigned = signer.unsign(
            cookie_value,
            max_age=settings.session_max_age_seconds,
        )
        decoded = base64.b64decode(unsigned)
        payload = json.loads(decoded)
        if isinstance(payload, dict):
            return payload
    except (BadSignature, SignatureExpired, ValueError, TypeError, json.JSONDecodeError):
        return {}
    return {}


def login_redirect(next_path: str = "/") -> RedirectResponse:
    params = {"next": next_path}
    return RedirectResponse(url=f"/login?{urlencode(params)}", status_code=303)


def validate_csrf_or_raise(request: Request, csrf_token: str) -> None:
    if not is_csrf_valid(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


def require_admin_or_redirect(request: Request) -> RedirectResponse | None:
    if current_user_is_admin(request):
        return None
    return RedirectResponse(
        url="/?workspace_view=chat&conversation=new&error=Admin+access+required",
        status_code=303,
    )


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request", "").lower() == "true"


@app.middleware("http")
async def auth_guard_middleware(request: Request, call_next):
    path = request.url.path
    is_static = path.startswith("/static")
    if is_static:
        return await call_next(request)

    session_payload = read_session_cookie_payload(request)
    session_user_id = session_payload.get("user_id")

    with SessionLocal() as session:
        users_exist = has_bootstrapped_users(session)
        user = None
        if isinstance(session_user_id, int):
            candidate = crud.get_user(session, session_user_id)
            if candidate and candidate.is_active:
                user = candidate

    public_paths = {"/login"}
    if path in public_paths:
        if users_exist and user and request.method.upper() == "GET":
            return RedirectResponse(url="/", status_code=303)
        return await call_next(request)

    if not users_exist:
        return RedirectResponse(url="/login", status_code=303)

    if not user:
        return login_redirect(path)
    return await call_next(request)


def parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return int(stripped)


def resolve_default_storage_template_id(session: Session) -> int:
    storage_templates = crud.list_storage_templates(session)
    if not storage_templates:
        raise ValueError("No storage templates are configured")
    default_template = next((item for item in storage_templates if item.name == "default"), None)
    return (default_template or storage_templates[0]).id


def validate_profile_upscale_model(value: str) -> str | None:
    """Validate and return a local upscale model name, or ``None`` if blank."""
    candidate = (value or "").strip()
    if not candidate:
        return None
    local_models = set(upscale_service.list_available_models())
    if not local_models:
        raise ValueError("No local upscale models available. Please place a model in UPSCALER_MODEL_DIR first.")
    if candidate not in local_models:
        raise ValueError("Selected upscaling model is not available locally")
    return candidate


def validate_profile_upscale_provider(value: str) -> str | None:
    """Validate and return an upscale provider name, or ``None`` if no upscaling."""
    candidate = (value or "").strip().lower()
    if not candidate or candidate == "__none__":
        return None
    if candidate not in {"local", "fal"}:
        raise ValueError(f"Unknown upscale provider: {candidate!r}")
    return candidate


def normalize_fal_model_identifier(value: str) -> str:
    """Return a normalized FAL model identifier string."""
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError("FAL model identifier is required")
    if len(normalized) > MAX_FAL_MODEL_IDENTIFIER_LENGTH:
        raise ValueError(
            f"FAL model identifier must be at most {MAX_FAL_MODEL_IDENTIFIER_LENGTH} characters"
        )
    return normalized


def parse_fal_model_params_json(value: str) -> dict[str, Any]:
    """Parse FAL model parameters from JSON text into a dictionary."""
    raw = (value or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"FAL model params must be valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("FAL model params JSON must be an object")
    return parsed


def parse_generic_params_json(value: str) -> dict[str, Any]:
    """Parse generic model parameters from JSON text into a dictionary."""
    raw = (value or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Extra params must be valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Extra params JSON must be an object")
    return parsed


def parse_profile_upscale_choice(
    session: Session,
    value: str,
) -> tuple[str | None, str | None, int | None]:
    """Resolve a profile upscale selection into provider, model identifier, and FAL model ID."""
    choice = (value or "").strip()
    if not choice or choice == "__none__":
        return None, None, None
    if choice == "fal":
        return "fal", None, None
    if choice.startswith("local:"):
        local_model = validate_profile_upscale_model(choice.split(":", 1)[1])
        return "local", local_model, None
    if choice.startswith("falm:") or choice.startswith("topaz:"):
        fal_model_id = parse_optional_int(choice.split(":", 1)[1])
        if fal_model_id is None or fal_model_id <= 0:
            raise ValueError("Selected FAL model is invalid")
        fal_model = crud.get_topaz_upscale_model(session, fal_model_id)
        if not fal_model:
            raise ValueError("Selected FAL model is not available")
        return "fal", fal_model.model_identifier, fal_model.id
    raise ValueError("Unknown upscale option")


def apply_openrouter_image_config(
    *,
    params_json: dict[str, Any],
    provider: str,
    aspect_ratio: str,
    image_size: str,
    allow_clear: bool = True,
) -> dict[str, Any]:
    merged = copy.deepcopy(params_json or {})
    provider_value = (provider or "").strip().lower()
    image_config_raw = merged.get("image_config")
    image_config = (
        copy.deepcopy(image_config_raw) if isinstance(image_config_raw, dict) else {}
    )

    if provider_value != "openrouter":
        image_config.pop("aspect_ratio", None)
        image_config.pop("image_size", None)
        if image_config:
            merged["image_config"] = image_config
        else:
            merged.pop("image_config", None)
        return merged

    ratio_value = (aspect_ratio or "").strip()
    image_size_value = (image_size or "").strip().upper()

    if ratio_value and ratio_value not in OPENROUTER_ALLOWED_ASPECT_RATIOS:
        raise ValueError("Invalid OpenRouter aspect ratio selected")
    if image_size_value and image_size_value not in OPENROUTER_ALLOWED_IMAGE_SIZES:
        raise ValueError("Invalid OpenRouter image size selected")

    if ratio_value:
        image_config["aspect_ratio"] = ratio_value
    elif allow_clear:
        image_config.pop("aspect_ratio", None)

    if image_size_value:
        image_config["image_size"] = image_size_value
    elif allow_clear:
        image_config.pop("image_size", None)

    if image_config:
        merged["image_config"] = image_config
    else:
        merged.pop("image_config", None)
    return merged


def apply_fal_image_config(
    *,
    params_json: dict[str, Any],
    provider: str,
    fal_aspect_ratio: str,
    fal_resolution: str,
    allow_clear: bool = True,
) -> dict[str, Any]:
    """Return params merged with validated FAL ratio/resolution settings."""
    merged = copy.deepcopy(params_json or {})
    provider_value = (provider or "").strip().lower()

    if provider_value != "fal":
        merged.pop("fal_aspect_ratio", None)
        merged.pop("fal_resolution", None)
        return merged

    ratio_value = (fal_aspect_ratio or "").strip()
    resolution_value = (fal_resolution or "").strip().upper()

    if not ratio_value:
        legacy_size = str(merged.get("fal_image_size") or "").strip()
        ratio_value = FAL_IMAGE_SIZE_TO_ASPECT_RATIO.get(legacy_size, "")

    if ratio_value and ratio_value not in FAL_ALLOWED_ASPECT_RATIOS:
        raise ValueError("Invalid FAL aspect ratio selected")
    if resolution_value and resolution_value not in FAL_ALLOWED_RESOLUTIONS:
        raise ValueError("Invalid FAL resolution selected")

    if ratio_value:
        merged["fal_aspect_ratio"] = ratio_value
    elif allow_clear:
        merged.pop("fal_aspect_ratio", None)

    if resolution_value:
        merged["fal_resolution"] = resolution_value
    elif allow_clear:
        merged.pop("fal_resolution", None)

    # Remove legacy key after migrating to explicit ratio/resolution.
    merged.pop("fal_image_size", None)
    return merged


def normalize_thumb_size(value: str | None) -> str:
    candidate = (value or "md").strip().lower()
    if candidate in {"sm", "md", "lg"}:
        return candidate
    return "md"


def normalize_min_rating(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 0:
        return 0
    if value > 5:
        return 5
    return value


def normalize_time_preset(value: str | None) -> str:
    candidate = (value or "today").strip().lower()
    aliases = {
        "this_week": "last_7_days",
        "this_month": "last_30_days",
    }
    candidate = aliases.get(candidate, candidate)
    if candidate in {
        "today",
        "last_7_days",
        "last_30_days",
        "last_60_days",
        "last_120_days",
        "last_year",
        "older",
        "custom",
    }:
        return candidate
    return "today"


def parse_optional_date(value: str | None) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Invalid date format; use YYYY-MM-DD") from exc


def build_created_at_bounds(
    *,
    time_preset: str,
    from_date: date | None,
    to_date: date | None,
) -> tuple[datetime | None, datetime | None]:
    now = datetime.now()

    # Custom date range always wins over preset when at least one bound is provided.
    if from_date is not None or to_date is not None:
        start = (
            datetime.combine(from_date, datetime.min.time())
            if from_date is not None
            else None
        )
        end = (
            datetime.combine(to_date, datetime.max.time())
            if to_date is not None
            else None
        )
        return start, end

    if time_preset == "custom":
        return None, None
    if time_preset == "last_7_days":
        return now - timedelta(days=7), now
    if time_preset == "last_30_days":
        return now - timedelta(days=30), now
    if time_preset == "last_60_days":
        return now - timedelta(days=60), now
    if time_preset == "last_120_days":
        return now - timedelta(days=120), now
    if time_preset == "last_year":
        return now - timedelta(days=365), now
    if time_preset == "older":
        return None, now - timedelta(days=365)

    return now - timedelta(days=1), now


def generation_session_token(generation: Generation) -> str:
    snapshot = generation.request_snapshot_json or {}
    raw_token = snapshot.get("chat_session_id")
    if isinstance(raw_token, str):
        token = raw_token.strip()
        if token:
            return token
    if generation.profile_id is not None:
        return f"profile:{generation.profile_id}"
    return f"profile-name:{slugify(generation.profile_name, max_length=64, fallback='unknown')}"


def build_chat_session_token() -> str:
    return f"session:{uuid.uuid4().hex[:12]}"


def format_session_timestamp(value: datetime | None) -> str:
    if not value or value == datetime.min:
        return ""
    return value.strftime("%d.%m.%Y %H:%M")


def format_session_age(created_at: datetime | None) -> str:
    """Format the age of a session as Xh, Xd, Xw, or Xm."""
    if not created_at or created_at == datetime.min:
        return ""

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    delta = now - created_at

    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        total_seconds = 0

    hours = total_seconds // 3600
    days = total_seconds // 86400
    weeks = days // 7
    months = days // 30

    # Today: show hours (>= 1 hour)
    if created_at >= today_start:
        if hours >= 1:
            return f"{hours}h"
        else:
            return "0h"
    # Yesterday: show hours or 1d
    elif created_at >= yesterday_start:
        if hours >= 1:
            return f"{hours}h"
        else:
            return "1d"
    # Less than 7 days
    elif days < 7:
        return f"{days}d"
    # Less than 30 days
    elif weeks < 4:
        return f"{weeks}w"
    # Older
    else:
        return f"{months}m"


def get_session_time_category(created_at: datetime | None) -> str:
    """Categorize a session by recency for grouped rendering in the sidebar."""
    if not created_at or created_at == datetime.min:
        return "older"

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = today_start - timedelta(days=7)
    thirty_days_ago = today_start - timedelta(days=30)
    sixty_days_ago = today_start - timedelta(days=60)
    onehundredtwenty_days_ago = today_start - timedelta(days=120)
    one_year_ago = today_start - timedelta(days=365)

    if created_at >= today_start:
        return "today"
    if created_at >= seven_days_ago:
        return "last7days"
    if created_at >= thirty_days_ago:
        return "last30days"
    if created_at >= sixty_days_ago:
        return "last60days"
    if created_at >= onehundredtwenty_days_ago:
        return "last120days"
    if created_at >= one_year_ago:
        return "lastyear"
    return "older"


def get_session_time_category_label(value: str) -> str:
    labels = {
        "today": "Today",
        "last7days": "Last 7 days",
        "last30days": "Last 30 days",
        "last60days": "Last 60 days",
        "last120days": "Last 120 days",
        "lastyear": "Last year",
        "older": "Older",
    }
    return labels.get(value, "Older")


SESSION_MAX_DAYS: int | None = None
SESSION_PAGE_SIZE = 10


def build_session_items(
    session: Session,
    offset: int = 0,
    limit: int = SESSION_PAGE_SIZE,
    max_days: int | None = SESSION_MAX_DAYS,
) -> tuple[list[dict[str, Any]], bool]:
    """
    Build session items with pagination and time categorization.
    Returns (session_items, has_more).
    """
    query = select(Generation).options(selectinload(Generation.assets))
    if max_days is not None:
        now = datetime.now(UTC)
        cutoff_date = now - timedelta(days=max_days)
        query = query.where(Generation.created_at >= cutoff_date)
    query = query.order_by(Generation.created_at.desc(), Generation.id.desc())

    # First, get all generations to build session index
    all_generations = list(session.scalars(query).all())
    hidden_tokens: set[str] = set()
    for generation in all_generations:
        token = generation_session_token(generation)
        if generation_chat_hidden(generation) or generation_chat_deleted(generation) or generation_session_archived(generation):
            hidden_tokens.add(token)

    # Build session index
    session_index: dict[str, dict[str, Any]] = {}
    for generation in all_generations:
        token = generation_session_token(generation)
        if token in hidden_tokens:
            continue
        custom_title = generation_session_title(generation)
        created_at = generation.created_at or datetime.min
        item = session_index.get(token)
        if not item:
            item = {
                "token": token,
                "profile_label": generation.profile_name or f"Session #{generation.id}",
                "custom_title": custom_title,
                "latest_generation_id": generation.id,
                "started_at": created_at,
                "latest_created_at": created_at,
                "latest_status": generation.status,
            }
            session_index[token] = item
        if created_at >= item["latest_created_at"]:
            item["latest_generation_id"] = generation.id
            item["latest_created_at"] = created_at
            item["latest_status"] = generation.status
            if custom_title:
                item["custom_title"] = custom_title

    # Get all unique sessions sorted by latest_created_at
    all_sessions = sorted(
        session_index.values(),
        key=lambda item: (
            item.get("latest_created_at") or datetime.min,
            item.get("latest_generation_id") or 0,
        ),
        reverse=True,
    )

    # Check if there are more sessions beyond the requested range
    has_more = len(all_sessions) > offset + limit

    # Get the requested slice
    session_slice = all_sessions[offset:offset + limit]

    # Build session items with time categories
    session_items = []
    for item in session_slice:
        started_at = item.get("started_at")
        latest_at = item.get("latest_created_at")
        started_label = format_session_timestamp(started_at)
        latest_label = format_session_timestamp(latest_at)
        base_label = str(item.get("profile_label") or "Session")
        custom_title = str(item.get("custom_title") or "").strip()

        session_items.append({
            "token": item["token"],
            "label": custom_title or base_label,
            "subtitle": latest_label or started_label,
            "age": format_session_age(latest_at),
            "time_category": get_session_time_category(latest_at),
            "time_category_label": get_session_time_category_label(get_session_time_category(latest_at)),
            "latest_created_at": latest_at,
        })

    return session_items, has_more


def generation_session_title(generation: Generation) -> str:
    snapshot = generation.request_snapshot_json or {}
    raw_title = snapshot.get("chat_session_title")
    if isinstance(raw_title, str):
        return raw_title.strip()
    return ""


def generation_chat_hidden(generation: Generation) -> bool:
    snapshot = generation.request_snapshot_json or {}
    return bool(snapshot.get("chat_hidden"))


def generation_session_archived(generation: Generation) -> bool:
    snapshot = generation.request_snapshot_json or {}
    return bool(snapshot.get("chat_archived"))


def generation_chat_deleted(generation: Generation) -> bool:
    snapshot = generation.request_snapshot_json or {}
    return bool(snapshot.get("chat_deleted"))


def list_generations_for_session_token(
    db: Session, session_token: str
) -> list[Generation]:
    token = (session_token or "").strip()
    if not token or token in {"all", "new"}:
        return []
    candidates = list(
        db.scalars(
            select(Generation).order_by(Generation.created_at.asc(), Generation.id.asc())
        ).all()
    )
    return [item for item in candidates if generation_session_token(item) == token]


def generate_workspace_redirect(
    *,
    conversation: str,
    workspace_view: str = "chat",
    error: str | None = None,
) -> RedirectResponse:
    view = (workspace_view or "chat").strip().lower()
    if view not in {"chat", "profiles", "gallery", "admin"}:
        view = "chat"
    params: dict[str, str] = {"workspace_view": view, "conversation": conversation}
    if error:
        params["error"] = error
    return RedirectResponse(url=f"/?{urlencode(params)}", status_code=303)


def safe_gallery_return_to(value: str | None) -> str:
    candidate = (value or "/gallery").strip()
    if candidate.startswith("/gallery"):
        return candidate
    return "/gallery"


def gallery_redirect(
    return_to: str | None = "/gallery",
    *,
    message: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    target = safe_gallery_return_to(return_to)
    params: dict[str, str] = {}
    if message:
        params["message"] = message
    if error:
        params["error"] = error
    if params:
        sep = "&" if "?" in target else "?"
        target = f"{target}{sep}{urlencode(params)}"
    return RedirectResponse(url=target, status_code=303)


def normalize_category_ids(values: list[int]) -> list[int]:
    return sorted({value for value in values if value > 0})


def normalize_category_name(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError("Category name is required")
    if len(normalized) > MAX_CATEGORY_NAME_LENGTH:
        raise ValueError(
            f"Category name must be at most {MAX_CATEGORY_NAME_LENGTH} characters"
        )
    return normalized


def normalize_profile_name(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError("Profile name is required")
    if len(normalized) > MAX_PROFILE_NAME_LENGTH:
        raise ValueError(
            f"Profile name must be at most {MAX_PROFILE_NAME_LENGTH} characters"
        )
    return normalized


def normalize_model_config_name(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError("Model name is required")
    if len(normalized) > MAX_MODEL_CONFIG_NAME_LENGTH:
        raise ValueError(
            f"Model name must be at most {MAX_MODEL_CONFIG_NAME_LENGTH} characters"
        )
    return normalized


def normalize_admin_section(value: str | None) -> str:
    candidate = (value or "models").strip().lower()
    if candidate in ADMIN_USER_SECTIONS:
        return candidate
    return "models"


def normalize_user_role(value: str) -> str:
    role = (value or "").strip().lower()
    if role in {ADMIN_ROLE, USER_ROLE}:
        return role
    raise ValueError("Invalid role")


def admin_redirect(
    section: str,
    *,
    message: str | None = None,
    error: str | None = None,
    extra_params: dict[str, str | int | bool | None] | None = None,
) -> RedirectResponse:
    params: dict[str, str] = {"section": normalize_admin_section(section)}
    if message:
        params["message"] = message
    if error:
        params["error"] = error
    if extra_params:
        for key, value in extra_params.items():
            if value is None:
                continue
            params[key] = str(value)
    return RedirectResponse(url=f"/admin?{urlencode(params)}", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    next_url: str | None = Query(default="/", alias="next"),
    error: str | None = Query(default=None),
    message: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    users_exist = has_bootstrapped_users(session)
    token = ensure_csrf_token(request)
    next_path = (next_url or "/").strip() or "/"
    if not next_path.startswith("/"):
        next_path = "/"

    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "csrf_token": token,
            "users_exist": users_exist,
            "next": next_path,
            "error": error or "",
            "message": message or "",
            "hide_header": True,
        },
    )


@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    next_url: str = Form(default="/", alias="next"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    users_exist = has_bootstrapped_users(session)
    username_value = (username or "").strip()
    next_path = (next_url or "/").strip() or "/"
    if not next_path.startswith("/"):
        next_path = "/"

    if not users_exist:
        if len(username_value) < 3:
            return RedirectResponse(
                url="/login?error=Username+must+be+at+least+3+characters",
                status_code=303,
            )
        try:
            password_hash = auth_service.hash_password(password)
            user = crud.create_user(
                session,
                username=username_value,
                password_hash=password_hash,
                role=ADMIN_ROLE,
                is_active=True,
            )
            start_auth_session(request, user)
            return RedirectResponse(url="/", status_code=303)
        except (ValueError, IntegrityError) as exc:
            return RedirectResponse(url=f"/login?error={str(exc)}", status_code=303)

    user = crud.get_user_by_username(session, username_value)
    if not user or not user.is_active or not auth_service.verify_password(password, user.password_hash):
        params = {"next": next_path, "error": "Invalid credentials"}
        return RedirectResponse(url=f"/login?{urlencode(params)}", status_code=303)

    start_auth_session(request, user)
    return RedirectResponse(url=next_path, status_code=303)


@app.get("/logout")
def logout(request: Request) -> RedirectResponse:
    clear_auth_session(request)
    return RedirectResponse(url="/login?message=Logged+out", status_code=303)


@app.get("/", response_class=HTMLResponse)
def generate_page(
    request: Request,
    error: str | None = Query(default=None),
    conversation: str | None = Query(default=None),
    workspace_view: str | None = Query(default="chat"),
    session_offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    active_workspace_view = (workspace_view or "chat").strip().lower()
    if active_workspace_view not in {"chat", "profiles", "gallery", "admin"}:
        active_workspace_view = "chat"
    if active_workspace_view == "admin" and not current_user_is_admin(request):
        active_workspace_view = "chat"

    # Build full session list once; we derive the rendered page slice from it.
    all_sessions, _ = build_session_items(
        session,
        offset=0,
        limit=100000,
        max_days=SESSION_MAX_DAYS,
    )
    all_session_tokens = {item["token"] for item in all_sessions}

    active_conversation = (conversation or "").strip()
    if active_conversation:
        if active_conversation not in {"all", "new"} and active_conversation not in all_session_tokens:
            active_conversation = ""
    if not active_conversation:
        active_conversation = all_sessions[0]["token"] if all_sessions else "new"

    effective_session_offset = session_offset
    if active_conversation not in {"", "all", "new"}:
        active_index = next(
            (idx for idx, item in enumerate(all_sessions) if item["token"] == active_conversation),
            -1,
        )
        if active_index >= 0:
            effective_session_offset = (active_index // SESSION_PAGE_SIZE) * SESSION_PAGE_SIZE

    session_items = all_sessions[
        effective_session_offset:effective_session_offset + SESSION_PAGE_SIZE
    ]
    session_has_more = len(all_sessions) > effective_session_offset + SESSION_PAGE_SIZE

    # Keep heavy DB queries chat-only so sidebar workspace switches stay responsive.
    profiles = []
    dimension_presets = []
    enhancement_ready = False
    upscale_ready = False
    upscale_models: list[str] = []
    fal_upscale_models: list[Any] = []
    fal_upscale_ready = False
    last_profile_id = None
    last_thumb_size = "md"
    conversation_generations = []

    if active_workspace_view == "chat":
        profiles = crud.list_profiles(session)
        dimension_presets = crud.list_dimension_presets(session)
        enhancement_config = crud.get_enhancement_config(session)
        enhancement_ready = bool(enhancement_config and enhancement_config.api_key_encrypted)
        upscale_ready = upscale_service.is_available()
        upscale_models = upscale_service.list_available_models()
        fal_upscale_models = crud.list_topaz_upscale_models(
            session, enabled_only=True
        )
        fal_upscale_ready = bool(model_config_service.get_default_api_key("fal"))

        if active_conversation not in {"all", "new"}:
            chat_session_prefs = crud.get_chat_session(session, active_conversation)
            if chat_session_prefs:
                last_profile_id = chat_session_prefs.last_profile_id
                last_thumb_size = chat_session_prefs.last_thumb_size or "md"

        if active_conversation == "all":
            recent_generations = list(
                session.scalars(
                    select(Generation)
                    .options(selectinload(Generation.assets))
                    .order_by(Generation.created_at.desc(), Generation.id.desc())
                    .limit(250)
                ).all()
            )
            recent_generations.reverse()
            conversation_generations = [
                generation
                for generation in recent_generations
                if not generation_chat_hidden(generation)
                and not generation_session_archived(generation)
                and not generation_chat_deleted(generation)
            ]
        elif active_conversation == "new":
            conversation_generations = []
        else:
            conversation_generations = [
                generation
                for generation in list_generations_for_session_token(session, active_conversation)
                if not generation_chat_hidden(generation)
                and not generation_session_archived(generation)
                and not generation_chat_deleted(generation)
            ]

    return templates.TemplateResponse(
        request,
        "generate.html",
        {
            "request": request,
            "profiles": profiles,
            "dimension_presets": dimension_presets,
            "conversation_generations": conversation_generations,
            "session_items": session_items,
            "session_has_more": session_has_more,
            "session_offset": effective_session_offset,
            "active_conversation": active_conversation,
            "workspace_view": active_workspace_view,
            "hide_footer": True,
            "hide_header": True,
            "enhancement_ready": enhancement_ready,
            "upscale_ready": upscale_ready,
            "upscale_models": upscale_models,
            "fal_upscale_models": fal_upscale_models,
            "topaz_upscale_models": fal_upscale_models,
            "fal_upscale_ready": fal_upscale_ready,
            "error": error or "",
            "last_profile_id": last_profile_id,
            "last_thumb_size": last_thumb_size,
        },
    )


@app.post("/generate", response_class=HTMLResponse)
def generate_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    prompt_user: str = Form(...),
    profile_id: int = Form(...),
    conversation: str = Form(default=""),
    width: str = Form(default=""),
    height: str = Form(default=""),
    n_images: str = Form(default=""),
    seed: str = Form(default=""),
    aspect_ratio: str = Form(default=""),
    image_size: str = Form(default=""),
    fal_aspect_ratio: str = Form(default=""),
    fal_resolution: str = Form(default=""),
    fal_image_size: str = Form(default=""),
    upscale_model: str = Form(default="__profile__"),
    upscale_provider_override: str = Form(default="__profile__"),
    input_images: list[UploadFile] = File(default=[]),
    input_image_asset_id: str = Form(default=""),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    validate_csrf_or_raise(request, csrf_token)
    profile = crud.get_profile(session, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    try:
        overrides: dict[str, Any] = {}
        conversation_value = (conversation or "").strip()
        if not conversation_value or conversation_value in {"new", "all"}:
            resolved_conversation = build_chat_session_token()
        else:
            resolved_conversation = conversation_value
        overrides["chat_session_id"] = resolved_conversation

        encoded_images: list[dict[str, str]] = []

        # Handle input_image_asset_id (from asset detail page)
        asset_id_value = parse_optional_int(input_image_asset_id)
        if asset_id_value is not None:
            asset = session.scalar(
                select(Asset)
                .options(selectinload(Asset.generation))
                .where(Asset.id == asset_id_value)
            )
            if asset and asset.generation:
                absolute_path = generation_service.asset_absolute_path(asset, which="file")
                if absolute_path.exists():
                    with open(absolute_path, "rb") as f:
                        image_data = f.read()
                    encoded_images.append(
                        {
                            "name": f"asset_{asset.id}",
                            "mime": asset.mime,
                            "b64": base64.b64encode(image_data).decode("ascii"),
                        }
                    )

        # Handle uploaded input_images
        if input_images:
            if len(input_images) + len(encoded_images) > MAX_INPUT_IMAGES:
                raise ValueError(f"Upload up to {MAX_INPUT_IMAGES} input images.")
            total_upload_bytes = 0
            for upload in input_images:
                content_type = (upload.content_type or "").lower()
                if not content_type.startswith("image/"):
                    raise ValueError("Input images must be valid image files.")
                data = upload.file.read()
                if not data:
                    continue
                total_upload_bytes += len(data)
                if MAX_UPLOAD_BYTES is not None and total_upload_bytes > MAX_UPLOAD_BYTES:
                    raise ValueError(
                        f"Upload exceeds the {settings.max_upload_size_mb} MB size limit."
                    )
                encoded_images.append(
                    {
                        "name": upload.filename or "input",
                        "mime": content_type,
                        "b64": base64.b64encode(data).decode("ascii"),
                    }
                )

        if encoded_images:
            overrides["input_images"] = encoded_images

        provider_value = str(profile.provider or "").strip().lower()

        # Apply OpenRouter-specific, FAL-specific, or standard dimension overrides
        if provider_value == "openrouter":
            # For OpenRouter: process aspect_ratio and image_size
            params_json_copy = dict(profile.params_json or {})
            params_json_with_overrides = apply_openrouter_image_config(
                params_json=params_json_copy,
                provider=provider_value,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                allow_clear=False,
            )
            overrides["params_json"] = params_json_with_overrides
        elif provider_value == "fal":
            # For FAL: process explicit aspect ratio + resolution settings.
            params_json_copy = dict(profile.params_json or {})
            if (fal_image_size or "").strip() and not (fal_aspect_ratio or "").strip():
                # Backward-compatibility for older forms still submitting fal_image_size.
                params_json_copy["fal_image_size"] = (fal_image_size or "").strip()
            params_json_with_overrides = apply_fal_image_config(
                params_json=params_json_copy,
                provider=provider_value,
                fal_aspect_ratio=fal_aspect_ratio,
                fal_resolution=fal_resolution,
                allow_clear=False,
            )
            overrides["params_json"] = params_json_with_overrides
        else:
            # For other providers: use width/height
            width_value = parse_optional_int(width)
            if width_value is not None:
                if width_value <= 0:
                    raise ValueError("Width must be greater than 0")
                overrides["width"] = width_value

            height_value = parse_optional_int(height)
            if height_value is not None:
                if height_value <= 0:
                    raise ValueError("Height must be greater than 0")
                overrides["height"] = height_value

        n_images_value = parse_optional_int(n_images)
        if n_images_value is not None:
            overrides["n_images"] = max(1, min(8, n_images_value))

        seed_value = parse_optional_int(seed)
        if seed_value is not None:
            overrides["seed"] = seed_value

        # Handle upscale provider/model overrides
        provider_choice = (upscale_provider_override or "__profile__").strip()
        upscale_choice = (upscale_model or "__profile__").strip()

        if provider_choice == "__none__" or upscale_choice == "__none__":
            # Explicit "no upscaling" override
            overrides["upscale_provider"] = None
            overrides["upscale_model"] = None
            overrides["upscale_topaz_model_id"] = None
        elif provider_choice == "__profile__" and upscale_choice == "__profile__":
            # Use profile settings — validate that the profile's upscale config is still valid
            profile_upscale_provider = str(profile.upscale_provider or "").strip().lower()
            profile_upscale_model = str(profile.upscale_model or "").strip()
            if profile_upscale_provider == "local" and profile_upscale_model:
                if not upscale_service.is_available():
                    raise ValueError("Local upscaler is not configured on this server")
                available = upscale_service.list_available_models()
                if available and profile_upscale_model not in available:
                    raise ValueError("Profile upscale model is not available")
            elif profile_upscale_provider == "fal":
                profile_fal_model_id = getattr(profile, "upscale_topaz_model_id", None)
                if profile_fal_model_id is not None:
                    fal_model = crud.get_topaz_upscale_model(session, int(profile_fal_model_id))
                    if not fal_model:
                        raise ValueError("Profile FAL model is not available")
        elif provider_choice == "fal" or (provider_choice == "__profile__" and upscale_choice == "fal"):
            # FAL.ai upscale override
            fal_key = model_config_service.get_default_api_key("fal")
            if not fal_key:
                raise ValueError("FAL.ai API key is not configured. Set it in Admin → Upscaling.")
            overrides["upscale_provider"] = "fal"
            overrides["upscale_model"] = None
            overrides["upscale_topaz_model_id"] = None
        elif upscale_choice.startswith("falm:") or upscale_choice.startswith("topaz:"):
            fal_key = model_config_service.get_default_api_key("fal")
            if not fal_key:
                raise ValueError("FAL.ai API key is not configured. Set it in Admin → Upscaling.")
            fal_model_id = parse_optional_int(upscale_choice.split(":", 1)[1])
            if fal_model_id is None or fal_model_id <= 0:
                raise ValueError("Selected FAL model is invalid")
            fal_model = crud.get_topaz_upscale_model(session, fal_model_id)
            if not fal_model or not fal_model.is_enabled:
                raise ValueError("Selected FAL model is not available")
            overrides["upscale_provider"] = "fal"
            overrides["upscale_model"] = fal_model.model_identifier
            overrides["upscale_topaz_model_id"] = fal_model.id
        elif upscale_choice.startswith("local:"):
            local_choice = upscale_choice.split(":", 1)[1]
            if not upscale_service.is_available():
                raise ValueError("Local upscaler is not configured on this server")
            available = upscale_service.list_available_models()
            if available and local_choice not in available:
                raise ValueError("Selected upscale model is not available")
            overrides["upscale_provider"] = "local"
            overrides["upscale_model"] = local_choice
            overrides["upscale_topaz_model_id"] = None
        elif upscale_choice and upscale_choice not in {"__profile__", "__none__"}:
            # Local model override
            if not upscale_service.is_available():
                raise ValueError("Local upscaler is not configured on this server")
            available = upscale_service.list_available_models()
            if available and upscale_choice not in available:
                raise ValueError("Selected upscale model is not available")
            overrides["upscale_provider"] = "local"
            overrides["upscale_model"] = upscale_choice
            overrides["upscale_topaz_model_id"] = None

        generation = generation_service.create_generation_from_profile(
            session,
            profile,
            prompt_user,
            overrides=overrides or None,
        )
        generation_service.enqueue(background_tasks, generation.id)
    except ValueError as exc:
        if is_htmx(request):
            return templates.TemplateResponse(
                request,
                "fragments/chat_error_item.html",
                {
                    "request": request,
                    "error_message": str(exc),
                },
            )
        params: dict[str, str] = {"error": str(exc)}
        conversation_value = (conversation or "").strip()
        if conversation_value and conversation_value not in {"new", "all"}:
            params["conversation"] = conversation_value
        return RedirectResponse(url=f"/?{urlencode(params)}", status_code=303)

    if is_htmx(request):
        conversation_value = (conversation or "").strip()
        if not conversation_value or conversation_value in {"new", "all"}:
            redirect_target = "/?" + urlencode(
                {
                    "conversation": resolved_conversation,
                    "workspace_view": "chat",
                }
            )
            response = HTMLResponse(content="")
            response.headers["HX-Redirect"] = redirect_target
            return response
        return templates.TemplateResponse(
            request,
            "fragments/chat_generation_item.html",
            {
                "request": request,
                "generation": generation,
                "assets": [],
            },
        )
    # Redirect to chat interface with the original session conversation
    return RedirectResponse(
        url=f"/?{urlencode({'workspace_view': 'chat', 'conversation': resolved_conversation})}",
        status_code=303,
    )


@app.post("/sessions/rename")
def rename_chat_session(
    request: Request,
    session_token: str = Form(...),
    title: str = Form(...),
    active_conversation: str = Form(default=""),
    workspace_view: str = Form(default="chat"),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    token = (session_token or "").strip()
    if not token or token in {"all", "new"}:
        return generate_workspace_redirect(
            conversation=active_conversation or "new",
            workspace_view=workspace_view,
            error="Invalid session token",
        )

    new_title = (title or "").strip()
    if not new_title:
        return generate_workspace_redirect(
            conversation=active_conversation or token,
            workspace_view=workspace_view,
            error="Session title must not be empty",
        )

    generations = list_generations_for_session_token(session, token)
    if not generations:
        return generate_workspace_redirect(
            conversation=active_conversation or "new",
            workspace_view=workspace_view,
            error="Session not found",
        )

    for generation in generations:
        snapshot = dict(generation.request_snapshot_json or {})
        snapshot["chat_session_title"] = new_title
        generation.request_snapshot_json = snapshot
        session.add(generation)
    session.commit()

    target_conversation = (active_conversation or "").strip() or token
    return generate_workspace_redirect(
        conversation=target_conversation,
        workspace_view=workspace_view,
    )


@app.post("/sessions/delete")
def delete_chat_session(
    request: Request,
    session_token: str = Form(...),
    active_conversation: str = Form(default=""),
    workspace_view: str = Form(default="chat"),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    token = (session_token or "").strip()
    if not token or token in {"all", "new"}:
        return generate_workspace_redirect(
            conversation=active_conversation or "new",
            workspace_view=workspace_view,
            error="Invalid session token",
        )

    generations = list_generations_for_session_token(session, token)
    if not generations:
        return generate_workspace_redirect(
            conversation=active_conversation or "new",
            workspace_view=workspace_view,
            error="Session not found",
        )

    for generation in generations:
        snapshot = dict(generation.request_snapshot_json or {})
        snapshot["chat_hidden"] = True
        snapshot["chat_deleted"] = True
        snapshot.pop("chat_archived", None)
        snapshot.pop("chat_session_id", None)
        snapshot.pop("chat_session_title", None)
        generation.request_snapshot_json = snapshot
        session.add(generation)
    session.commit()

    requested_active = (active_conversation or "").strip()
    next_conversation = "new" if requested_active == token else (requested_active or "new")
    return generate_workspace_redirect(
        conversation=next_conversation,
        workspace_view=workspace_view,
    )


@app.post("/sessions/archive")
def archive_chat_session(
    request: Request,
    session_token: str = Form(...),
    active_conversation: str = Form(default=""),
    workspace_view: str = Form(default="chat"),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    token = (session_token or "").strip()
    if not token or token in {"all", "new"}:
        return generate_workspace_redirect(
            conversation=active_conversation or "new",
            workspace_view=workspace_view,
            error="Invalid session token",
        )

    generations = list_generations_for_session_token(session, token)
    if not generations:
        return generate_workspace_redirect(
            conversation=active_conversation or "new",
            workspace_view=workspace_view,
            error="Session not found",
        )

    for generation in generations:
        snapshot = dict(generation.request_snapshot_json or {})
        snapshot["chat_archived"] = True
        snapshot.pop("chat_deleted", None)
        generation.request_snapshot_json = snapshot
        session.add(generation)
    session.commit()

    requested_active = (active_conversation or "").strip()
    next_conversation = "new" if requested_active == token else (requested_active or "new")
    return generate_workspace_redirect(
        conversation=next_conversation,
        workspace_view=workspace_view,
    )


@app.get("/jobs/{generation_id}", response_class=HTMLResponse)
def job_status(
    request: Request,
    generation_id: int,
    view: str = Query(default="default"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    generation = session.scalar(
        select(Generation)
        .options(selectinload(Generation.assets))
        .where(Generation.id == generation_id)
    )
    if not generation:
        raise HTTPException(status_code=404, detail="Job not found")

    assets = sorted(generation.assets, key=lambda item: item.id)
    template_name = (
        "fragments/chat_generation_item.html"
        if view.strip().lower() == "chat"
        else "fragments/job_status.html"
    )
    return templates.TemplateResponse(
        request,
        template_name,
        {
            "request": request,
            "generation": generation,
            "assets": assets,
        },
    )


@app.post("/jobs/{generation_id}/cancel", response_class=HTMLResponse)
def job_cancel(
    request: Request,
    generation_id: int,
    view: str = Query(default="default"),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    validate_csrf_or_raise(request, csrf_token)
    generation = generation_service.cancel_generation(session, generation_id)
    if not generation:
        raise HTTPException(status_code=404, detail="Job not found")

    assets = (
        sorted(generation.assets, key=lambda item: item.id) if generation.assets else []
    )
    if is_htmx(request):
        template_name = (
            "fragments/chat_generation_item.html"
            if view.strip().lower() == "chat"
            else "fragments/job_status.html"
        )
        return templates.TemplateResponse(
            request,
            template_name,
            {
                "request": request,
                "generation": generation,
                "assets": assets,
            },
        )
    return RedirectResponse(url=f"/jobs/{generation.id}", status_code=303)


@app.get("/api/providers/{provider}/models", response_class=JSONResponse)
async def provider_models(provider: str) -> JSONResponse:
    try:
        models = await provider_registry.list_models(provider.strip())
        return JSONResponse({"provider": provider, "models": models, "error": None})
    except ProviderError as exc:
        return JSONResponse({"provider": provider, "models": [], "error": str(exc)})


@app.get("/admin", response_class=HTMLResponse)
def admin_page(
    request: Request,
    section: str | None = Query(default="models"),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
    fal_model_create_open: str | None = Query(default=None),
    fal_model_edit_id: str | None = Query(default=None),
    fal_model_name: str | None = Query(default=None),
    fal_model_identifier: str | None = Query(default=None),
    fal_model_params_json: str | None = Query(default=None),
    fal_model_is_enabled: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    denied = require_admin_or_redirect(request)
    if denied:
        return denied

    model_configs = crud.list_model_configs(session)
    dimension_presets = crud.list_dimension_presets(session)
    categories = crud.list_categories(session)
    users = crud.list_users(session)
    enhancement_config = crud.get_enhancement_config(session)
    encryption_ready = bool((settings.provider_config_key or "").strip())
    active_admin_section = normalize_admin_section(section)

    # Build per-provider API key info for the "API Keys" admin section
    provider_names = provider_registry.provider_names()
    provider_api_key_rows = {row.provider: row for row in crud.list_provider_api_keys(session)}
    provider_api_key_info = [
        {
            "provider": p,
            "has_db_key": p in provider_api_key_rows,
            "has_env_key": model_config_service.has_env_api_key(p),
        }
        for p in provider_names
        if p in model_config_service.PROVIDER_API_KEY_ATTR
    ]

    # Build upscaling info for the "Upscaling" admin section
    fal_api_key_row = provider_api_key_rows.get("fal")
    create_dialog_open = str(fal_model_create_open or "").strip().lower() in {
        "1",
        "true",
        "on",
        "yes",
    }
    try:
        edit_dialog_model_id = parse_optional_int(fal_model_edit_id)
    except ValueError:
        edit_dialog_model_id = None
    if edit_dialog_model_id is not None and edit_dialog_model_id <= 0:
        edit_dialog_model_id = None
    draft_enabled = str(fal_model_is_enabled or "").strip().lower() in {
        "1",
        "true",
        "on",
        "yes",
    }
    upscaling_info = {
        "local_available": upscale_service.is_available(),
        "local_models": upscale_service.list_available_models(),
        "fal_has_db_key": fal_api_key_row is not None,
        "fal_has_env_key": bool(settings.fal_api_key),
        "fal_models": crud.list_topaz_upscale_models(session, enabled_only=False),
        "topaz_models": crud.list_topaz_upscale_models(session, enabled_only=False),
        "fal_model_create_open": create_dialog_open,
        "fal_model_edit_id": edit_dialog_model_id,
        "fal_model_draft_name": fal_model_name or "",
        "fal_model_draft_identifier": fal_model_identifier or "",
        "fal_model_draft_params_json": fal_model_params_json if fal_model_params_json is not None else "{}",
        "fal_model_draft_enabled": draft_enabled,
    }

    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "request": request,
            "model_configs": model_configs,
            "dimension_presets": dimension_presets,
            "categories": categories,
            "enhancement_config": enhancement_config,
            "providers": provider_names,
            "provider_meta": provider_registry.provider_meta(),
            "users": users,
            "error": error or "",
            "message": message or "",
            "encryption_ready": encryption_ready,
            "active_admin_section": active_admin_section,
            "app_copyright_text": APP_COPYRIGHT_TEXT,
            "onboarding_reset_enabled": settings.auth_allow_onboarding_reset,
            "provider_api_key_info": provider_api_key_info,
            "upscaling_info": upscaling_info,
        },
    )


@app.post("/admin/provider-api-keys/{provider}/update")
def admin_update_provider_api_key(
    request: Request,
    provider: str,
    api_key: str = Form(default=""),
    clear_api_key: bool = Form(default=False),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    provider = provider.strip().lower()
    if provider not in provider_registry.provider_names():
        raise HTTPException(status_code=404, detail="Unsupported provider")
    if provider not in model_config_service.PROVIDER_API_KEY_ATTR:
        raise HTTPException(status_code=404, detail="Provider does not support API key configuration")
    try:
        if clear_api_key:
            crud.delete_provider_api_key(session, provider)
        else:
            api_key_value = api_key.strip()
            if api_key_value:
                encrypted = model_config_service.encrypt_api_key(api_key_value)
                crud.upsert_provider_api_key(session, provider, encrypted)
    except ValueError as exc:
        return admin_redirect("apikeys", error=str(exc))
    return admin_redirect("apikeys", message="Saved")


@app.post("/admin/upscaling/fal")
def admin_update_fal_upscale_key(
    request: Request,
    api_key: str = Form(default=""),
    clear_api_key: bool = Form(default=False),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Save or clear the FAL.ai API key used for upscaling."""
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    try:
        if clear_api_key:
            crud.delete_provider_api_key(session, "fal")
        else:
            api_key_value = api_key.strip()
            if api_key_value:
                encrypted = model_config_service.encrypt_api_key(api_key_value)
                crud.upsert_provider_api_key(session, "fal", encrypted)
    except ValueError as exc:
        return admin_redirect("upscaling", error=str(exc))
    return admin_redirect("upscaling", message="Saved")


@app.post("/admin/fal-models")
@app.post("/admin/topaz-models")
def admin_create_topaz_model(
    request: Request,
    name: str = Form(...),
    model_identifier: str = Form(...),
    params_json: str = Form(default="{}"),
    is_enabled: str = Form(default=""),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a named FAL upscale model configuration."""
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    enabled_value = str(is_enabled).strip().lower() in {"1", "true", "on", "yes"}
    try:
        name_value = normalize_model_config_name(name)
        identifier_value = normalize_fal_model_identifier(model_identifier)
        params_value = parse_fal_model_params_json(params_json)
        crud.create_topaz_upscale_model(
            session,
            name=name_value,
            model_identifier=identifier_value,
            params_json=params_value,
            is_enabled=enabled_value,
        )
    except (ValueError, IntegrityError) as exc:
        return admin_redirect(
            "upscaling",
            error=str(exc),
            extra_params={
                "fal_model_create_open": "1",
                "fal_model_name": name,
                "fal_model_identifier": model_identifier,
                "fal_model_params_json": params_json,
                "fal_model_is_enabled": "1" if enabled_value else "0",
            },
        )
    return admin_redirect("upscaling", message="Saved")


@app.post("/admin/fal-models/{topaz_model_id}/update")
@app.post("/admin/topaz-models/{topaz_model_id}/update")
def admin_update_topaz_model(
    request: Request,
    topaz_model_id: int,
    name: str = Form(...),
    model_identifier: str = Form(...),
    params_json: str = Form(default="{}"),
    is_enabled: str = Form(default=""),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Update an existing FAL upscale model configuration."""
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    topaz_model = crud.get_topaz_upscale_model(session, topaz_model_id)
    if not topaz_model:
        raise HTTPException(status_code=404, detail="FAL model not found")
    enabled_value = str(is_enabled).strip().lower() in {"1", "true", "on", "yes"}
    try:
        name_value = normalize_model_config_name(name)
        identifier_value = normalize_fal_model_identifier(model_identifier)
        params_value = parse_fal_model_params_json(params_json)
        crud.update_topaz_upscale_model(
            session,
            topaz_model,
            name=name_value,
            model_identifier=identifier_value,
            params_json=params_value,
            is_enabled=enabled_value,
        )
    except (ValueError, IntegrityError) as exc:
        return admin_redirect(
            "upscaling",
            error=str(exc),
            extra_params={
                "fal_model_edit_id": topaz_model.id,
                "fal_model_name": name,
                "fal_model_identifier": model_identifier,
                "fal_model_params_json": params_json,
                "fal_model_is_enabled": "1" if enabled_value else "0",
            },
        )
    return admin_redirect("upscaling", message="Saved")


@app.post("/admin/fal-models/{topaz_model_id}/delete")
@app.post("/admin/topaz-models/{topaz_model_id}/delete")
def admin_delete_topaz_model(
    request: Request,
    topaz_model_id: int,
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Delete a FAL upscale model configuration."""
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    topaz_model = crud.get_topaz_upscale_model(session, topaz_model_id)
    if not topaz_model:
        raise HTTPException(status_code=404, detail="FAL model not found")
    crud.delete_topaz_upscale_model(session, topaz_model)
    return admin_redirect("upscaling", message="Deleted")


@app.post("/admin/dimension-presets")
def admin_create_dimension_preset(
    request: Request,
    name: str = Form(...),
    width: str = Form(...),
    height: str = Form(...),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    try:
        name_value = name.strip()
        if not name_value:
            raise ValueError("Preset name is required")
        width_value = parse_optional_int(width)
        height_value = parse_optional_int(height)
        if width_value is None or width_value <= 0:
            raise ValueError("Width must be greater than 0")
        if height_value is None or height_value <= 0:
            raise ValueError("Height must be greater than 0")

        crud.create_dimension_preset(
            session,
            name=name_value,
            width=width_value,
            height=height_value,
        )
    except (ValueError, IntegrityError) as exc:
        return admin_redirect("dimensions", error=str(exc))

    return admin_redirect("dimensions", message="Saved")


@app.post("/admin/dimension-presets/{preset_id}/update")
def admin_update_dimension_preset(
    request: Request,
    preset_id: int,
    name: str = Form(...),
    width: str = Form(...),
    height: str = Form(...),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    preset = crud.get_dimension_preset(session, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Dimension preset not found")

    try:
        name_value = name.strip()
        if not name_value:
            raise ValueError("Preset name is required")
        width_value = parse_optional_int(width)
        height_value = parse_optional_int(height)
        if width_value is None or width_value <= 0:
            raise ValueError("Width must be greater than 0")
        if height_value is None or height_value <= 0:
            raise ValueError("Height must be greater than 0")

        crud.update_dimension_preset(
            session,
            preset,
            name=name_value,
            width=width_value,
            height=height_value,
        )
    except (ValueError, IntegrityError) as exc:
        return admin_redirect("dimensions", error=str(exc))

    return admin_redirect("dimensions", message="Saved")


@app.post("/admin/dimension-presets/{preset_id}/delete")
def admin_delete_dimension_preset(
    request: Request,
    preset_id: int,
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    preset = crud.get_dimension_preset(session, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Dimension preset not found")

    crud.delete_dimension_preset(session, preset)
    return admin_redirect("dimensions", message="Deleted")


@app.post("/admin/categories")
def admin_create_category(
    request: Request,
    name: str = Form(...),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    try:
        name_value = normalize_category_name(name)
        crud.create_category(session, name=name_value)
    except (ValueError, IntegrityError) as exc:
        return admin_redirect("categories", error=str(exc))

    return admin_redirect("categories", message="Saved")


@app.post("/admin/categories/{category_id}/update")
def admin_update_category(
    request: Request,
    category_id: int,
    name: str = Form(...),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    category = crud.get_category(session, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    try:
        name_value = normalize_category_name(name)
        crud.update_category(session, category, name=name_value)
    except (ValueError, IntegrityError) as exc:
        return admin_redirect("categories", error=str(exc))

    return admin_redirect("categories", message="Saved")


@app.post("/admin/categories/{category_id}/delete")
def admin_delete_category(
    request: Request,
    category_id: int,
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    category = crud.get_category(session, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    crud.delete_category(session, category)
    return admin_redirect("categories", message="Deleted")


@app.post("/admin/model-configs")
def admin_create_model_config(
    request: Request,
    name: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    enhancement_prompt: str = Form(default=""),
    api_key: str = Form(default=""),
    use_custom_api_key: bool = Form(default=False),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    provider = provider.strip()
    if provider not in provider_registry.provider_names():
        raise HTTPException(status_code=404, detail="Unsupported provider")

    try:
        name_value = normalize_model_config_name(name)

        # Validate model is required
        model_value = model.strip()
        if not model_value:
            raise ValueError("Model is required")

        # Validate API key if custom key is enabled
        api_key_encrypted = None
        api_key_value = api_key.strip()
        if use_custom_api_key:
            if not api_key_value:
                raise ValueError("API key is required when using custom API key")
            api_key_encrypted = model_config_service.encrypt_api_key(api_key_value)

        crud.create_model_config(
            session,
            name=name_value,
            provider=provider,
            model=model_value,
            enhancement_prompt=enhancement_prompt.strip() or None,
            api_key_encrypted=api_key_encrypted,
            use_custom_api_key=use_custom_api_key,
        )
    except (ValueError, IntegrityError) as exc:
        return admin_redirect("models", error=str(exc))

    return admin_redirect("models", message="Saved")


@app.post("/admin/model-configs/{model_config_id}/update")
def admin_update_model_config(
    request: Request,
    model_config_id: int,
    name: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    enhancement_prompt: str = Form(default=""),
    api_key: str = Form(default=""),
    use_custom_api_key: bool = Form(default=False),
    clear_api_key: bool = Form(default=False),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    provider = provider.strip()
    if provider not in provider_registry.provider_names():
        raise HTTPException(status_code=404, detail="Unsupported provider")

    config = crud.get_model_config(session, model_config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Model configuration not found")

    try:
        name_value = normalize_model_config_name(name)

        # Validate model is required
        model_value = model.strip()
        if not model_value:
            raise ValueError("Model is required")

        # Handle API key based on use_custom_api_key flag
        api_key_encrypted = None
        if use_custom_api_key:
            if clear_api_key:
                api_key_encrypted = None
            else:
                api_key_value = api_key.strip()
                if api_key_value:
                    api_key_encrypted = model_config_service.encrypt_api_key(api_key_value)
                elif config.api_key_encrypted:
                    # Keep existing key if no new key provided
                    api_key_encrypted = config.api_key_encrypted

        crud.update_model_config(
            session,
            config,
            name=name_value,
            provider=provider,
            model=model_value,
            enhancement_prompt=enhancement_prompt.strip() or None,
            api_key_encrypted=api_key_encrypted,
            use_custom_api_key=use_custom_api_key,
        )
    except (ValueError, IntegrityError) as exc:
        return admin_redirect("models", error=str(exc))

    return admin_redirect("models", message="Saved")


@app.post("/admin/model-configs/{model_config_id}/delete")
def admin_delete_model_config(
    request: Request,
    model_config_id: int,
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    config = crud.get_model_config(session, model_config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Model configuration not found")

    crud.delete_model_config(session, config)
    return admin_redirect("models", message="Deleted")


@app.post("/admin/enhancement")
def admin_update_enhancement(
    request: Request,
    provider: str = Form(...),
    model: str = Form(...),
    api_key: str = Form(default=""),
    clear_api_key: bool = Form(default=False),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    provider = provider.strip()
    if provider not in provider_registry.provider_names():
        raise HTTPException(status_code=404, detail="Unsupported provider")

    try:
        existing = crud.get_enhancement_config(session)
        api_key_encrypted = existing.api_key_encrypted if existing else None
        if clear_api_key:
            api_key_encrypted = None
        else:
            api_key_value = api_key.strip()
            if api_key_value:
                api_key_encrypted = model_config_service.encrypt_api_key(api_key_value)

        crud.upsert_enhancement_config(
            session,
            provider=provider,
            model=model.strip(),
            api_key_encrypted=api_key_encrypted,
        )
    except (ValueError, IntegrityError) as exc:
        return admin_redirect("enhancement", error=str(exc))

    return admin_redirect("enhancement", message="Saved")


@app.post("/admin/users")
def admin_create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(default=USER_ROLE),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied

    username_value = (username or "").strip()
    if len(username_value) < 3:
        return admin_redirect("users", error="Username must be at least 3 characters")
    try:
        role_value = normalize_user_role(role)
        password_hash = auth_service.hash_password(password)
        crud.create_user(
            session,
            username=username_value,
            password_hash=password_hash,
            role=role_value,
            is_active=True,
        )
    except (ValueError, IntegrityError) as exc:
        return admin_redirect("users", error=str(exc))
    return admin_redirect("users", message="User created")


@app.post("/admin/users/{user_id}/update")
def admin_update_user(
    request: Request,
    user_id: int,
    role: str = Form(...),
    password: str = Form(default=""),
    is_active: bool = Form(default=False),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied

    user = crud.get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        role_value = normalize_user_role(role)
        fields: dict[str, Any] = {"role": role_value, "is_active": is_active}
        password_value = (password or "").strip()
        if password_value:
            fields["password_hash"] = auth_service.hash_password(password_value)

        active_admin_count = crud.count_admin_users(session, active_only=True)
        removing_active_admin = (
            user.role == ADMIN_ROLE and user.is_active and (role_value != ADMIN_ROLE or not is_active)
        )
        if removing_active_admin and active_admin_count <= 1:
            return admin_redirect("users", error="At least one active admin must remain")

        crud.update_user(session, user, **fields)
    except ValueError as exc:
        return admin_redirect("users", error=str(exc))

    return admin_redirect("users", message="User updated")


@app.post("/admin/users/{user_id}/delete")
def admin_delete_user(
    request: Request,
    user_id: int,
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied

    user = crud.get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    acting_user_id = get_session_user_id(request)
    if acting_user_id and acting_user_id == user.id:
        return admin_redirect("users", error="You cannot delete your own user")

    if user.role == ADMIN_ROLE and user.is_active and crud.count_admin_users(session, active_only=True) <= 1:
        return admin_redirect("users", error="At least one active admin must remain")

    crud.delete_user(session, user)
    return admin_redirect("users", message="User deleted")


@app.post("/admin/dev/reset-onboarding")
def admin_reset_onboarding(
    request: Request,
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    denied = require_admin_or_redirect(request)
    if denied:
        return denied
    if not settings.auth_allow_onboarding_reset:
        raise HTTPException(status_code=404, detail="Not found")

    crud.delete_all_users(session)
    clear_auth_session(request)
    return RedirectResponse(url="/login?message=Onboarding+reset", status_code=303)


@app.post("/api/enhance", response_class=JSONResponse)
async def enhance_prompt(
    request: Request,
    session: Session = Depends(get_session),
) -> JSONResponse:
    csrf_header = request.headers.get("X-CSRF-Token")
    if not is_csrf_valid(request, csrf_header):
        return JSONResponse({"prompt": "", "error": "Invalid CSRF token."}, status_code=403)

    payload = await request.json()
    prompt = str(payload.get("prompt") or "").strip()
    model_config_id = payload.get("model_config_id")
    if not prompt:
        return JSONResponse(
            {"prompt": "", "error": "Prompt is required."}, status_code=400
        )

    model_config = None
    if isinstance(model_config_id, int):
        model_config = crud.get_model_config(session, model_config_id)

    enhancement_prompt = None
    if model_config and model_config.enhancement_prompt:
        enhancement_prompt = model_config.enhancement_prompt

    try:
        enhanced = await enhancement_service.enhance(prompt, enhancement_prompt)
        return JSONResponse({"prompt": enhanced, "error": None})
    except ValueError as exc:
        return JSONResponse({"prompt": "", "error": str(exc)}, status_code=400)


@app.post("/api/session-preferences", response_class=JSONResponse)
async def update_session_preferences(
    request: Request,
    session: Session = Depends(get_session),
) -> JSONResponse:
    csrf_header = request.headers.get("X-CSRF-Token")
    if not is_csrf_valid(request, csrf_header):
        return JSONResponse({"success": False, "error": "Invalid CSRF token"}, status_code=403)

    payload = await request.json()
    chat_session_id = str(payload.get("chat_session_id") or "").strip()

    if not chat_session_id or chat_session_id in {"all", "new"}:
        return JSONResponse(
            {"success": False, "error": "Invalid session ID"}, status_code=400
        )

    last_profile_id = payload.get("last_profile_id")
    last_thumb_size = payload.get("last_thumb_size")

    # Validate profile_id if provided
    if last_profile_id is not None:
        if not isinstance(last_profile_id, int) or last_profile_id <= 0:
            return JSONResponse(
                {"success": False, "error": "Invalid profile ID"}, status_code=400
            )

    # Validate thumb_size if provided
    if last_thumb_size is not None:
        if last_thumb_size not in {"sm", "md", "lg"}:
            return JSONResponse(
                {"success": False, "error": "Invalid thumb size"}, status_code=400
            )

    crud.upsert_chat_session_preferences(
        session,
        chat_session_id=chat_session_id,
        last_profile_id=last_profile_id,
        last_thumb_size=last_thumb_size,
    )
    return JSONResponse({"success": True, "error": None})


@app.get("/api/sessions", response_class=JSONResponse)
def list_sessions(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=SESSION_PAGE_SIZE, ge=1, le=50),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """API endpoint to fetch paginated sessions with time categories."""
    session_items, has_more = build_session_items(
        session,
        offset=offset,
        limit=limit,
        max_days=SESSION_MAX_DAYS,
    )
    return JSONResponse({
        "sessions": session_items,
        "has_more": has_more,
        "offset": offset,
        "limit": limit,
    })


@app.get("/sessions/list-fragment", response_class=HTMLResponse)
def list_sessions_fragment(
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=SESSION_PAGE_SIZE, ge=1, le=50),
    prev_category: str = Query(default=""),
    active_conversation: str = Query(default="new"),
    workspace_view: str = Query(default="chat"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    session_items, session_has_more = build_session_items(
        session,
        offset=offset,
        limit=limit,
        max_days=SESSION_MAX_DAYS,
    )
    next_offset = offset + len(session_items)
    next_prev_category = prev_category
    if session_items:
        next_prev_category = str(session_items[-1].get("time_category") or "")

    safe_workspace_view = (workspace_view or "chat").strip().lower()
    if safe_workspace_view not in {"chat", "profiles", "gallery", "admin"}:
        safe_workspace_view = "chat"

    return templates.TemplateResponse(
        request,
        "fragments/session_items_chunk.html",
        {
            "request": request,
            "session_items": session_items,
            "session_has_more": session_has_more,
            "session_next_offset": next_offset,
            "session_prev_category": prev_category,
            "session_next_prev_category": next_prev_category,
            "active_conversation": active_conversation,
            "workspace_view": safe_workspace_view,
        },
    )


@app.get("/profiles/new", response_class=HTMLResponse)
def new_profile_page(
    _request: Request,
    error: str | None = Query(default=None),
) -> HTMLResponse:
    params: dict[str, str] = {"create": "1"}
    if error:
        params["error"] = error
    return RedirectResponse(url=f"/profiles?{urlencode(params)}", status_code=303)


@app.get("/profiles", response_class=HTMLResponse)
def profiles_page(
    request: Request,
    create: bool = Query(default=False),
    edit_id: int | None = Query(default=None),
    error: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    profiles = crud.list_profiles(session)
    model_configs = crud.list_model_configs(session)
    categories = crud.list_categories(session)
    open_edit_id: int | None = None
    if edit_id is not None and crud.get_profile(session, edit_id):
        open_edit_id = edit_id
    fal_key = model_config_service.get_default_api_key("fal")

    return templates.TemplateResponse(
        request,
        "profiles.html",
        {
            "request": request,
            "profiles": profiles,
            "model_configs": model_configs,
            "categories": categories,
            "upscale_ready": upscale_service.is_available(),
            "upscale_models": upscale_service.list_available_models(),
            "fal_upscale_models": crud.list_topaz_upscale_models(
                session, enabled_only=False
            ),
            "topaz_upscale_models": crud.list_topaz_upscale_models(
                session, enabled_only=False
            ),
            "fal_upscale_ready": bool(fal_key),
            "error": error,
            "open_create_dialog": create,
            "open_edit_id": open_edit_id,
        },
    )


@app.get("/profiles/{profile_id}/edit", response_class=HTMLResponse)
def edit_profile_page(
    _request: Request,
    profile_id: int,
    error: str | None = Query(default=None),
) -> HTMLResponse:
    params: dict[str, str] = {"edit_id": str(profile_id)}
    if error:
        params["error"] = error
    return RedirectResponse(url=f"/profiles?{urlencode(params)}", status_code=303)


@app.post("/profiles")
def create_profile(
    request: Request,
    name: str = Form(...),
    model_config_id: str = Form(...),
    base_prompt: str = Form(default=""),
    width: str = Form(default=""),
    height: str = Form(default=""),
    openrouter_aspect_ratio: str = Form(default=""),
    openrouter_image_size: str = Form(default=""),
    fal_aspect_ratio: str = Form(default=""),
    fal_resolution: str = Form(default=""),
    fal_image_size: str = Form(default=""),
    fal_extra_params: str = Form(default=""),
    extra_params: str = Form(default=""),
    n_images: int = Form(default=1),
    seed: str = Form(default=""),
    output_format: str = Form(default="png"),
    upscale_choice: str = Form(default=""),
    upscale_provider: str = Form(default=""),
    upscale_model: str = Form(default=""),
    category_ids: list[int] = Form(default=[]),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    try:
        name_value = normalize_profile_name(name)
        model_config_value = parse_optional_int(model_config_id)
        if model_config_value is None:
            raise ValueError("Model selection is required")
        model_config = crud.get_model_config(session, model_config_value)
        if not model_config:
            raise ValueError("Selected model does not exist")
        provider_value = str(model_config.provider or "").strip().lower()
        if provider_value == "openrouter":
            width_value = None
            height_value = None
        elif provider_value == "fal":
            width_value = None
            height_value = None
        else:
            width_value = parse_optional_int(width)
            height_value = parse_optional_int(height)
            if width_value is not None and width_value <= 0:
                raise ValueError("Width must be greater than 0")
            if height_value is not None and height_value <= 0:
                raise ValueError("Height must be greater than 0")
        params_value = apply_openrouter_image_config(
            params_json={},
            provider=provider_value,
            aspect_ratio=openrouter_aspect_ratio,
            image_size=openrouter_image_size,
        )
        if provider_value == "fal":
            if (fal_image_size or "").strip() and not (fal_aspect_ratio or "").strip():
                params_value["fal_image_size"] = (fal_image_size or "").strip()
            params_value = apply_fal_image_config(
                params_json=params_value,
                provider=provider_value,
                fal_aspect_ratio=fal_aspect_ratio,
                fal_resolution=fal_resolution,
            )
            # Handle FAL-specific parameters (backward compatibility)
            extra = parse_fal_model_params_json(fal_extra_params)
            for key, val in extra.items():
                if key not in ("fal_aspect_ratio", "fal_resolution", "fal_image_size", "image_config") and val is not None:
                    params_value[key] = val
        else:
            # Handle generic parameters for all other providers
            extra = parse_generic_params_json(extra_params)
            reserved_keys = {
                "fal_aspect_ratio",
                "fal_resolution",
                "fal_image_size",
                "image_config",
            }
            for key, val in extra.items():
                if key not in reserved_keys and val is not None:
                    params_value[key] = val
        if (upscale_choice or "").strip():
            (
                upscale_provider_value,
                upscale_model_value,
                upscale_topaz_model_id_value,
            ) = parse_profile_upscale_choice(session, upscale_choice)
        else:
            # Backward-compatible fallback for older form payloads.
            upscale_provider_value = validate_profile_upscale_provider(upscale_provider)
            upscale_model_value = (
                validate_profile_upscale_model(upscale_model)
                if upscale_provider_value == "local"
                else None
            )
            upscale_topaz_model_id_value = None
        normalized_category_ids = normalize_category_ids(category_ids)
        categories = crud.list_categories_by_ids(session, normalized_category_ids)
        if len(categories) != len(normalized_category_ids):
            raise ValueError("One or more selected categories do not exist")
        crud.create_profile(
            session,
            name=name_value,
            provider=model_config.provider,
            model=model_config.model,
            model_config_id=model_config.id,
            base_prompt=base_prompt.strip() or None,
            negative_prompt=None,
            width=width_value,
            height=height_value,
            aspect_ratio=None,
            n_images=max(1, n_images),
            seed=parse_optional_int(seed),
            output_format=(output_format.strip().lower() or "png"),
            upscale_provider=upscale_provider_value,
            upscale_model=upscale_model_value,
            upscale_topaz_model_id=upscale_topaz_model_id_value,
            params_json=params_value,
            categories=categories,
            storage_template_id=resolve_default_storage_template_id(session),
        )
    except (ValueError, IntegrityError) as exc:
        return RedirectResponse(url=f"/profiles?create=1&error={str(exc)}", status_code=303)
    return RedirectResponse(url="/profiles", status_code=303)


@app.post("/profiles/{profile_id}/update")
def update_profile(
    request: Request,
    profile_id: int,
    name: str = Form(...),
    model_config_id: str = Form(...),
    base_prompt: str = Form(default=""),
    width: str = Form(default=""),
    height: str = Form(default=""),
    openrouter_aspect_ratio: str = Form(default=""),
    openrouter_image_size: str = Form(default=""),
    fal_aspect_ratio: str = Form(default=""),
    fal_resolution: str = Form(default=""),
    fal_image_size: str = Form(default=""),
    fal_extra_params: str = Form(default=""),
    extra_params: str = Form(default=""),
    n_images: int = Form(default=1),
    seed: str = Form(default=""),
    output_format: str = Form(default="png"),
    upscale_choice: str = Form(default=""),
    upscale_provider: str = Form(default=""),
    upscale_model: str = Form(default=""),
    category_ids: list[int] = Form(default=[]),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    profile = crud.get_profile(session, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    try:
        name_value = normalize_profile_name(name)
        model_config_value = parse_optional_int(model_config_id)
        if model_config_value is None:
            raise ValueError("Model selection is required")
        model_config = crud.get_model_config(session, model_config_value)
        if not model_config:
            raise ValueError("Selected model does not exist")
        provider_value = str(model_config.provider or "").strip().lower()
        if provider_value == "openrouter":
            width_value = None
            height_value = None
        elif provider_value == "fal":
            width_value = None
            height_value = None
        else:
            width_value = parse_optional_int(width)
            height_value = parse_optional_int(height)
            if width_value is not None and width_value <= 0:
                raise ValueError("Width must be greater than 0")
            if height_value is not None and height_value <= 0:
                raise ValueError("Height must be greater than 0")
        params_value = apply_openrouter_image_config(
            params_json=dict(profile.params_json or {}),
            provider=provider_value,
            aspect_ratio=openrouter_aspect_ratio,
            image_size=openrouter_image_size,
        )
        if provider_value == "fal":
            if (fal_image_size or "").strip() and not (fal_aspect_ratio or "").strip():
                params_value["fal_image_size"] = (fal_image_size or "").strip()
            params_value = apply_fal_image_config(
                params_json=params_value,
                provider=provider_value,
                fal_aspect_ratio=fal_aspect_ratio,
                fal_resolution=fal_resolution,
            )
            # Remove previously stored extra params (all keys except reserved ones)
            reserved_keys = {
                "fal_aspect_ratio",
                "fal_resolution",
                "fal_image_size",
                "image_config",
            }
            for key in list(params_value.keys()):
                if key not in reserved_keys:
                    del params_value[key]
            # Handle FAL-specific parameters (backward compatibility)
            extra = parse_fal_model_params_json(fal_extra_params)
            for key, val in extra.items():
                if key not in reserved_keys and val is not None:
                    params_value[key] = val
        else:
            # Handle generic parameters for all other providers
            # Remove previously stored extra params (all keys except reserved ones)
            reserved_keys = {
                "fal_aspect_ratio",
                "fal_resolution",
                "fal_image_size",
                "image_config",
            }
            for key in list(params_value.keys()):
                if key not in reserved_keys:
                    del params_value[key]
            extra = parse_generic_params_json(extra_params)
            for key, val in extra.items():
                if key not in reserved_keys and val is not None:
                    params_value[key] = val
        if (upscale_choice or "").strip():
            (
                upscale_provider_value,
                upscale_model_value,
                upscale_topaz_model_id_value,
            ) = parse_profile_upscale_choice(session, upscale_choice)
        else:
            # Backward-compatible fallback for older form payloads.
            upscale_provider_value = validate_profile_upscale_provider(upscale_provider)
            upscale_model_value = (
                validate_profile_upscale_model(upscale_model)
                if upscale_provider_value == "local"
                else None
            )
            upscale_topaz_model_id_value = None
        normalized_category_ids = normalize_category_ids(category_ids)
        categories = crud.list_categories_by_ids(session, normalized_category_ids)
        if len(categories) != len(normalized_category_ids):
            raise ValueError("One or more selected categories do not exist")
        crud.update_profile(
            session,
            profile,
            name=name_value,
            provider=model_config.provider,
            model=model_config.model,
            model_config_id=model_config.id,
            base_prompt=base_prompt.strip() or None,
            negative_prompt=None,
            width=width_value,
            height=height_value,
            aspect_ratio=None,
            n_images=max(1, n_images),
            seed=parse_optional_int(seed),
            output_format=(output_format.strip().lower() or "png"),
            upscale_provider=upscale_provider_value,
            upscale_model=upscale_model_value,
            upscale_topaz_model_id=upscale_topaz_model_id_value,
            params_json=params_value,
            categories=categories,
        )
    except (ValueError, IntegrityError) as exc:
        return RedirectResponse(
            url=f"/profiles?edit_id={profile_id}&error={str(exc)}", status_code=303
        )

    return RedirectResponse(url="/profiles", status_code=303)


@app.post("/profiles/{profile_id}/delete")
def delete_profile(
    request: Request,
    profile_id: int,
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    profile = crud.get_profile(session, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    try:
        crud.delete_profile(session, profile)
    except IntegrityError:
        return RedirectResponse(
            url="/profiles?error=Profile cannot be deleted while generations still reference it",
            status_code=303,
        )
    return RedirectResponse(url="/profiles", status_code=303)


def _parse_gallery_filters(
    profile_name: str | None,
    provider: str | None,
    q: str | None,
    category_ids: list[int],
    min_rating: str | None,
    unrated: bool,
    time_preset: str | None,
    date_from: str | None,
    date_to: str | None,
    thumb_size: str | None,
) -> dict[str, Any]:
    """Parse and normalise gallery filter query parameters.

    Returns a dict with all normalised values and derived fields ready for
    both template rendering and ``gallery_service.list_assets``.
    """
    normalized_category_ids = normalize_category_ids(category_ids)
    parsed_min_rating: int | None = None
    try:
        parsed_min_rating = parse_optional_int(min_rating)
    except ValueError:
        parsed_min_rating = None
    min_rating_value = normalize_min_rating(parsed_min_rating)
    time_preset_value = normalize_time_preset(time_preset)
    parsed_date_from: date | None = None
    parsed_date_to: date | None = None
    try:
        parsed_date_from = parse_optional_date(date_from)
        parsed_date_to = parse_optional_date(date_to)
    except ValueError:
        parsed_date_from = None
        parsed_date_to = None
    if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
        parsed_date_from, parsed_date_to = parsed_date_to, parsed_date_from
    if parsed_date_from is not None or parsed_date_to is not None:
        time_preset_value = "custom"
    created_after, created_before = build_created_at_bounds(
        time_preset=time_preset_value,
        from_date=parsed_date_from,
        to_date=parsed_date_to,
    )
    thumb_size_value = normalize_thumb_size(thumb_size)

    filter_params: dict[str, Any] = {}
    if profile_name:
        filter_params["profile_name"] = profile_name
    if provider:
        filter_params["provider"] = provider
    if q:
        filter_params["q"] = q
    if normalized_category_ids:
        filter_params["category_ids"] = normalized_category_ids
    if min_rating_value is not None:
        filter_params["min_rating"] = min_rating_value
    if unrated:
        filter_params["unrated"] = "1"
    filter_params["time_preset"] = time_preset_value
    if parsed_date_from is not None:
        filter_params["date_from"] = parsed_date_from.isoformat()
    if parsed_date_to is not None:
        filter_params["date_to"] = parsed_date_to.isoformat()

    gallery_query = urlencode(filter_params, doseq=True)
    return_to_params: dict[str, Any] = {"thumb_size": thumb_size_value}
    return_to_params.update(filter_params)
    return_to = f"/gallery?{urlencode(return_to_params, doseq=True)}"

    return {
        "normalized_category_ids": normalized_category_ids,
        "min_rating_value": min_rating_value,
        "time_preset_value": time_preset_value,
        "parsed_date_from": parsed_date_from,
        "parsed_date_to": parsed_date_to,
        "created_after": created_after,
        "created_before": created_before,
        "thumb_size_value": thumb_size_value,
        "filter_params": filter_params,
        "gallery_query": gallery_query,
        "return_to": return_to,
    }


@app.get("/gallery", response_class=HTMLResponse)
def gallery_page(
    request: Request,
    page: int = Query(default=1, ge=1),
    profile_name: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    q: str | None = Query(default=None),
    category_ids: list[int] = Query(default=[]),
    min_rating: str | None = Query(default=None),
    unrated: bool = Query(default=False),
    time_preset: str | None = Query(default="today"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    thumb_size: str | None = Query(default="md"),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    filters = _parse_gallery_filters(
        profile_name=profile_name,
        provider=provider,
        q=q,
        category_ids=category_ids,
        min_rating=min_rating,
        unrated=unrated,
        time_preset=time_preset,
        date_from=date_from,
        date_to=date_to,
        thumb_size=thumb_size,
    )
    page_data = gallery_service.list_assets(
        session,
        page=page,
        profile_name=profile_name or None,
        provider=provider or None,
        prompt_query=q or None,
        category_ids=filters["normalized_category_ids"] or None,
        min_rating=None if unrated else filters["min_rating_value"],
        unrated_only=unrated,
        created_after=filters["created_after"],
        created_before=filters["created_before"],
    )
    options = gallery_service.list_filter_options(session)

    parsed_date_from = filters["parsed_date_from"]
    parsed_date_to = filters["parsed_date_to"]

    return templates.TemplateResponse(
        request,
        "gallery.html",
        {
            "request": request,
            "page_data": page_data,
            "profile_name": profile_name or "",
            "provider": provider or "",
            "q": q or "",
            "selected_category_ids": filters["normalized_category_ids"],
            "min_rating": filters["min_rating_value"],
            "unrated_only": unrated,
            "time_preset": filters["time_preset_value"],
            "date_from": parsed_date_from.isoformat() if parsed_date_from else "",
            "date_to": parsed_date_to.isoformat() if parsed_date_to else "",
            "thumb_size": filters["thumb_size_value"],
            "gallery_query": filters["gallery_query"],
            "return_to": filters["return_to"],
            "filter_options": options,
            "message": message or "",
            "error": error or "",
            "hide_header": True,
        },
    )


@app.get("/gallery/items", response_class=HTMLResponse)
def gallery_items(
    request: Request,
    page: int = Query(default=2, ge=1),
    profile_name: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    q: str | None = Query(default=None),
    category_ids: list[int] = Query(default=[]),
    min_rating: str | None = Query(default=None),
    unrated: bool = Query(default=False),
    time_preset: str | None = Query(default="today"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    thumb_size: str | None = Query(default="md"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    filters = _parse_gallery_filters(
        profile_name=profile_name,
        provider=provider,
        q=q,
        category_ids=category_ids,
        min_rating=min_rating,
        unrated=unrated,
        time_preset=time_preset,
        date_from=date_from,
        date_to=date_to,
        thumb_size=thumb_size,
    )
    page_data = gallery_service.list_assets(
        session,
        page=page,
        profile_name=profile_name or None,
        provider=provider or None,
        prompt_query=q or None,
        category_ids=filters["normalized_category_ids"] or None,
        min_rating=None if unrated else filters["min_rating_value"],
        unrated_only=unrated,
        created_after=filters["created_after"],
        created_before=filters["created_before"],
    )

    return templates.TemplateResponse(
        request,
        "fragments/gallery_items.html",
        {
            "request": request,
            "page_data": page_data,
            "thumb_size": filters["thumb_size_value"],
            "gallery_query": filters["gallery_query"],
            "return_to": filters["return_to"],
        },
    )


@app.post("/assets/{asset_id}/rating")
def update_asset_rating(
    request: Request,
    asset_id: int,
    rating: int = Form(...),
    return_to: str = Form(default="/gallery"),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    if rating < 0 or rating > 5:
        return gallery_redirect(return_to, error="Rating must be between 0 and 5")

    asset = crud.get_asset(session, asset_id, with_generation=False)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset.rating = None if rating == 0 else rating
    session.add(asset)
    session.commit()
    if rating == 0:
        return gallery_redirect(return_to, message="Rating removed")
    return gallery_redirect(return_to, message="Rating updated")


@app.post("/assets/bulk-set-categories")
def bulk_set_asset_categories(
    request: Request,
    asset_ids: list[int] = Form(default=[]),
    category_ids: list[int] = Form(default=[]),
    return_to: str = Form(default="/gallery"),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    requested_asset_ids = sorted({item for item in asset_ids if item > 0})
    if not requested_asset_ids:
        return gallery_redirect(return_to, error="No assets selected")

    normalized_category_ids = normalize_category_ids(category_ids)
    if not normalized_category_ids:
        return gallery_redirect(return_to, error="Select at least one category")

    categories = crud.list_categories_by_ids(session, normalized_category_ids)
    if len(categories) != len(normalized_category_ids):
        return gallery_redirect(return_to, error="One or more categories do not exist")

    assets = list(
        session.scalars(
            select(Asset)
            .options(selectinload(Asset.categories))
            .where(Asset.id.in_(requested_asset_ids))
        ).all()
    )
    by_id = {asset.id: asset for asset in assets}

    updated = 0
    missing = 0
    for asset_id in requested_asset_ids:
        asset = by_id.get(asset_id)
        if not asset:
            missing += 1
            continue
        asset.categories = list(categories)
        session.add(asset)
        updated += 1

    if updated:
        session.commit()

    message = None
    error = None
    if updated:
        message = (
            f"Updated categories for {updated} asset(s) "
            f"({len(normalized_category_ids)} categories)"
        )
    if missing:
        error = f"{missing} asset(s) not found"
    if not updated and not missing:
        error = "No assets updated"

    return gallery_redirect(return_to, message=message, error=error)


@app.post("/assets/bulk-delete")
def bulk_delete_assets(
    request: Request,
    asset_ids: list[int] = Form(default=[]),
    return_to: str = Form(default="/gallery"),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    validate_csrf_or_raise(request, csrf_token)
    if not asset_ids:
        return gallery_redirect(return_to, error="No assets selected")

    deleted = 0
    failures = 0

    for asset_id in asset_ids:
        if generation_service.delete_asset(session, asset_id):
            deleted += 1
        else:
            failures += 1

    message = None
    error = None
    if deleted:
        message = f"Deleted {deleted} asset(s)"
    if failures:
        error = f"{failures} asset(s) could not be deleted"
    if not deleted and not failures:
        error = "No assets deleted"

    return gallery_redirect(return_to, message=message, error=error)


@app.get("/assets/{asset_id}", response_class=HTMLResponse)
def asset_detail(
    request: Request,
    asset_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    htmx_request = is_htmx(request)
    asset = session.scalar(
        select(Asset)
        .options(selectinload(Asset.generation), selectinload(Asset.categories))
        .where(Asset.id == asset_id)
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    profiles = crud.list_profiles(session)
    session_token = generation_session_token(asset.generation) if asset.generation else ""

    context = {
        "request": request,
        "asset": asset,
        "profiles": profiles,
        "session_token": session_token,
        "asset_meta_pretty": dumps_json(asset.meta_json, pretty=True),
        "profile_snapshot_pretty": (
            dumps_json(asset.generation.profile_snapshot_json, pretty=True)
            if asset.generation
            else "{}"
        ),
        "storage_snapshot_pretty": (
            dumps_json(asset.generation.storage_template_snapshot_json, pretty=True)
            if asset.generation
            else "{}"
        ),
        "request_snapshot_pretty": (
            dumps_json(asset.generation.request_snapshot_json, pretty=True)
            if asset.generation
            else "{}"
        ),
        "compact_dialog": htmx_request,
    }
    template_name = (
        "fragments/asset_detail_dialog_body.html"
        if htmx_request
        else "asset_detail.html"
    )
    return templates.TemplateResponse(request, template_name, context)


@app.post("/assets/{asset_id}/delete")
def delete_asset(
    request: Request,
    asset_id: int,
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
):
    validate_csrf_or_raise(request, csrf_token)
    deleted = generation_service.delete_asset(session, asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Asset not found")
    if is_htmx(request):
        return templates.TemplateResponse(
            request,
            "fragments/flash.html",
            {"request": request, "message": "Asset deleted"},
        )
    return RedirectResponse(url="/gallery", status_code=303)


@app.post("/generations/{generation_id}/delete")
def delete_generation(
    request: Request,
    generation_id: int,
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
):
    validate_csrf_or_raise(request, csrf_token)
    deleted = generation_service.delete_generation(session, generation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Generation not found")
    if is_htmx(request):
        return templates.TemplateResponse(
            request,
            "fragments/flash.html",
            {"request": request, "message": "Generation deleted"},
        )
    return RedirectResponse(url="/gallery", status_code=303)


@app.post("/generations/{generation_id}/rerun", response_class=HTMLResponse)
def rerun_generation(
    request: Request,
    generation_id: int,
    background_tasks: BackgroundTasks,
    view: str = Query(default="default"),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    validate_csrf_or_raise(request, csrf_token)
    source = crud.get_generation(session, generation_id)
    if not source:
        raise HTTPException(status_code=404, detail="Generation not found")

    generation = generation_service.create_generation_from_snapshot(session, source)
    generation_service.enqueue(background_tasks, generation.id)

    template_name = (
        "fragments/chat_generation_item.html"
        if view.strip().lower() == "chat"
        else "fragments/job_status.html"
    )
    return templates.TemplateResponse(
        request,
        template_name,
        {
            "request": request,
            "generation": generation,
            "assets": [],
        },
    )


@app.get("/assets/{asset_id}/file")
def asset_file(asset_id: int, session: Session = Depends(get_session)) -> FileResponse:
    asset = session.scalar(
        select(Asset)
        .options(selectinload(Asset.generation))
        .where(Asset.id == asset_id)
    )
    if not asset or not asset.generation:
        raise HTTPException(status_code=404, detail="Asset not found")
    absolute_path = generation_service.asset_absolute_path(asset, which="file")
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="Asset file missing")
    return FileResponse(path=absolute_path, media_type=asset.mime)


@app.get("/assets/{asset_id}/download")
def asset_download(
    asset_id: int, session: Session = Depends(get_session)
) -> FileResponse:
    asset = session.scalar(
        select(Asset)
        .options(selectinload(Asset.generation))
        .where(Asset.id == asset_id)
    )
    if not asset or not asset.generation:
        raise HTTPException(status_code=404, detail="Asset not found")
    absolute_path = generation_service.asset_absolute_path(asset, which="file")
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="Asset file missing")
    filename = Path(asset.file_path).name
    return FileResponse(path=absolute_path, media_type=asset.mime, filename=filename)


@app.get("/assets/{asset_id}/thumb")
def asset_thumbnail(
    asset_id: int, session: Session = Depends(get_session)
) -> FileResponse:
    asset = session.scalar(
        select(Asset)
        .options(selectinload(Asset.generation))
        .where(Asset.id == asset_id)
    )
    if not asset or not asset.generation:
        raise HTTPException(status_code=404, detail="Asset not found")
    absolute_path = generation_service.asset_absolute_path(asset, which="thumb")
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail missing")
    return FileResponse(path=absolute_path, media_type="image/webp")


@app.get("/generations/{generation_id}/input-images/{image_index}")
def generation_input_image_thumbnail(
    generation_id: int,
    image_index: int,
    session: Session = Depends(get_session),
) -> Response:
    generation = session.scalar(
        select(Generation).where(Generation.id == generation_id)
    )
    if not generation:
        raise HTTPException(status_code=404, detail="Generation not found")

    snapshot = generation.request_snapshot_json or {}
    input_images = snapshot.get("input_images")
    if not isinstance(input_images, list):
        raise HTTPException(status_code=404, detail="Input image not found")
    if image_index < 0 or image_index >= len(input_images):
        raise HTTPException(status_code=404, detail="Input image not found")

    item = input_images[image_index]
    if not isinstance(item, dict):
        raise HTTPException(status_code=404, detail="Input image not found")

    b64_value = item.get("b64")
    if not isinstance(b64_value, str) or not b64_value.strip():
        raise HTTPException(status_code=404, detail="Input image not available")

    try:
        image_bytes = base64.b64decode(b64_value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid input image data") from exc

    media_type = str(item.get("mime") or "image/png").strip() or "image/png"
    return Response(content=image_bytes, media_type=media_type)


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8010"))
    reload_enabled = os.getenv("UVICORN_RELOAD", "1") in {"1", "true", "True"}
    uvicorn.run("app.main:app", host=host, port=port, reload=reload_enabled)
