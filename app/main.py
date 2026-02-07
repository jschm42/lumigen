from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from typing import Any, AsyncIterator, Optional
from urllib.parse import urlencode

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Query, Request
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
from app.services.gallery_service import GalleryService
from app.services.generation_service import GenerationService
from app.services.sidecar_service import SidecarService
from app.services.storage_service import StorageService
from app.services.thumbnail_service import ThumbnailService
from app.utils.jsonutil import dumps_json
from app.utils.paths import ensure_dir
from app.utils.slugify import slugify


settings = get_settings()


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
provider_registry = ProviderRegistry(settings)
generation_service = GenerationService(
    settings=settings,
    registry=provider_registry,
    storage_service=storage_service,
    thumbnail_service=thumbnail_service,
    sidecar_service=sidecar_service,
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


def normalize_thumb_size(value: Optional[str]) -> str:
    candidate = (value or "md").strip().lower()
    if candidate in {"sm", "md", "lg"}:
        return candidate
    return "md"


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


def normalize_folder_segment(value: str) -> str:
    return slugify(value, max_length=64, fallback="")


@app.get("/", response_class=HTMLResponse)
def generate_page(
    request: Request,
    error: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    profiles = crud.list_profiles(session)
    gallery_folders = crud.list_gallery_folders(session)
    return templates.TemplateResponse(
        "generate.html",
        {
            "request": request,
            "profiles": profiles,
            "gallery_folders": gallery_folders,
            "error": error or "",
        },
    )


@app.post("/generate", response_class=HTMLResponse)
def generate_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    prompt_user: str = Form(...),
    profile_id: int = Form(...),
    width: str = Form(default=""),
    height: str = Form(default=""),
    aspect_ratio: str = Form(default=""),
    n_images: str = Form(default=""),
    seed: str = Form(default=""),
    override_negative_prompt: bool = Form(default=False),
    negative_prompt: str = Form(default=""),
    gallery_folder_id: str = Form(default=""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    profile = crud.get_profile(session, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    try:
        overrides: dict[str, Any] = {}

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

        aspect_ratio_value = aspect_ratio.strip()
        if aspect_ratio_value:
            overrides["aspect_ratio"] = aspect_ratio_value

        n_images_value = parse_optional_int(n_images)
        if n_images_value is not None:
            overrides["n_images"] = max(1, min(8, n_images_value))

        seed_value = parse_optional_int(seed)
        if seed_value is not None:
            overrides["seed"] = seed_value

        if override_negative_prompt:
            overrides["negative_prompt"] = negative_prompt.strip() or None

        folder_id_value = parse_optional_int(gallery_folder_id)
        if folder_id_value is not None:
            folder = crud.get_gallery_folder(session, folder_id_value)
            if not folder:
                raise ValueError("Selected gallery folder does not exist")
            overrides["gallery_folder_id"] = folder.id

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
                "fragments/flash.html",
                {"request": request, "message": f"Error: {str(exc)}"},
            )
        return RedirectResponse(url=f"/?error={str(exc)}", status_code=303)

    if is_htmx(request):
        return templates.TemplateResponse(
            "fragments/job_status.html",
            {
                "request": request,
                "generation": generation,
                "assets": [],
            },
        )
    return RedirectResponse(url=f"/jobs/{generation.id}", status_code=303)


@app.get("/jobs/{generation_id}", response_class=HTMLResponse)
def job_status(
    request: Request,
    generation_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    generation = session.scalar(
        select(Generation).options(selectinload(Generation.assets)).where(Generation.id == generation_id)
    )
    if not generation:
        raise HTTPException(status_code=404, detail="Job not found")

    assets = sorted(generation.assets, key=lambda item: item.id)
    return templates.TemplateResponse(
        "fragments/job_status.html",
        {
            "request": request,
            "generation": generation,
            "assets": assets,
        },
    )


@app.get("/api/providers/{provider}/models", response_class=JSONResponse)
async def provider_models(provider: str) -> JSONResponse:
    try:
        models = await provider_registry.list_models(provider.strip())
        return JSONResponse({"provider": provider, "models": models, "error": None})
    except ProviderError as exc:
        return JSONResponse({"provider": provider, "models": [], "error": str(exc)})


@app.get("/profiles", response_class=HTMLResponse)
def profiles_page(
    request: Request,
    edit_id: Optional[int] = Query(default=None),
    error: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    profiles = crud.list_profiles(session)
    storage_templates = crud.list_storage_templates(session)
    form_profile = crud.get_profile(session, edit_id) if edit_id else None

    return templates.TemplateResponse(
        "profiles.html",
        {
            "request": request,
            "profiles": profiles,
            "storage_templates": storage_templates,
            "form_profile": form_profile,
            "providers": provider_registry.provider_names(),
            "error": error,
        },
    )


@app.post("/profiles")
def create_profile(
    name: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    base_prompt: str = Form(...),
    negative_prompt: str = Form(default=""),
    width: str = Form(default=""),
    height: str = Form(default=""),
    aspect_ratio: str = Form(default=""),
    n_images: int = Form(default=1),
    seed: str = Form(default=""),
    output_format: str = Form(default="png"),
    params_json: str = Form(default="{}"),
    storage_template_id: int = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    try:
        crud.create_profile(
            session,
            name=name.strip(),
            provider=provider.strip(),
            model=model.strip(),
            base_prompt=base_prompt.strip(),
            negative_prompt=negative_prompt.strip() or None,
            width=parse_optional_int(width),
            height=parse_optional_int(height),
            aspect_ratio=aspect_ratio.strip() or None,
            n_images=max(1, n_images),
            seed=parse_optional_int(seed),
            output_format=(output_format.strip().lower() or "png"),
            params_json=parse_params_json(params_json),
            storage_template_id=storage_template_id,
        )
    except (ValueError, IntegrityError) as exc:
        return RedirectResponse(url=f"/profiles?error={str(exc)}", status_code=303)
    return RedirectResponse(url="/profiles", status_code=303)


@app.post("/profiles/{profile_id}/update")
def update_profile(
    profile_id: int,
    name: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    base_prompt: str = Form(...),
    negative_prompt: str = Form(default=""),
    width: str = Form(default=""),
    height: str = Form(default=""),
    aspect_ratio: str = Form(default=""),
    n_images: int = Form(default=1),
    seed: str = Form(default=""),
    output_format: str = Form(default="png"),
    params_json: str = Form(default="{}"),
    storage_template_id: int = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    profile = crud.get_profile(session, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    try:
        crud.update_profile(
            session,
            profile,
            name=name.strip(),
            provider=provider.strip(),
            model=model.strip(),
            base_prompt=base_prompt.strip(),
            negative_prompt=negative_prompt.strip() or None,
            width=parse_optional_int(width),
            height=parse_optional_int(height),
            aspect_ratio=aspect_ratio.strip() or None,
            n_images=max(1, n_images),
            seed=parse_optional_int(seed),
            output_format=(output_format.strip().lower() or "png"),
            params_json=parse_params_json(params_json),
            storage_template_id=storage_template_id,
        )
    except (ValueError, IntegrityError) as exc:
        return RedirectResponse(url=f"/profiles?edit_id={profile_id}&error={str(exc)}", status_code=303)

    return RedirectResponse(url="/profiles", status_code=303)


@app.post("/profiles/{profile_id}/delete")
def delete_profile(profile_id: int, session: Session = Depends(get_session)) -> RedirectResponse:
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
    folder: Optional[str] = Query(default=None),
    thumb_size: Optional[str] = Query(default="md"),
    message: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    selected_folder = (folder or "").strip()
    root_only = selected_folder == "root"
    folder_id: Optional[int] = None
    if selected_folder and not root_only:
        try:
            folder_id = int(selected_folder)
        except ValueError:
            selected_folder = ""

    page_data = gallery_service.list_assets(
        session,
        page=page,
        profile_name=profile_name or None,
        provider=provider or None,
        status=status or None,
        prompt_query=q or None,
        gallery_folder_id=folder_id,
        root_only=root_only,
    )
    options = gallery_service.list_filter_options(session)
    return templates.TemplateResponse(
        "gallery.html",
        {
            "request": request,
            "page_data": page_data,
            "profile_name": profile_name or "",
            "provider": provider or "",
            "status": status or "",
            "q": q or "",
            "folder": selected_folder,
            "thumb_size": normalize_thumb_size(thumb_size),
            "filter_options": options,
            "message": message or "",
            "error": error or "",
        },
    )


@app.post("/gallery/folders")
def create_gallery_folder(
    parent_folder_id: str = Form(default=""),
    folder_name: str = Form(...),
    return_to: str = Form(default="/gallery"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    try:
        parent_id = parse_optional_int(parent_folder_id)
    except ValueError:
        return gallery_redirect(return_to, error="Invalid parent folder")
    parent_path = ""
    if parent_id is not None:
        parent = crud.get_gallery_folder(session, parent_id)
        if not parent:
            return gallery_redirect(return_to, error="Parent folder not found")
        parent_path = parent.path

    folder_segment = normalize_folder_segment(folder_name)
    if not folder_segment:
        return gallery_redirect(return_to, error="Folder name is empty or invalid")

    path = f"{parent_path}/{folder_segment}" if parent_path else folder_segment
    if crud.get_gallery_folder_by_path(session, path):
        return gallery_redirect(return_to, error=f"Folder already exists: {path}")

    try:
        crud.create_gallery_folder(session, path=path)
    except IntegrityError:
        return gallery_redirect(return_to, error=f"Folder already exists: {path}")

    return gallery_redirect(return_to, message=f"Folder created: {path}")


@app.post("/assets/{asset_id}/move-folder")
def move_asset_to_folder(
    asset_id: int,
    gallery_folder_id: str = Form(default=""),
    return_to: str = Form(default="/gallery"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    asset = crud.get_asset(session, asset_id, with_generation=False)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    try:
        folder_id = parse_optional_int(gallery_folder_id)
    except ValueError:
        return gallery_redirect(return_to, error="Invalid target folder")
    if folder_id is None:
        asset.gallery_folder_id = None
    else:
        folder = crud.get_gallery_folder(session, folder_id)
        if not folder:
            return gallery_redirect(return_to, error="Target folder not found")
        asset.gallery_folder_id = folder.id

    session.add(asset)
    session.commit()
    return gallery_redirect(return_to, message=f"Asset #{asset.id} moved")


@app.get("/assets/{asset_id}", response_class=HTMLResponse)
def asset_detail(
    request: Request,
    asset_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    asset = session.scalar(
        select(Asset).options(selectinload(Asset.generation), selectinload(Asset.gallery_folder)).where(Asset.id == asset_id)
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    return templates.TemplateResponse(
        "asset_detail.html",
        {
            "request": request,
            "asset": asset,
            "asset_meta_pretty": dumps_json(asset.meta_json, pretty=True),
            "profile_snapshot_pretty": dumps_json(asset.generation.profile_snapshot_json, pretty=True) if asset.generation else "{}",
            "storage_snapshot_pretty": dumps_json(asset.generation.storage_template_snapshot_json, pretty=True) if asset.generation else "{}",
            "request_snapshot_pretty": dumps_json(asset.generation.request_snapshot_json, pretty=True) if asset.generation else "{}",
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
    asset = session.scalar(select(Asset).options(selectinload(Asset.generation)).where(Asset.id == asset_id))
    if not asset or not asset.generation:
        raise HTTPException(status_code=404, detail="Asset not found")
    absolute_path = generation_service.asset_absolute_path(asset, which="file")
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="Asset file missing")
    return FileResponse(path=absolute_path, media_type=asset.mime)


@app.get("/assets/{asset_id}/download")
def asset_download(asset_id: int, session: Session = Depends(get_session)) -> FileResponse:
    asset = session.scalar(select(Asset).options(selectinload(Asset.generation)).where(Asset.id == asset_id))
    if not asset or not asset.generation:
        raise HTTPException(status_code=404, detail="Asset not found")
    absolute_path = generation_service.asset_absolute_path(asset, which="file")
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="Asset file missing")
    filename = Path(asset.file_path).name
    return FileResponse(path=absolute_path, media_type=asset.mime, filename=filename)


@app.get("/assets/{asset_id}/thumb")
def asset_thumbnail(asset_id: int, session: Session = Depends(get_session)) -> FileResponse:
    asset = session.scalar(select(Asset).options(selectinload(Asset.generation)).where(Asset.id == asset_id))
    if not asset or not asset.generation:
        raise HTTPException(status_code=404, detail="Asset not found")
    absolute_path = generation_service.asset_absolute_path(asset, which="thumb")
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail missing")
    return FileResponse(path=absolute_path, media_type="image/webp")


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8010"))
    reload_enabled = os.getenv("UVICORN_RELOAD", "0") in {"1", "true", "True"}
    uvicorn.run("app.main:app", host=host, port=port, reload=reload_enabled)
