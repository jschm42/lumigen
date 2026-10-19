"""Tests for gallery facets, model filter, ZIP download, UTC timestamps and filter presets."""
from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import account as account_api
from app.api import assets as assets_api
from app.db.models import Asset, Base, Generation, User


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


def _add_asset(
    session: Session, asset_id: int, base_dir: Path, *, provider: str, model: str, write_file: bool = True
) -> Asset:
    gen = Generation(
        id=asset_id,
        profile_name=f"Profile {asset_id % 2}",
        prompt_user=f"Prompt {asset_id}",
        prompt_final=f"Prompt {asset_id}",
        provider=provider,
        model=model,
        status="succeeded",
        profile_snapshot_json={},
        storage_template_snapshot_json={"base_dir": base_dir.as_posix()},
        request_snapshot_json={},
        created_at=datetime.now(UTC),
    )
    session.add(gen)
    session.flush()
    rel = f"img/asset_{asset_id}.png"
    if write_file:
        target = base_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"png-bytes-{asset_id}".encode())
    asset = Asset(
        id=asset_id,
        generation_id=gen.id,
        file_path=rel,
        sidecar_path=f"{rel}.json",
        thumbnail_path=f"img/asset_{asset_id}_thumb.webp",
        width=512,
        height=512,
        mime="image/png",
        rating=0,
        meta_json={},
        created_at=datetime.now(UTC),
    )
    session.add(asset)
    session.commit()
    return asset


def _list(session: Session, **overrides):
    params = {
        "q": "",
        "profile_name": "",
        "provider": "",
        "model": "",
        "min_rating": None,
        "unrated": False,
        "time_preset": "",
        "date_from": "",
        "date_to": "",
        "category_ids": "",
        "artbook_token": "",
        "collapse_stacks": True,
        "page": 1,
        "page_size": 40,
    }
    params.update(overrides)
    return assets_api.list_assets(session=session, **params)


def test_facets_and_model_filter(db_session: Session, tmp_path: Path):
    _add_asset(db_session, 1, tmp_path, provider="openai", model="gpt-image-1")
    _add_asset(db_session, 2, tmp_path, provider="bfl", model="flux-2-pro")
    _add_asset(db_session, 3, tmp_path, provider="bfl", model="flux-2-pro")

    facets = assets_api.get_asset_facets(session=db_session)
    assert facets["providers"] == ["bfl", "openai"]
    assert facets["models"] == ["flux-2-pro", "gpt-image-1"]
    assert facets["profiles"] == ["Profile 0", "Profile 1"]

    result = _list(db_session, model="flux-2-pro")
    assert result["total"] == 2
    assert {a["id"] for a in result["assets"]} == {2, 3}


def test_asset_timestamps_are_utc(db_session: Session, tmp_path: Path):
    _add_asset(db_session, 1, tmp_path, provider="openai", model="m")
    created = _list(db_session)["assets"][0]["created_at"]
    assert created.endswith("+00:00")


def test_today_filter_includes_fresh_assets(db_session: Session, tmp_path: Path):
    _add_asset(db_session, 1, tmp_path, provider="openai", model="m")
    assert _list(db_session, time_preset="today")["total"] == 1


def test_download_zip_contains_existing_files(db_session: Session, tmp_path: Path, monkeypatch):
    from app.api import generation as generation_api

    monkeypatch.setattr(
        generation_api.generation_service,
        "_base_dir_from_snapshot",
        lambda snapshot: Path(snapshot["base_dir"]),
    )
    _add_asset(db_session, 1, tmp_path, provider="openai", model="m")
    _add_asset(db_session, 2, tmp_path, provider="openai", model="m")
    _add_asset(db_session, 3, tmp_path, provider="openai", model="m", write_file=False)

    response = assets_api.download_assets_zip({"asset_ids": [1, 2, 3, 999]}, session=db_session)
    assert response.media_type == "application/zip"
    assert "attachment" in response.headers["content-disposition"]

    import asyncio

    async def collect() -> bytes:
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode())
        return b"".join(chunks)

    data = asyncio.run(collect())
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = sorted(archive.namelist())
        assert names == ["1-asset_1.png", "2-asset_2.png"]
        assert archive.read("1-asset_1.png") == b"png-bytes-1"


def test_download_zip_validation(db_session: Session):
    with pytest.raises(HTTPException) as empty:
        assets_api.download_assets_zip({"asset_ids": []}, session=db_session)
    assert empty.value.status_code == 400
    with pytest.raises(HTTPException) as too_many:
        assets_api.download_assets_zip(
            {"asset_ids": list(range(assets_api.MAX_ZIP_ASSETS + 1))}, session=db_session
        )
    assert too_many.value.status_code == 400
    with pytest.raises(HTTPException) as missing:
        assets_api.download_assets_zip({"asset_ids": [42]}, session=db_session)
    assert missing.value.status_code == 404


def test_gallery_presets_roundtrip(db_session: Session):
    user = User(username="jean", password_hash="x", role="user", is_active=True)
    other = User(username="alice", password_hash="x", role="user", is_active=True)
    db_session.add_all([user, other])
    db_session.commit()

    assert account_api.get_gallery_presets(user=user, session=db_session) == []
    saved = account_api.save_gallery_presets(
        [{"id": "p1", "name": "Best FLUX", "filters": {"provider": "bfl", "min_rating": 4, "evil": 1}}],
        user=user,
        session=db_session,
    )
    assert saved == [{"id": "p1", "name": "Best FLUX", "filters": {"provider": "bfl", "min_rating": 4}}]
    assert account_api.get_gallery_presets(user=user, session=db_session) == saved
    assert account_api.get_gallery_presets(user=other, session=db_session) == []

    with pytest.raises(HTTPException):
        account_api.save_gallery_presets([{"name": ""}], user=user, session=db_session)
    with pytest.raises(HTTPException):
        account_api.save_gallery_presets(
            [{"name": f"p{i}"} for i in range(account_api.MAX_GALLERY_PRESETS + 1)],
            user=user,
            session=db_session,
        )
