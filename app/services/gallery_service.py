from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Asset, GalleryFolder, Generation


@dataclass
class GalleryPage:
    items: list[Asset]
    page: int
    page_size: int
    total: int
    pages: int


@dataclass
class GalleryFilterOptions:
    profile_names: list[str]
    providers: list[str]
    statuses: list[str]
    folders: list[GalleryFolder]


class GalleryService:
    def __init__(self, default_page_size: int = 24) -> None:
        self.default_page_size = default_page_size

    def list_assets(
        self,
        session: Session,
        *,
        page: int = 1,
        page_size: Optional[int] = None,
        profile_name: Optional[str] = None,
        provider: Optional[str] = None,
        status: Optional[str] = None,
        prompt_query: Optional[str] = None,
        gallery_folder_id: Optional[int] = None,
        root_only: bool = False,
    ) -> GalleryPage:
        safe_page_size = max(1, min(200, page_size or self.default_page_size))
        safe_page = max(1, page)

        filters = []
        if profile_name:
            filters.append(Generation.profile_name == profile_name)
        if provider:
            filters.append(Generation.provider == provider)
        if status:
            filters.append(Generation.status == status)
        if prompt_query:
            filters.append(Generation.prompt_user.ilike(f"%{prompt_query}%"))
        if root_only:
            filters.append(Asset.gallery_folder_id.is_(None))
        elif gallery_folder_id is not None:
            filters.append(Asset.gallery_folder_id == gallery_folder_id)

        count_stmt = select(func.count()).select_from(Asset).join(Generation)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = int(session.scalar(count_stmt) or 0)

        stmt = (
            select(Asset)
            .join(Generation)
            .options(selectinload(Asset.generation), selectinload(Asset.gallery_folder))
            .order_by(Asset.created_at.desc())
            .offset((safe_page - 1) * safe_page_size)
            .limit(safe_page_size)
        )
        if filters:
            stmt = stmt.where(*filters)

        items = list(session.scalars(stmt).all())
        pages = max(1, math.ceil(total / safe_page_size))
        return GalleryPage(items=items, page=safe_page, page_size=safe_page_size, total=total, pages=pages)

    def list_filter_options(self, session: Session) -> GalleryFilterOptions:
        profile_stmt = (
            select(Generation.profile_name)
            .join(Asset)
            .distinct()
            .order_by(Generation.profile_name.asc())
        )
        provider_stmt = (
            select(Generation.provider)
            .join(Asset)
            .distinct()
            .order_by(Generation.provider.asc())
        )
        status_stmt = (
            select(Generation.status)
            .join(Asset)
            .distinct()
            .order_by(Generation.status.asc())
        )
        folder_stmt = select(GalleryFolder).order_by(GalleryFolder.path.asc())

        profile_names = [item for item in session.scalars(profile_stmt).all() if item]
        providers = [item for item in session.scalars(provider_stmt).all() if item]
        statuses = [item for item in session.scalars(status_stmt).all() if item]
        folders = list(session.scalars(folder_stmt).all())

        return GalleryFilterOptions(
            profile_names=profile_names,
            providers=providers,
            statuses=statuses,
            folders=folders,
        )
