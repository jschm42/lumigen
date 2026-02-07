from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Asset, Generation


@dataclass
class GalleryPage:
    items: list[Asset]
    page: int
    page_size: int
    total: int
    pages: int


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

        count_stmt = select(func.count()).select_from(Asset).join(Generation)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = int(session.scalar(count_stmt) or 0)

        stmt = (
            select(Asset)
            .join(Generation)
            .options(selectinload(Asset.generation))
            .order_by(Asset.created_at.desc())
            .offset((safe_page - 1) * safe_page_size)
            .limit(safe_page_size)
        )
        if filters:
            stmt = stmt.where(*filters)

        items = list(session.scalars(stmt).all())
        pages = max(1, math.ceil(total / safe_page_size))
        return GalleryPage(items=items, page=safe_page, page_size=safe_page_size, total=total, pages=pages)
