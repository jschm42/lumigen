"""Unit tests for profile categories assignment in profiles REST API."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import categories as cat_api
from app.api import profiles as profiles_api
from app.db.models import Base


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


def test_profile_create_and_update_with_categories(db_session: Session) -> None:
    """Test assigning categories when creating and updating profiles."""
    # 1. Create two categories
    cat1 = cat_api.create_category({"name": "Portraits"}, session=db_session)
    cat2 = cat_api.create_category({"name": "Landscape"}, session=db_session)
    cat3 = cat_api.create_category({"name": "SciFi"}, session=db_session)

    # 2. Create profile with cat1 and cat2
    payload = {
        "name": "Portrait Master",
        "description": "Studio portrait preset",
        "system_prompt": "high quality portrait",
        "default_aspect_ratio": "4:3",
        "category_ids": [cat1["id"], cat2["id"]],
    }
    created = profiles_api.create_profile(payload, session=db_session)
    assert created["name"] == "Portrait Master"
    assert set(created["category_ids"]) == {cat1["id"], cat2["id"]}
    assert len(created["categories"]) == 2
    assert {c["name"] for c in created["categories"]} == {"Portraits", "Landscape"}

    # 3. Retrieve profile by id
    fetched = profiles_api.get_profile(created["id"], session=db_session)
    assert set(fetched["category_ids"]) == {cat1["id"], cat2["id"]}
    assert len(fetched["categories"]) == 2

    # 4. List profiles
    all_profiles = profiles_api.list_profiles(session=db_session)
    matching = [p for p in all_profiles if p["id"] == created["id"]]
    assert len(matching) == 1
    assert set(matching[0]["category_ids"]) == {cat1["id"], cat2["id"]}

    # 5. Update profile categories to cat3 only
    update_payload = {
        "category_ids": [cat3["id"]],
    }
    updated = profiles_api.update_profile(created["id"], update_payload, session=db_session)
    assert updated["category_ids"] == [cat3["id"]]
    assert len(updated["categories"]) == 1
    assert updated["categories"][0]["name"] == "SciFi"

    # 6. Update profile categories to empty list
    cleared = profiles_api.update_profile(created["id"], {"category_ids": []}, session=db_session)
    assert cleared["category_ids"] == []
    assert cleared["categories"] == []
