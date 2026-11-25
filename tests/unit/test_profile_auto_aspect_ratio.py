"""Profiles without a format ("Auto") leave the aspect ratio to the prompt."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import profiles as profiles_api
from app.api.generation import api_generate_submit
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


def test_profile_auto_format_is_stored_as_none_and_returned_empty(db_session: Session) -> None:
    created = profiles_api.create_profile(
        {"name": "Story", "default_aspect_ratio": ""}, session=db_session
    )
    assert created["default_aspect_ratio"] == ""
    assert profiles_api.crud.get_profile(db_session, created["id"]).aspect_ratio is None

    updated = profiles_api.update_profile(
        created["id"], {"default_aspect_ratio": "16:9"}, session=db_session
    )
    assert updated["default_aspect_ratio"] == "16:9"

    kept = profiles_api.update_profile(created["id"], {"name": "Story 2"}, session=db_session)
    assert kept["default_aspect_ratio"] == "16:9"

    cleared = profiles_api.update_profile(
        created["id"], {"default_aspect_ratio": ""}, session=db_session
    )
    assert cleared["default_aspect_ratio"] == ""


@pytest.mark.asyncio
async def test_generate_without_aspect_ratio_sends_no_override():
    """The route must not force 1:1 when the client sends no aspect ratio."""
    with patch("app.api.generation.generation_service.enqueue"), \
         patch("app.api.generation.generation_service.create_generation_from_profile") as mock_create, \
         patch("app.db.crud.get_profile") as mock_get_profile:
        profile = MagicMock(id=1, provider="standard", model="m", model_config_id=None, params_json={})
        mock_get_profile.return_value = profile
        mock_create.return_value = MagicMock(id=5, status="queued")

        request = MagicMock()
        request.headers = {"content-type": "application/json"}
        request.json = AsyncMock(return_value={"prompt": "A wide valley", "profile_id": 1})

        await api_generate_submit(request=request, background_tasks=MagicMock(), session=MagicMock())

    overrides = mock_create.call_args.kwargs["overrides"]
    assert "aspect_ratio" not in overrides
