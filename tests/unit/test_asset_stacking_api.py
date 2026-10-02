"""Unit tests for asset photo stacking, stack management, and date range filtering."""
from __future__ import annotations

from datetime import datetime, timedelta

try:
    from datetime import UTC
except ImportError:
    UTC = UTC

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import assets as assets_api
from app.db.models import Asset, Base, Generation


@pytest.fixture
def db_session():
    """Provide an isolated in-memory SQLite database session."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def _create_test_asset(session: Session, asset_id: int, created_at: datetime | None = None) -> Asset:
    """Helper to create a generation and asset."""
    gen = Generation(
        id=asset_id,
        profile_name="TestProfile",
        prompt_user=f"Test prompt {asset_id}",
        prompt_final=f"Test prompt {asset_id}",
        provider="openai",
        model="dall-e-3",
        status="succeeded",
        profile_snapshot_json={},
        storage_template_snapshot_json={"base_dir": "."},
        request_snapshot_json={},
        created_at=created_at or datetime.now(UTC),
    )
    session.add(gen)
    session.flush()

    asset = Asset(
        id=asset_id,
        generation_id=gen.id,
        file_path=f"test/asset_{asset_id}.png",
        sidecar_path=f"test/asset_{asset_id}.png.json",
        thumbnail_path=f"test/asset_{asset_id}_thumb.webp",
        width=1024,
        height=1024,
        mime="image/png",
        rating=0,
        meta_json={"prompt": f"Test prompt {asset_id}"},
        created_at=created_at or datetime.now(UTC),
    )
    session.add(asset)
    session.commit()
    return asset


def test_create_and_serialize_stack(db_session: Session):
    """Test grouping multiple assets into a stack."""
    a1 = _create_test_asset(db_session, 1)
    a2 = _create_test_asset(db_session, 2)
    a3 = _create_test_asset(db_session, 3)

    # 1. Require at least 2 assets
    with pytest.raises(HTTPException) as exc_info:
        assets_api.stack_assets({"asset_ids": [a1.id]}, session=db_session)
    assert exc_info.value.status_code == 400

    # 2. Stack 3 assets
    res = assets_api.stack_assets({"asset_ids": [a1.id, a2.id, a3.id]}, session=db_session)
    assert res["success"] is True
    assert res["count"] == 3
    stack_id = res["stack_id"]
    assert stack_id.startswith("stk_")

    # Refresh assets
    db_session.refresh(a1)
    db_session.refresh(a2)
    db_session.refresh(a3)

    assert a1.stack_id == stack_id
    assert a1.stack_order == 0
    assert a2.stack_id == stack_id
    assert a2.stack_order == 1
    assert a3.stack_id == stack_id
    assert a3.stack_order == 2

    # 3. Test get_asset preloading
    single_res = assets_api.get_asset(a1.id, session=db_session)
    assert single_res["stack_id"] == stack_id
    assert single_res["stack_count"] == 3
    assert len(single_res["stack_items"]) == 3


def test_set_stack_cover(db_session: Session):
    """Test setting an asset as the cover of its stack."""
    a1 = _create_test_asset(db_session, 10)
    a2 = _create_test_asset(db_session, 11)
    a3 = _create_test_asset(db_session, 12)

    assets_api.stack_assets({"asset_ids": [a1.id, a2.id, a3.id]}, session=db_session)

    # Set a3 as cover
    cover_res = assets_api.set_stack_cover(a3.id, session=db_session)
    assert cover_res["success"] is True
    assert cover_res["asset_id"] == a3.id

    db_session.refresh(a1)
    db_session.refresh(a2)
    db_session.refresh(a3)

    assert a3.stack_order == 0
    assert a1.stack_order == 1
    assert a2.stack_order == 2


def test_unstack_all_and_partial(db_session: Session):
    """Test dissolving a stack and removing individual assets."""
    a1 = _create_test_asset(db_session, 20)
    a2 = _create_test_asset(db_session, 21)
    a3 = _create_test_asset(db_session, 22)

    stack_res = assets_api.stack_assets({"asset_ids": [a1.id, a2.id, a3.id]}, session=db_session)
    stack_id = stack_res["stack_id"]

    # Remove 1 asset: a1
    assets_api.unstack_assets({"asset_ids": [a1.id]}, session=db_session)
    db_session.refresh(a1)
    db_session.refresh(a2)
    db_session.refresh(a3)

    assert a1.stack_id is None
    assert a2.stack_id == stack_id
    assert a2.stack_order == 0
    assert a3.stack_id == stack_id
    assert a3.stack_order == 1

    # Remove another asset: a2 -> stack now has 1 item left (a3), so it should dissolve automatically
    assets_api.unstack_assets({"asset_ids": [a2.id]}, session=db_session)
    db_session.refresh(a2)
    db_session.refresh(a3)

    assert a2.stack_id is None
    assert a3.stack_id is None


def test_delete_asset_stack_cleanup(db_session: Session):
    """Test that deleting an asset cleanly updates or dissolves its stack."""
    a1 = _create_test_asset(db_session, 30)
    a2 = _create_test_asset(db_session, 31)

    stack_res = assets_api.stack_assets({"asset_ids": [a1.id, a2.id]}, session=db_session)
    stack_id = stack_res["stack_id"]
    assert stack_id

    # Delete cover a1
    del_res = assets_api.delete_asset(a1.id, session=db_session)
    assert del_res["success"] is True

    # Remaining a2 should have dissolved because only 1 asset remains
    db_session.refresh(a2)
    assert a2.stack_id is None


def test_list_assets_date_range_and_collapse_stacks(db_session: Session):
    """Test list_assets with date_from, date_to, and collapse_stacks."""
    base_date = datetime(2026, 5, 10, 12, 0, 0)
    a1 = _create_test_asset(db_session, 40, created_at=base_date)
    a2 = _create_test_asset(db_session, 41, created_at=base_date + timedelta(days=1))
    a3 = _create_test_asset(db_session, 42, created_at=base_date + timedelta(days=5))

    # Stack a1 and a2
    assets_api.stack_assets({"asset_ids": [a2.id, a1.id]}, session=db_session)

    # 1. Collapsed view: only cover (a2) and unstacked (a3) returned -> total 2 items
    res_collapsed = assets_api.list_assets(collapse_stacks=True, session=db_session)
    assert res_collapsed["total"] == 2
    item_ids = [item["id"] for item in res_collapsed["assets"]]
    assert a2.id in item_ids
    assert a3.id in item_ids
    assert a1.id not in item_ids

    # 2. Expanded view (collapse_stacks=False): all 3 returned
    res_expanded = assets_api.list_assets(collapse_stacks=False, session=db_session)
    assert res_expanded["total"] == 3

    # 3. Date range filter: 2026-05-10 to 2026-05-12
    res_dates = assets_api.list_assets(
        date_from="2026-05-10",
        date_to="2026-05-12",
        collapse_stacks=False,
        session=db_session,
    )
    assert res_dates["total"] == 2
    date_ids = [item["id"] for item in res_dates["assets"]]
    assert a1.id in date_ids
    assert a2.id in date_ids
    assert a3.id not in date_ids
