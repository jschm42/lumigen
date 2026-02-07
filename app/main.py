from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import crud
from app.db.engine import SessionLocal, get_session, init_db
from app.db.models import Asset, Generation
from app.providers.registry import ProviderRegistry
from app.services.gallery_service import GalleryService
from app.services.generation_service import GenerationService
from app.services.sidecar_service import SidecarService
from app.services.storage_service import StorageService
from app.services.thumbnail_service import ThumbnailService
from app.utils.jsonutil import dumps_json
from app.utils.paths import ensure_dir


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


@app.get("/", response_class=HTMLResponse)
def generate_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    profiles = crud.list_profiles(session)
    return templates.TemplateResponse(
        "generate.html",
        {
            "request": request,
            "profiles": profiles,
            "provider_names": provider_registry.provider_names(),
        },
    )


@app.post("/generate", response_class=HTMLResponse)
def generate_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    prompt_user: str = Form(...),
    profile_id: int = Form(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    profile = crud.get_profile(session, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    generation = generation_service.create_generation_from_profile(session, profile, prompt_user)
    generation_service.enqueue(background_tasks, generation.id)

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
            "form_action": f"/profiles/{form_profile.id}/update" if form_profile else "/profiles",
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
    session: Session = Depends(get_session),
) -> HTMLResponse:
    page_data = gallery_service.list_assets(
        session,
        page=page,
        profile_name=profile_name or None,
        provider=provider or None,
        status=status or None,
        prompt_query=q or None,
    )
    return templates.TemplateResponse(
        "gallery.html",
        {
            "request": request,
            "page_data": page_data,
            "profile_name": profile_name or "",
            "provider": provider or "",
            "status": status or "",
            "q": q or "",
        },
    )


@app.get("/assets/{asset_id}", response_class=HTMLResponse)
def asset_detail(
    request: Request,
    asset_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    asset = session.scalar(
        select(Asset).options(selectinload(Asset.generation)).where(Asset.id == asset_id)
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
