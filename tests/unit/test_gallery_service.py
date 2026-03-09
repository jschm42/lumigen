from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Asset, Base, Category, Generation
from app.services.gallery_service import GalleryService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with SessionLocal() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def _add_generation_with_asset(
    session,
    *,
    generation_id: int,
    profile_name: str,
    provider: str,
    status: str,
    prompt_user: str,
    category: Category | None = None,
    rating: int | None = None,
    created_at: datetime | None = None,
):
    created_value = created_at or (datetime.utcnow() + timedelta(seconds=generation_id))
    generation = Generation(
        id=generation_id,
        profile_id=None,
        profile_name=profile_name,
        prompt_user=prompt_user,
        prompt_final=prompt_user,
        provider=provider,
        model="model",
        status=status,
        error=None,
        profile_snapshot_json={},
        storage_template_snapshot_json={"base_dir": "."},
        request_snapshot_json={},
        failure_sidecar_path=None,
        created_at=created_value,
    )
    asset = Asset(
        generation_id=generation_id,
        file_path=f"asset-{generation_id}.png",
        sidecar_path=f"asset-{generation_id}.png.json",
        thumbnail_path=f".thumbs/asset-{generation_id}.webp",
        width=64,
        height=64,
        mime="image/png",
        rating=rating,
        meta_json={},
        created_at=created_value,
    )
    if category is not None:
        asset.categories = [category]
    generation.assets = [asset]
    session.add(generation)
    session.commit()


def test_list_assets_filters_and_paginates(db_session) -> None:
    cat_anim = Category(name="Anime")
    cat_real = Category(name="Realism")
    db_session.add_all([cat_anim, cat_real])
    db_session.commit()

    _add_generation_with_asset(
        db_session,
        generation_id=1,
        profile_name="P1",
        provider="openai",
        status="succeeded",
        prompt_user="cat portrait",
        category=cat_anim,
    )
    _add_generation_with_asset(
        db_session,
        generation_id=2,
        profile_name="P2",
        provider="openrouter",
        status="failed",
        prompt_user="city skyline",
        category=cat_real,
    )
    _add_generation_with_asset(
        db_session,
        generation_id=3,
        profile_name="P1",
        provider="openai",
        status="succeeded",
        prompt_user="cat in rain",
        category=cat_anim,
    )

    service = GalleryService(default_page_size=2)

    page1 = service.list_assets(db_session, page=1)
    assert page1.page == 1
    assert page1.page_size == 2
    assert page1.total == 3
    assert page1.pages == 2
    assert len(page1.items) == 2

    filtered = service.list_assets(
        db_session,
        page=1,
        page_size=10,
        profile_name="P1",
        provider="openai",
        prompt_query="cat",
        category_ids=[cat_anim.id],
    )
    assert filtered.total == 2
    assert filtered.pages == 1
    assert len(filtered.items) == 2
    assert all(item.generation.profile_name == "P1" for item in filtered.items)

    filtered_none = service.list_assets(
        db_session,
        page=1,
        page_size=10,
        category_ids=[9999],
    )
    assert filtered_none.total == 0
    assert filtered_none.pages == 1
    assert filtered_none.items == []


def test_list_assets_applies_page_size_and_page_bounds(db_session) -> None:
    _add_generation_with_asset(
        db_session,
        generation_id=11,
        profile_name="P",
        provider="stub",
        status="succeeded",
        prompt_user="hello",
    )
    service = GalleryService(default_page_size=24)

    low = service.list_assets(db_session, page=0, page_size=0)
    assert low.page == 1
    assert low.page_size == 24

    high = service.list_assets(db_session, page=1, page_size=500)
    assert high.page_size == 200


def test_list_filter_options_returns_distinct_sorted_values(db_session) -> None:
    cat_b = Category(name="B")
    cat_a = Category(name="A")
    db_session.add_all([cat_b, cat_a])
    db_session.commit()

    _add_generation_with_asset(
        db_session,
        generation_id=21,
        profile_name="Profile Z",
        provider="openrouter",
        status="failed",
        prompt_user="x",
        category=cat_a,
    )
    _add_generation_with_asset(
        db_session,
        generation_id=22,
        profile_name="Profile A",
        provider="openai",
        status="succeeded",
        prompt_user="y",
        category=cat_b,
    )
    _add_generation_with_asset(
        db_session,
        generation_id=23,
        profile_name="Profile A",
        provider="openai",
        status="succeeded",
        prompt_user="z",
        category=cat_b,
    )

    options = GalleryService().list_filter_options(db_session)
    assert options.profile_names == ["Profile A", "Profile Z"]
    assert options.providers == ["openai", "openrouter"]
    assert options.statuses == ["failed", "succeeded"]
    assert [item.name for item in options.categories] == ["A", "B"]


def test_list_assets_filters_by_min_rating_and_unrated(db_session) -> None:
    _add_generation_with_asset(
        db_session,
        generation_id=31,
        profile_name="P",
        provider="stub",
        status="succeeded",
        prompt_user="one",
        rating=1,
    )
    _add_generation_with_asset(
        db_session,
        generation_id=32,
        profile_name="P",
        provider="stub",
        status="succeeded",
        prompt_user="three",
        rating=3,
    )
    _add_generation_with_asset(
        db_session,
        generation_id=33,
        profile_name="P",
        provider="stub",
        status="succeeded",
        prompt_user="none",
        rating=None,
    )

    service = GalleryService(default_page_size=20)

    min_rating = service.list_assets(db_session, min_rating=2)
    assert min_rating.total == 1
    assert len(min_rating.items) == 1
    assert min_rating.items[0].rating == 3

    unrated = service.list_assets(db_session, unrated_only=True)
    assert unrated.total == 1
    assert len(unrated.items) == 1
    assert unrated.items[0].rating is None


def test_list_assets_filters_by_created_at_range(db_session) -> None:
    now = datetime.utcnow()
    old_time = now - timedelta(days=20)
    week_time = now - timedelta(days=5)
    today_time = now - timedelta(hours=2)

    _add_generation_with_asset(
        db_session,
        generation_id=41,
        profile_name="P",
        provider="stub",
        status="succeeded",
        prompt_user="old",
        created_at=old_time,
    )
    _add_generation_with_asset(
        db_session,
        generation_id=42,
        profile_name="P",
        provider="stub",
        status="succeeded",
        prompt_user="week",
        created_at=week_time,
    )
    _add_generation_with_asset(
        db_session,
        generation_id=43,
        profile_name="P",
        provider="stub",
        status="succeeded",
        prompt_user="today",
        created_at=today_time,
    )

    service = GalleryService(default_page_size=50)

    last_week = service.list_assets(db_session, created_after=now - timedelta(days=7))
    assert last_week.total == 2
    assert {item.generation.prompt_user for item in last_week.items} == {"week", "today"}

    custom_window = service.list_assets(
        db_session,
        created_after=now - timedelta(days=6),
        created_before=now - timedelta(days=1),
    )
    assert custom_window.total == 1
    assert len(custom_window.items) == 1
    assert custom_window.items[0].generation.prompt_user == "week"
