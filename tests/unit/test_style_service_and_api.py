"""Unit tests for style service and admin style REST API endpoints."""
from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi import HTTPException
from fastapi.datastructures import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from app.api import admin as admin_api
from app.db import crud
from app.db.models import Base
from app.services import style_service


@pytest.fixture
def db_session():
    """Provide an isolated in-memory SQLite database session."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_ensure_default_styles(db_session: Session):
    """Test that ensure_default_styles seeds styles when empty and does not duplicate."""
    assert len(crud.list_styles(db_session)) == 0

    count = style_service.ensure_default_styles(db_session)
    assert count == len(style_service.DEFAULT_STYLES)
    assert count >= 10

    # Ensure no duplicates when called again
    count_second = style_service.ensure_default_styles(db_session)
    assert count_second == 0

    styles = crud.list_styles(db_session)
    assert len(styles) == count


def test_restore_default_styles(db_session: Session):
    """Test that restore_default_styles can update modified styles and restore missing."""
    style_service.ensure_default_styles(db_session)

    # Modify one of the styles
    cinematic = crud.get_style_by_name(db_session, "Cinematic")
    assert cinematic is not None
    crud.update_style(db_session, cinematic, prompt="custom prompt")

    # Delete one
    pop_art = crud.get_style_by_name(db_session, "Pop Art")
    assert pop_art is not None
    crud.delete_style(db_session, pop_art)

    result = style_service.restore_default_styles(db_session, overwrite=True)
    assert result["created"] == 1  # Pop Art restored
    assert result["updated"] >= 1  # Cinematic prompt restored

    cinematic_restored = crud.get_style_by_name(db_session, "Cinematic")
    assert cinematic_restored is not None
    assert "custom prompt" not in cinematic_restored.prompt


def test_list_admin_styles_no_attribute_error(db_session: Session):
    """Test list_admin_styles serializes Style objects correctly without AttributeError."""
    style_service.ensure_default_styles(db_session)

    styles = admin_api.list_admin_styles(session=db_session)
    assert len(styles) == len(style_service.DEFAULT_STYLES)
    for s in styles:
        assert "id" in s
        assert "name" in s
        assert "description" in s
        assert "prompt_template" in s
        assert "negative_prompt" in s
        assert "image_url" in s


@pytest.mark.asyncio
async def test_save_admin_style_create_and_update(db_session: Session):
    """Test saving (creating and updating) a style preset via JSON request."""
    # 1. Create new style via JSON request
    create_request = Request(
        scope={
            "type": "http",
            "headers": [(b"content-type", b"application/json")],
        }
    )
    create_request._json = {
        "name": "Neon Dream",
        "description": "Dreamy neon colors",
        "prompt_template": "dreamy neon, vibrant glow, soft lighting",
    }

    created = await admin_api.save_admin_style(create_request, session=db_session)
    assert created["id"] is not None
    assert created["name"] == "Neon Dream"
    assert created["prompt_template"] == "dreamy neon, vibrant glow, soft lighting"

    # 2. Update existing style
    update_request = Request(
        scope={
            "type": "http",
            "headers": [(b"content-type", b"application/json")],
        }
    )
    update_request._json = {
        "id": created["id"],
        "name": "Neon Dream V2",
        "description": "Updated description",
        "prompt_template": "dreamy neon, updated glow",
    }

    updated = await admin_api.save_admin_style(update_request, session=db_session)
    assert updated["id"] == created["id"]
    assert updated["name"] == "Neon Dream V2"
    assert updated["description"] == "Updated description"


@pytest.mark.asyncio
async def test_save_admin_style_validation(db_session: Session):
    """Test validation errors in save_admin_style."""
    # Empty name
    req = Request(
        scope={
            "type": "http",
            "headers": [(b"content-type", b"application/json")],
        }
    )
    req._json = {"name": "", "prompt_template": "something"}
    with pytest.raises(HTTPException) as exc:
        await admin_api.save_admin_style(req, session=db_session)
    assert exc.value.status_code == 400

    # Name too long (>30)
    req._json = {"name": "A" * 31, "prompt_template": "something"}
    with pytest.raises(HTTPException) as exc:
        await admin_api.save_admin_style(req, session=db_session)
    assert exc.value.status_code == 400

    # Duplicate name
    crud.create_style(
        db_session, name="UniqueName", description="desc", prompt="prompt"
    )
    req._json = {"name": "UniqueName", "prompt_template": "prompt"}
    with pytest.raises(HTTPException) as exc:
        await admin_api.save_admin_style(req, session=db_session)
    assert exc.value.status_code == 400


def test_delete_admin_style(db_session: Session):
    """Test deleting a style preset."""
    style = crud.create_style(
        db_session, name="ToDelete", description="desc", prompt="prompt"
    )
    res = admin_api.delete_admin_style(style.id, session=db_session)
    assert res["success"] is True

    # 404 for deleted
    with pytest.raises(HTTPException) as exc:
        admin_api.delete_admin_style(style.id, session=db_session)
    assert exc.value.status_code == 404


def test_restore_styles_defaults_api(db_session: Session):
    """Test POST /api/admin/styles/restore-defaults endpoint."""
    res = admin_api.restore_styles_defaults(session=db_session)
    assert res["success"] is True
    assert res["created"] == len(style_service.DEFAULT_STYLES)
    assert "Gesamt" in res["message"]


def test_export_endpoints(db_session: Session):
    """Test GET /api/admin/export/styles and export/all endpoints."""
    style_service.ensure_default_styles(db_session)

    # Styles export JSON
    res_styles = admin_api.export_styles_data(session=db_session)
    assert res_styles.status_code == 200
    assert "attachment;" in res_styles.headers["content-disposition"]
    data = json.loads(res_styles.body.decode("utf-8"))
    assert "styles" in data
    assert len(data["styles"]) == len(style_service.DEFAULT_STYLES)

    # All export JSON
    res_all = admin_api.export_all_data(session=db_session)
    assert res_all.status_code == 200
    all_data = json.loads(res_all.body.decode("utf-8"))
    assert "styles" in all_data
    assert "models" in all_data
    assert "profiles" in all_data

    # Styles ZIP export
    res_zip = admin_api.export_styles_zip_data(session=db_session)
    assert res_zip.status_code == 200
    with zipfile.ZipFile(io.BytesIO(res_zip.body), "r") as zf:
        assert "styles.json" in zf.namelist()


@pytest.mark.asyncio
async def test_import_data_json_and_zip(db_session: Session):
    """Test POST /api/admin/import with JSON and ZIP payloads."""
    # 1. Import from JSON list
    styles_list = [
        {"name": "Imported 1", "description": "Desc 1", "prompt": "Prompt 1"},
        {"name": "Imported 2", "description": "Desc 2", "prompt": "Prompt 2"},
    ]
    json_bytes = json.dumps(styles_list).encode("utf-8")

    upload_file = UploadFile(
        filename="styles.json",
        file=io.BytesIO(json_bytes),
    )

    res = await admin_api.import_data(upload_file, session=db_session)
    assert res["success"] is True
    assert res["imported"]["styles"] == 2

    # 2. Import from ZIP
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zip_payload = {
            "format_version": "1",
            "styles": [
                {
                    "name": "Zip Style 1",
                    "description": "Zip Desc",
                    "prompt": "Zip Prompt",
                }
            ],
        }
        zf.writestr("styles.json", json.dumps(zip_payload))
    zip_bytes = zip_buf.getvalue()

    zip_upload = UploadFile(
        filename="backup.zip",
        file=io.BytesIO(zip_bytes),
    )

    res_zip = await admin_api.import_data(zip_upload, session=db_session)
    assert res_zip["success"] is True
    assert res_zip["imported"]["styles_created"] == 1


def test_style_preview_settings_api(db_session: Session):
    """Test getting and updating the style preview model configuration."""
    # Create test model configs
    m1 = crud.create_model_config(
        db_session, name="Model One", provider="openai", model="dall-e-3"
    )
    m2 = crud.create_model_config(
        db_session, name="Model Two", provider="fal", model="flux-schnell"
    )

    # 1. Initial settings
    res = admin_api.get_style_preview_settings(session=db_session)
    assert "models" in res
    assert len(res["models"]) >= 2
    assert res["model_config_id"] in [m1.id, m2.id]

    # 2. Update to Model Two
    update_res = admin_api.update_style_preview_settings(
        {"model_config_id": m2.id}, session=db_session
    )
    assert update_res["success"] is True
    assert update_res["model_config_id"] == m2.id

    # 3. Read again -> should be Model Two
    res_after = admin_api.get_style_preview_settings(session=db_session)
    assert res_after["model_config_id"] == m2.id
