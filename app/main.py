from __future__ import annotations

import base64
import copy
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Optional
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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import crud
from app.db.engine import SessionLocal, get_session, init_db
from app.db.models import Asset, Generation
from app.providers.base import ProviderError
from app.providers.registry import ProviderRegistry
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

MAX_INPUT_IMAGES = 5
MAX_CATEGORY_NAME_LENGTH = 30
MAX_PROFILE_NAME_LENGTH = 50
MAX_MODEL_CONFIG_NAME_LENGTH = 50
OPENROUTER_ALLOWED_ASPECT_RATIOS = {
    "1:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "9:21",
    "16:9",
    "21:9",
}
OPENROUTER_ALLOWED_IMAGE_SIZES = {"1K", "2K", "4K"}


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

template_dir = Path(__file__).resolve().parent / "web" / "templates"
static_dir = Path(__file__).resolve().parent / "web" / "static"
templates = Jinja2Templates(directory=str(template_dir))

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

storage_service = StorageService(max_slug_length=settings.max_slug_length)
thumbnail_service = ThumbnailService(storage_service, max_px=settings.thumb_max_px)
sidecar_service = SidecarService(storage_service)
model_config_service = ModelConfigService(settings)
enhancement_service = EnhancementService(settings, model_config_service)
upscale_service = UpscaleService(settings)
provider_registry = ProviderRegistry(settings)
generation_service = GenerationService(
    settings=settings,
    registry=provider_registry,
    storage_service=storage_service,
    thumbnail_service=thumbnail_service,
    sidecar_service=sidecar_service,
    model_config_service=model_config_service,
    upscale_service=upscale_service,
)
gallery_service = GalleryService(default_page_size=settings.default_page_size)


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request", "").lower() == "true"


def parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return int(stripped)


def parse_params_json(raw: Optional[str]) -> dict[str, Any]:
    if not raw or not raw.strip():
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("params_json must be a JSON object")
    return parsed


def apply_openrouter_image_config(
    *,
    params_json: dict[str, Any],
    provider: str,
    aspect_ratio: str,
    image_size: str,
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
        raise ValueError("Invalid OpenRouter aspect ratio")
    if image_size_value and image_size_value not in OPENROUTER_ALLOWED_IMAGE_SIZES:
        raise ValueError("Invalid OpenRouter image size")

    if ratio_value:
        image_config["aspect_ratio"] = ratio_value
    else:
        image_config.pop("aspect_ratio", None)

    if image_size_value:
        image_config["image_size"] = image_size_value
    else:
        image_config.pop("image_size", None)

    if image_config:
        merged["image_config"] = image_config
    else:
        merged.pop("image_config", None)
    return merged


def normalize_thumb_size(value: Optional[str]) -> str:
    candidate = (value or "md").strip().lower()
    if candidate in {"sm", "md", "lg"}:
        return candidate
    return "md"


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


def generation_session_title(generation: Generation) -> str:
    snapshot = generation.request_snapshot_json or {}
    raw_title = snapshot.get("chat_session_title")
    if isinstance(raw_title, str):
        return raw_title.strip()
    return ""


def generation_chat_hidden(generation: Generation) -> bool:
    snapshot = generation.request_snapshot_json or {}
    return bool(snapshot.get("chat_hidden"))


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
    error: Optional[str] = None,
) -> RedirectResponse:
    view = (workspace_view or "chat").strip().lower()
    if view not in {"chat", "profiles", "gallery", "admin"}:
        view = "chat"
    params: dict[str, str] = {"workspace_view": view, "conversation": conversation}
    if error:
        params["error"] = error
    return RedirectResponse(url=f"/?{urlencode(params)}", status_code=303)


def safe_gallery_return_to(value: Optional[str]) -> str:
    candidate = (value or "/gallery").strip()
    if candidate.startswith("/gallery"):
        return candidate
    return "/gallery"


def gallery_redirect(
    return_to: Optional[str] = "/gallery",
    *,
    message: Optional[str] = None,
    error: Optional[str] = None,
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
        raise ValueError("Name is required")
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


@app.get("/", response_class=HTMLResponse)
def generate_page(
    request: Request,
    error: Optional[str] = Query(default=None),
    conversation: Optional[str] = Query(default=None),
    workspace_view: Optional[str] = Query(default="chat"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    profiles = crud.list_profiles(session)
    dimension_presets = crud.list_dimension_presets(session)
    enhancement_config = crud.get_enhancement_config(session)
    recent_generations = list(
        session.scalars(
            select(Generation)
            .options(selectinload(Generation.assets))
            .order_by(Generation.created_at.desc(), Generation.id.desc())
            .limit(250)
        ).all()
    )
    recent_generations.reverse()
    recent_generations = [
        generation
        for generation in recent_generations
        if not generation_chat_hidden(generation)
    ]

    session_index: dict[str, dict[str, Any]] = {}
    for generation in recent_generations:
        token = generation_session_token(generation)
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

    session_items = sorted(
        session_index.values(),
        key=lambda item: (
            item.get("latest_created_at") or datetime.min,
            item.get("latest_generation_id") or 0,
        ),
        reverse=True,
    )
    for item in session_items:
        started_at = item.get("started_at")
        latest_at = item.get("latest_created_at")
        started_label = format_session_timestamp(started_at)
        latest_label = format_session_timestamp(latest_at)
        base_label = str(item.get("profile_label") or "Session")
        custom_title = str(item.get("custom_title") or "").strip()
        item["label"] = custom_title or base_label
        item["subtitle"] = latest_label or started_label

    active_conversation = (conversation or "").strip()
    if active_conversation:
        if active_conversation not in {"all", "new"} and active_conversation not in {
            item["token"] for item in session_items
        }:
            active_conversation = ""
    if not active_conversation:
        active_conversation = session_items[0]["token"] if session_items else "new"

    if active_conversation == "all":
        conversation_generations = recent_generations
    elif active_conversation == "new":
        conversation_generations = []
    else:
        conversation_generations = [
            generation
            for generation in recent_generations
            if generation_session_token(generation) == active_conversation
        ]

    active_workspace_view = (workspace_view or "chat").strip().lower()
    if active_workspace_view not in {"chat", "profiles", "gallery", "admin"}:
        active_workspace_view = "chat"

    return templates.TemplateResponse(
        "generate.html",
        {
            "request": request,
            "profiles": profiles,
            "dimension_presets": dimension_presets,
            "conversation_generations": conversation_generations,
            "session_items": session_items,
            "active_conversation": active_conversation,
            "workspace_view": active_workspace_view,
            "hide_footer": True,
            "hide_header": True,
            "enhancement_ready": bool(
                enhancement_config and enhancement_config.api_key_encrypted
            ),
            "upscale_ready": upscale_service.is_available(),
            "upscale_models": upscale_service.list_available_models(),
            "error": error or "",
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
    upscale_enable: bool = Form(default=False),
    upscale_model: str = Form(default=""),
    input_images: list[UploadFile] = File(default=[]),
    session: Session = Depends(get_session),
) -> HTMLResponse:
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

        if input_images:
            if len(input_images) > MAX_INPUT_IMAGES:
                raise ValueError(f"Upload up to {MAX_INPUT_IMAGES} input images.")
            encoded_images: list[dict[str, str]] = []
            for upload in input_images:
                content_type = (upload.content_type or "").lower()
                if not content_type.startswith("image/"):
                    raise ValueError("Input images must be valid image files.")
                data = upload.file.read()
                if not data:
                    continue
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
        if provider_value != "openrouter":
            width_value = parse_optional_int(width)
            if width_value is not None:
                if width_value <= 0:
                    raise ValueError("Width must be > 0")
                overrides["width"] = width_value

            height_value = parse_optional_int(height)
            if height_value is not None:
                if height_value <= 0:
                    raise ValueError("Height must be > 0")
                overrides["height"] = height_value

        n_images_value = parse_optional_int(n_images)
        if n_images_value is not None:
            overrides["n_images"] = max(1, min(8, n_images_value))

        seed_value = parse_optional_int(seed)
        if seed_value is not None:
            overrides["seed"] = seed_value

        if upscale_enable:
            if not upscale_service.is_available():
                raise ValueError("Upscaler is not configured on this server")
            model_value = upscale_model.strip()
            if not model_value:
                raise ValueError("Upscale model is required")
            available = upscale_service.list_available_models()
            if available and model_value not in available:
                raise ValueError("Selected upscale model is not available")
            overrides["upscale_model"] = model_value

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
            "fragments/chat_generation_item.html",
            {
                "request": request,
                "generation": generation,
                "assets": [],
            },
        )
    return RedirectResponse(url=f"/jobs/{generation.id}", status_code=303)


@app.post("/sessions/rename")
def rename_chat_session(
    session_token: str = Form(...),
    title: str = Form(...),
    active_conversation: str = Form(default=""),
    workspace_view: str = Form(default="chat"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
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
    session_token: str = Form(...),
    active_conversation: str = Form(default=""),
    workspace_view: str = Form(default="chat"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
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
    session: Session = Depends(get_session),
) -> HTMLResponse:
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
    error: Optional[str] = Query(default=None),
    message: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    model_configs = crud.list_model_configs(session)
    dimension_presets = crud.list_dimension_presets(session)
    categories = crud.list_categories(session)
    enhancement_config = crud.get_enhancement_config(session)
    encryption_ready = bool((settings.provider_config_key or "").strip())

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "model_configs": model_configs,
            "dimension_presets": dimension_presets,
            "categories": categories,
            "enhancement_config": enhancement_config,
            "providers": provider_registry.provider_names(),
            "error": error or "",
            "message": message or "",
            "encryption_ready": encryption_ready,
        },
    )


@app.post("/admin/dimension-presets")
def admin_create_dimension_preset(
    name: str = Form(...),
    width: str = Form(...),
    height: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    try:
        name_value = name.strip()
        if not name_value:
            raise ValueError("Name is required")
        width_value = parse_optional_int(width)
        height_value = parse_optional_int(height)
        if width_value is None or width_value <= 0:
            raise ValueError("Width must be > 0")
        if height_value is None or height_value <= 0:
            raise ValueError("Height must be > 0")

        crud.create_dimension_preset(
            session,
            name=name_value,
            width=width_value,
            height=height_value,
        )
    except (ValueError, IntegrityError) as exc:
        return RedirectResponse(url=f"/admin?error={str(exc)}", status_code=303)

    return RedirectResponse(url="/admin?message=Saved", status_code=303)


@app.post("/admin/dimension-presets/{preset_id}/update")
def admin_update_dimension_preset(
    preset_id: int,
    name: str = Form(...),
    width: str = Form(...),
    height: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    preset = crud.get_dimension_preset(session, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Dimension preset not found")

    try:
        name_value = name.strip()
        if not name_value:
            raise ValueError("Name is required")
        width_value = parse_optional_int(width)
        height_value = parse_optional_int(height)
        if width_value is None or width_value <= 0:
            raise ValueError("Width must be > 0")
        if height_value is None or height_value <= 0:
            raise ValueError("Height must be > 0")

        crud.update_dimension_preset(
            session,
            preset,
            name=name_value,
            width=width_value,
            height=height_value,
        )
    except (ValueError, IntegrityError) as exc:
        return RedirectResponse(url=f"/admin?error={str(exc)}", status_code=303)

    return RedirectResponse(url="/admin?message=Saved", status_code=303)


@app.post("/admin/dimension-presets/{preset_id}/delete")
def admin_delete_dimension_preset(
    preset_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    preset = crud.get_dimension_preset(session, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Dimension preset not found")

    crud.delete_dimension_preset(session, preset)
    return RedirectResponse(url="/admin?message=Deleted", status_code=303)


@app.post("/admin/categories")
def admin_create_category(
    name: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    try:
        name_value = normalize_category_name(name)
        crud.create_category(session, name=name_value)
    except (ValueError, IntegrityError) as exc:
        return RedirectResponse(url=f"/admin?error={str(exc)}", status_code=303)

    return RedirectResponse(url="/admin?message=Saved", status_code=303)


@app.post("/admin/categories/{category_id}/update")
def admin_update_category(
    category_id: int,
    name: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    category = crud.get_category(session, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    try:
        name_value = normalize_category_name(name)
        crud.update_category(session, category, name=name_value)
    except (ValueError, IntegrityError) as exc:
        return RedirectResponse(url=f"/admin?error={str(exc)}", status_code=303)

    return RedirectResponse(url="/admin?message=Saved", status_code=303)


@app.post("/admin/categories/{category_id}/delete")
def admin_delete_category(
    category_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    category = crud.get_category(session, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    crud.delete_category(session, category)
    return RedirectResponse(url="/admin?message=Deleted", status_code=303)


@app.post("/admin/model-configs")
def admin_create_model_config(
    name: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    enhancement_prompt: str = Form(default=""),
    api_key: str = Form(default=""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    provider = provider.strip()
    if provider not in provider_registry.provider_names():
        raise HTTPException(status_code=404, detail="Unknown provider")

    try:
        name_value = normalize_model_config_name(name)
        api_key_encrypted = None
        api_key_value = api_key.strip()
        if api_key_value:
            api_key_encrypted = model_config_service.encrypt_api_key(api_key_value)

        crud.create_model_config(
            session,
            name=name_value,
            provider=provider,
            model=model.strip(),
            enhancement_prompt=enhancement_prompt.strip() or None,
            api_key_encrypted=api_key_encrypted,
        )
    except (ValueError, IntegrityError) as exc:
        return RedirectResponse(url=f"/admin?error={str(exc)}", status_code=303)

    return RedirectResponse(url="/admin?message=Saved", status_code=303)


@app.post("/admin/model-configs/{model_config_id}/update")
def admin_update_model_config(
    model_config_id: int,
    name: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    enhancement_prompt: str = Form(default=""),
    api_key: str = Form(default=""),
    clear_api_key: bool = Form(default=False),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    provider = provider.strip()
    if provider not in provider_registry.provider_names():
        raise HTTPException(status_code=404, detail="Unknown provider")

    config = crud.get_model_config(session, model_config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Model config not found")

    try:
        name_value = normalize_model_config_name(name)
        api_key_encrypted = config.api_key_encrypted
        if clear_api_key:
            api_key_encrypted = None
        else:
            api_key_value = api_key.strip()
            if api_key_value:
                api_key_encrypted = model_config_service.encrypt_api_key(api_key_value)

        crud.update_model_config(
            session,
            config,
            name=name_value,
            provider=provider,
            model=model.strip(),
            enhancement_prompt=enhancement_prompt.strip() or None,
            api_key_encrypted=api_key_encrypted,
        )
    except (ValueError, IntegrityError) as exc:
        return RedirectResponse(url=f"/admin?error={str(exc)}", status_code=303)

    return RedirectResponse(url="/admin?message=Saved", status_code=303)


@app.post("/admin/model-configs/{model_config_id}/delete")
def admin_delete_model_config(
    model_config_id: int, session: Session = Depends(get_session)
) -> RedirectResponse:
    config = crud.get_model_config(session, model_config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Model config not found")

    crud.delete_model_config(session, config)
    return RedirectResponse(url="/admin?message=Deleted", status_code=303)


@app.post("/admin/enhancement")
def admin_update_enhancement(
    provider: str = Form(...),
    model: str = Form(...),
    api_key: str = Form(default=""),
    clear_api_key: bool = Form(default=False),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    provider = provider.strip()
    if provider not in provider_registry.provider_names():
        raise HTTPException(status_code=404, detail="Unknown provider")

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
        return RedirectResponse(url=f"/admin?error={str(exc)}", status_code=303)

    return RedirectResponse(url="/admin?message=Saved", status_code=303)


@app.post("/api/enhance", response_class=JSONResponse)
async def enhance_prompt(
    request: Request,
    session: Session = Depends(get_session),
) -> JSONResponse:
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


@app.get("/profiles/new", response_class=HTMLResponse)
def new_profile_page(
    request: Request,
    error: Optional[str] = Query(default=None),
) -> HTMLResponse:
    params: dict[str, str] = {"create": "1"}
    if error:
        params["error"] = error
    return RedirectResponse(url=f"/profiles?{urlencode(params)}", status_code=303)


@app.get("/profiles", response_class=HTMLResponse)
def profiles_page(
    request: Request,
    create: bool = Query(default=False),
    edit_id: Optional[int] = Query(default=None),
    error: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    profiles = crud.list_profiles(session)
    storage_templates = crud.list_storage_templates(session)
    model_configs = crud.list_model_configs(session)
    categories = crud.list_categories(session)
    open_edit_id: Optional[int] = None
    if edit_id is not None and crud.get_profile(session, edit_id):
        open_edit_id = edit_id

    return templates.TemplateResponse(
        "profiles.html",
        {
            "request": request,
            "profiles": profiles,
            "storage_templates": storage_templates,
            "model_configs": model_configs,
            "categories": categories,
            "error": error,
            "open_create_dialog": create,
            "open_edit_id": open_edit_id,
        },
    )


@app.get("/profiles/{profile_id}/edit", response_class=HTMLResponse)
def edit_profile_page(
    request: Request,
    profile_id: int,
    error: Optional[str] = Query(default=None),
) -> HTMLResponse:
    params: dict[str, str] = {"edit_id": str(profile_id)}
    if error:
        params["error"] = error
    return RedirectResponse(url=f"/profiles?{urlencode(params)}", status_code=303)


@app.post("/profiles")
def create_profile(
    name: str = Form(...),
    model_config_id: str = Form(...),
    base_prompt: str = Form(default=""),
    width: str = Form(default=""),
    height: str = Form(default=""),
    openrouter_aspect_ratio: str = Form(default=""),
    openrouter_image_size: str = Form(default=""),
    n_images: int = Form(default=1),
    seed: str = Form(default=""),
    output_format: str = Form(default="png"),
    params_json: str = Form(default="{}"),
    category_ids: list[int] = Form(default=[]),
    storage_template_id: int = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
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
        else:
            width_value = parse_optional_int(width)
            height_value = parse_optional_int(height)
            if width_value is not None and width_value <= 0:
                raise ValueError("Width must be > 0")
            if height_value is not None and height_value <= 0:
                raise ValueError("Height must be > 0")
        params_value = apply_openrouter_image_config(
            params_json=parse_params_json(params_json),
            provider=provider_value,
            aspect_ratio=openrouter_aspect_ratio,
            image_size=openrouter_image_size,
        )
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
            params_json=params_value,
            categories=categories,
            storage_template_id=storage_template_id,
        )
    except (ValueError, IntegrityError) as exc:
        return RedirectResponse(url=f"/profiles?create=1&error={str(exc)}", status_code=303)
    return RedirectResponse(url="/profiles", status_code=303)


@app.post("/profiles/{profile_id}/update")
def update_profile(
    profile_id: int,
    name: str = Form(...),
    model_config_id: str = Form(...),
    base_prompt: str = Form(default=""),
    width: str = Form(default=""),
    height: str = Form(default=""),
    openrouter_aspect_ratio: str = Form(default=""),
    openrouter_image_size: str = Form(default=""),
    n_images: int = Form(default=1),
    seed: str = Form(default=""),
    output_format: str = Form(default="png"),
    params_json: str = Form(default="{}"),
    category_ids: list[int] = Form(default=[]),
    storage_template_id: int = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
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
        else:
            width_value = parse_optional_int(width)
            height_value = parse_optional_int(height)
            if width_value is not None and width_value <= 0:
                raise ValueError("Width must be > 0")
            if height_value is not None and height_value <= 0:
                raise ValueError("Height must be > 0")
        params_value = apply_openrouter_image_config(
            params_json=parse_params_json(params_json),
            provider=provider_value,
            aspect_ratio=openrouter_aspect_ratio,
            image_size=openrouter_image_size,
        )
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
            params_json=params_value,
            categories=categories,
            storage_template_id=storage_template_id,
        )
    except (ValueError, IntegrityError) as exc:
        return RedirectResponse(
            url=f"/profiles?edit_id={profile_id}&error={str(exc)}", status_code=303
        )

    return RedirectResponse(url="/profiles", status_code=303)


@app.post("/profiles/{profile_id}/delete")
def delete_profile(
    profile_id: int, session: Session = Depends(get_session)
) -> RedirectResponse:
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


@app.get("/gallery", response_class=HTMLResponse)
def gallery_page(
    request: Request,
    page: int = Query(default=1, ge=1),
    profile_name: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    category_ids: list[int] = Query(default=[]),
    thumb_size: Optional[str] = Query(default="md"),
    message: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    normalized_category_ids = normalize_category_ids(category_ids)
    thumb_size_value = normalize_thumb_size(thumb_size)
    page_data = gallery_service.list_assets(
        session,
        page=page,
        profile_name=profile_name or None,
        provider=provider or None,
        status=status or None,
        prompt_query=q or None,
        category_ids=normalized_category_ids or None,
    )
    options = gallery_service.list_filter_options(session)

    filter_params: dict[str, Any] = {}
    if profile_name:
        filter_params["profile_name"] = profile_name
    if provider:
        filter_params["provider"] = provider
    if status:
        filter_params["status"] = status
    if q:
        filter_params["q"] = q
    if normalized_category_ids:
        filter_params["category_ids"] = normalized_category_ids
    gallery_query = urlencode(filter_params, doseq=True)

    return_to_params: dict[str, Any] = {"page": page, "thumb_size": thumb_size_value}
    return_to_params.update(filter_params)
    return_to = f"/gallery?{urlencode(return_to_params, doseq=True)}"

    return templates.TemplateResponse(
        "gallery.html",
        {
            "request": request,
            "page_data": page_data,
            "profile_name": profile_name or "",
            "provider": provider or "",
            "status": status or "",
            "q": q or "",
            "selected_category_ids": normalized_category_ids,
            "thumb_size": thumb_size_value,
            "gallery_query": gallery_query,
            "return_to": return_to,
            "filter_options": options,
            "message": message or "",
            "error": error or "",
            "hide_header": True,
            "hide_footer": True,
        },
    )


@app.post("/assets/bulk-set-categories")
def bulk_set_asset_categories(
    asset_ids: list[int] = Form(default=[]),
    category_ids: list[int] = Form(default=[]),
    return_to: str = Form(default="/gallery"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
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
    asset_ids: list[int] = Form(default=[]),
    return_to: str = Form(default="/gallery"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
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
    asset = session.scalar(
        select(Asset)
        .options(selectinload(Asset.generation), selectinload(Asset.categories))
        .where(Asset.id == asset_id)
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    return templates.TemplateResponse(
        "asset_detail.html",
        {
            "request": request,
            "asset": asset,
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
        },
    )


@app.post("/assets/{asset_id}/delete")
def delete_asset(
    request: Request,
    asset_id: int,
    session: Session = Depends(get_session),
):
    deleted = generation_service.delete_asset(session, asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Asset not found")
    if is_htmx(request):
        return templates.TemplateResponse(
            "fragments/flash.html",
            {"request": request, "message": "Asset deleted"},
        )
    return RedirectResponse(url="/gallery", status_code=303)


@app.post("/generations/{generation_id}/delete")
def delete_generation(
    request: Request,
    generation_id: int,
    session: Session = Depends(get_session),
):
    deleted = generation_service.delete_generation(session, generation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Generation not found")
    if is_htmx(request):
        return templates.TemplateResponse(
            "fragments/flash.html",
            {"request": request, "message": "Generation deleted"},
        )
    return RedirectResponse(url="/gallery", status_code=303)


@app.post("/generations/{generation_id}/rerun", response_class=HTMLResponse)
def rerun_generation(
    request: Request,
    generation_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    source = crud.get_generation(session, generation_id)
    if not source:
        raise HTTPException(status_code=404, detail="Generation not found")

    generation = generation_service.create_generation_from_snapshot(session, source)
    generation_service.enqueue(background_tasks, generation.id)

    return templates.TemplateResponse(
        "fragments/job_status.html",
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


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8010"))
    reload_enabled = os.getenv("UVICORN_RELOAD", "1") in {"1", "true", "True"}
    uvicorn.run("app.main:app", host=host, port=port, reload=reload_enabled)
