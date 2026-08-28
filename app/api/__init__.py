"""Lumigen JSON REST API package."""
from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.assets import router as assets_router
from app.api.auth import router as auth_router
from app.api.categories import router as categories_router
from app.api.generation import router as generation_router
from app.api.models import router as models_router
from app.api.profiles import router as profiles_router
from app.api.sessions import router as sessions_router
from app.api.styles import router as styles_router

api_router = APIRouter(prefix="/api")

api_router.include_router(auth_router)
api_router.include_router(generation_router)
api_router.include_router(sessions_router)
api_router.include_router(assets_router)
api_router.include_router(profiles_router)
api_router.include_router(admin_router)
api_router.include_router(models_router)
api_router.include_router(styles_router)
api_router.include_router(categories_router)

__all__ = ["api_router"]
