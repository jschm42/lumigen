"""Unit tests for the REST API generation submit endpoint."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.generation import api_generate_submit


@pytest.mark.asyncio
async def test_api_generate_submit_with_overrides():
    """Test that api_generate_submit properly parses overrides from JSON request."""
    with patch("app.api.generation.generation_service.enqueue") as mock_enqueue, \
         patch("app.api.generation.generation_service.create_generation_from_profile") as mock_create, \
         patch("app.db.crud.get_profile") as mock_get_profile:

        mock_profile = MagicMock()
        mock_profile.id = 1
        mock_profile.provider = "standard"
        mock_profile.model = "mock-model"
        mock_profile.model_config_id = None
        mock_profile.params_json = {}
        mock_get_profile.return_value = mock_profile

        mock_gen = MagicMock()
        mock_gen.id = 456
        mock_gen.status = "pending"
        mock_create.return_value = mock_gen

        mock_request = MagicMock()
        mock_request.headers = {"content-type": "application/json"}
        mock_request.json = AsyncMock(return_value={
            "prompt": "Futuristic skyline",
            "negative_prompt": "fog, artifacts",
            "profile_id": 1,
            "aspect_ratio": "16:9",
            "resolution": "2K",
            "width": 1344,
            "height": 768,
            "n_images": 3,
            "seed": 99999,
            "upscale_model": "__none__",
        })

        mock_bg = MagicMock()
        mock_session = MagicMock()

        res = await api_generate_submit(
            request=mock_request,
            background_tasks=mock_bg,
            session=mock_session,
        )

        assert res["job_id"] == 456
        assert res["status"] == "pending"

        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        overrides = kwargs.get("overrides") or {}
        assert overrides["aspect_ratio"] == "16:9"
        assert overrides["resolution"] == "2K"
        assert overrides["width"] == 1344
        assert overrides["height"] == 768
        assert overrides["n_images"] == 3
        assert overrides["seed"] == 99999
        assert overrides["negative_prompt"] == "fog, artifacts"
        assert overrides["upscale_provider"] is None
        mock_enqueue.assert_called_once_with(mock_bg, 456)


@pytest.mark.asyncio
async def test_api_generate_submit_with_multipart_and_input_images():
    """Test that api_generate_submit processes multipart form data with image file uploads."""
    with patch("app.api.generation.generation_service.enqueue") as mock_enqueue, \
         patch("app.api.generation.generation_service.create_generation_from_profile") as mock_create, \
         patch("app.db.crud.get_profile") as mock_get_profile:

        mock_profile = MagicMock()
        mock_profile.id = 2
        mock_profile.provider = "standard"
        mock_profile.model = "test-model"
        mock_profile.model_config_id = None
        mock_profile.params_json = {}
        mock_get_profile.return_value = mock_profile

        mock_gen = MagicMock()
        mock_gen.id = 789
        mock_gen.status = "pending"
        mock_create.return_value = mock_gen

        mock_upload = MagicMock()
        mock_upload.filename = "ref.png"
        mock_upload.content_type = "image/png"
        mock_upload.read = AsyncMock(return_value=b"fake-png-bytes")

        mock_form = MagicMock()
        mock_form.get = lambda k, default=None: {
            "prompt": "An oil painting of a cat",
            "profile_id": "2",
            "aspect_ratio": "1:1",
            "resolution": "1K",
            "seed": "12345",
        }.get(k, default)
        mock_form.getlist = lambda k: [mock_upload] if k == "images" else []

        mock_request = MagicMock()
        mock_request.headers = {"content-type": "multipart/form-data"}
        mock_request.form = AsyncMock(return_value=mock_form)

        mock_bg = MagicMock()
        mock_session = MagicMock()

        res = await api_generate_submit(
            request=mock_request,
            background_tasks=mock_bg,
            session=mock_session,
        )

        assert res["job_id"] == 789
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        overrides = kwargs.get("overrides") or {}
        assert overrides["seed"] == 12345
        assert "input_images" in overrides
        assert len(overrides["input_images"]) == 1
        assert overrides["input_images"][0]["name"] == "ref.png"
        assert overrides["input_images"][0]["mime"] == "image/png"
        mock_enqueue.assert_called_once_with(mock_bg, 789)

