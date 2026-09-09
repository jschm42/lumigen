"""Unit tests for categories REST API endpoints and asset bulk categorization."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import assets as assets_api
from app.api import categories as cat_api
from app.db import crud
from app.db.models import Asset, Base, Category, Generation, Profile, StorageTemplate


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


def test_categories_crud_endpoints(db_session: Session):

    """Test category listing, creating, updating, and deleting via API handlers."""
    # 1. Initially empty
    cats = cat_api.list_categories(session=db_session)
    assert isinstance(cats, list)

    # 2. Create Category
    res = cat_api.create_category({"name": "Cyberpunk"}, session=db_session)
    assert res["name"] == "Cyberpunk"
    assert res["id"] is not None
    cat_id = res["id"]

    # 3. Duplicate create should fail
    with pytest.raises(HTTPException) as exc_info:
        cat_api.create_category({"name": "Cyberpunk"}, session=db_session)
    assert exc_info.value.status_code == 409

    # 4. Update Category
    updated = cat_api.update_category(cat_id, {"name": "Sci-Fi"}, session=db_session)
    assert updated["name"] == "Sci-Fi"
    assert updated["id"] == cat_id

    # 5. List Categories contains updated
    listed = cat_api.list_categories(session=db_session)
    assert any(c["id"] == cat_id and c["name"] == "Sci-Fi" for c in listed)

    # 6. Delete Category
    del_res = cat_api.delete_category(cat_id, session=db_session)
    assert del_res["success"] is True

    # 7. Delete non-existent raises 404
    with pytest.raises(HTTPException) as exc_del:
        cat_api.delete_category(cat_id, session=db_session)
    assert exc_del.value.status_code == 404


def test_bulk_categorize_and_single_asset(db_session: Session):
    """Test bulk categorization and single asset categorization handlers."""
    # Create test categories
    c1 = crud.create_category(db_session, name="Portrait")
    c2 = crud.create_category(db_session, name="Landscape")

    # Create dummy storage template & profile
    st = StorageTemplate(name="test-tmpl", base_dir="/tmp", template="{id}.png")
    db_session.add(st)
    db_session.commit()

    prof = Profile(name="TestProfile", storage_template_id=st.id)
    db_session.add(prof)
    db_session.commit()

    gen = Generation(
        profile_id=prof.id,
        profile_name="TestProfile",
        prompt_user="A cat",
        prompt_final="A cat",
        provider="dummy",
        model="dummy-model",
        profile_snapshot_json={},
        request_snapshot_json={},
        storage_template_snapshot_json={},
    )

    db_session.add(gen)
    db_session.commit()




    a1 = Asset(
        generation_id=gen.id,
        file_path="/tmp/test1.png",
        sidecar_path="/tmp/test1.json",
        thumbnail_path="/tmp/test1_thumb.png",
        width=512,
        height=512,
        mime="image/png",
    )
    a2 = Asset(
        generation_id=gen.id,
        file_path="/tmp/test2.png",
        sidecar_path="/tmp/test2.json",
        thumbnail_path="/tmp/test2_thumb.png",
        width=512,
        height=512,
        mime="image/png",
    )
    db_session.add_all([a1, a2])
    db_session.commit()

    # 1. Bulk categorize with replace mode
    assets_api.bulk_categorize_assets(
        {"asset_ids": [a1.id, a2.id], "category_ids": [c1.id], "mode": "replace"},
        session=db_session,
    )
    assert len(a1.categories) == 1
    assert a1.categories[0].name == "Portrait"
    assert len(a2.categories) == 1
    assert a2.categories[0].name == "Portrait"

    # 2. Bulk categorize with append mode
    assets_api.bulk_categorize_assets(
        {"asset_ids": [a1.id], "category_ids": [c2.id], "mode": "append"},
        session=db_session,
    )
    assert len(a1.categories) == 2
    assert {c.id for c in a1.categories} == {c1.id, c2.id}

    # 3. Single asset categories update
    assets_api.update_asset_categories(
        a1.id,
        {"category_ids": [c2.id]},
        session=db_session,
    )
    assert len(a1.categories) == 1
    assert a1.categories[0].name == "Landscape"

    # 4. Check category counts in list_categories
    cats = cat_api.list_categories(session=db_session)
    c2_data = next(c for c in cats if c["id"] == c2.id)
    assert c2_data["asset_count"] >= 1
