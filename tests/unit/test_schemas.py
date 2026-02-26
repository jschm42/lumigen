from __future__ import annotations

import pytest
from pydantic import ValidationError

from app import schemas
from app.schemas.admin import (
    CategoryRequest,
    DimensionPresetRequest,
    EnhancementConfigRequest,
    ModelConfigRequest,
)
from app.schemas.assets import AssetDetailResponse, BulkCategoryRequest, BulkDeleteRequest
from app.schemas.generation import GenerationCreateRequest, GenerationResponse
from app.schemas.session import (
    SessionDeleteRequest,
    SessionPreferencesRequest,
    SessionRenameRequest,
)


def test_admin_dimension_and_category_requests_validate_constraints() -> None:
    dimension = DimensionPresetRequest(name="Square", width=1024, height=1024)
    category = CategoryRequest(name="Portrait")

    assert dimension.name == "Square"
    assert dimension.width == 1024
    assert dimension.height == 1024
    assert category.name == "Portrait"

    with pytest.raises(ValidationError):
        DimensionPresetRequest(name="", width=0, height=512)

    with pytest.raises(ValidationError):
        CategoryRequest(name="x" * 31)


def test_model_and_enhancement_requests_defaults_and_required_fields() -> None:
    model_config = ModelConfigRequest(name="Cfg", provider="openai", model="gpt-image-1")
    enhancement = EnhancementConfigRequest(provider="openai", model="gpt-image-1")

    assert model_config.enhancement_prompt == ""
    assert model_config.api_key == ""
    assert model_config.use_custom_api_key is False
    assert enhancement.api_key == ""
    assert enhancement.clear_api_key is False

    with pytest.raises(ValidationError):
        ModelConfigRequest(name="Cfg", provider="", model="x")

    with pytest.raises(ValidationError):
        EnhancementConfigRequest(provider="stub", model="")


def test_asset_bulk_requests_require_non_empty_lists() -> None:
    category_request = BulkCategoryRequest(asset_ids=[1, 2], category_ids=[7])
    delete_request = BulkDeleteRequest(asset_ids=[3])

    assert category_request.return_to == "/gallery"
    assert delete_request.return_to == "/gallery"

    with pytest.raises(ValidationError):
        BulkCategoryRequest(asset_ids=[], category_ids=[1])

    with pytest.raises(ValidationError):
        BulkDeleteRequest(asset_ids=[])


def test_generation_request_defaults_and_limits() -> None:
    request = GenerationCreateRequest(prompt_user="hello", profile_id=1)

    assert request.conversation == ""
    assert request.upscale_enable is False
    assert request.input_images == []
    assert request.input_image_asset_id == ""

    with pytest.raises(ValidationError):
        GenerationCreateRequest(prompt_user="", profile_id=1)

    with pytest.raises(ValidationError):
        GenerationCreateRequest(prompt_user="ok", profile_id=0)


def test_session_request_models_validate_pattern_and_lengths() -> None:
    rename_request = SessionRenameRequest(session_token="session:1", title="Title")
    delete_request = SessionDeleteRequest(session_token="session:1")
    preferences = SessionPreferencesRequest(
        chat_session_id="session:1",
        last_profile_id=3,
        last_thumb_size="md",
    )

    assert rename_request.workspace_view == "chat"
    assert delete_request.workspace_view == "chat"
    assert preferences.last_thumb_size == "md"

    with pytest.raises(ValidationError):
        SessionRenameRequest(session_token="", title="x")

    with pytest.raises(ValidationError):
        SessionPreferencesRequest(chat_session_id="session:1", last_thumb_size="xl")


def test_response_models_support_attribute_sources() -> None:
    asset_source = type(
        "AssetLike",
        (),
        {
            "id": 5,
            "file_path": "images/test.png",
            "mime": "image/png",
            "width": 512,
            "height": 512,
        },
    )()
    generation_source = type(
        "GenerationLike",
        (),
        {"id": 7, "status": "queued", "prompt": "demo", "created_at": "now"},
    )()

    asset = AssetDetailResponse.model_validate(asset_source)
    generation = GenerationResponse.model_validate(generation_source)

    assert asset.id == 5
    assert generation.status == "queued"


def test_schema_package_exports_expected_symbols() -> None:
    assert "GenerationCreateRequest" in schemas.__all__
    assert "SessionPreferencesRequest" in schemas.__all__
    assert "DimensionPresetRequest" in schemas.__all__
    assert "BulkDeleteRequest" in schemas.__all__

    assert schemas.GenerationCreateRequest is GenerationCreateRequest
    assert schemas.SessionRenameRequest is SessionRenameRequest
    assert schemas.DimensionPresetRequest is DimensionPresetRequest
    assert schemas.BulkCategoryRequest is BulkCategoryRequest
