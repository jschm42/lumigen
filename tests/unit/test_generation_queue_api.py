"""Unit tests for the generation queue API endpoints."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.generation import cancel_job, get_queue, retry_job


@pytest.mark.asyncio
async def test_get_queue():
    """Test get_queue correctly partitions active vs recent jobs."""
    gen_running = MagicMock()
    gen_running.id = 1
    gen_running.status = "running"
    gen_running.prompt_user = "A running prompt"
    gen_running.prompt_final = None
    gen_running.model = "test-model"
    gen_running.provider = "fal"
    gen_running.request_snapshot_json = {"chat_session_id": "sess-1", "aspect_ratio": "1:1", "resolution": "1K"}
    gen_running.created_at = None
    gen_running.finished_at = None
    gen_running.error = None
    gen_running.assets = []

    gen_queued = MagicMock()
    gen_queued.id = 2
    gen_queued.status = "queued"
    gen_queued.prompt_user = "A queued prompt"
    gen_queued.prompt_final = None
    gen_queued.model = "test-model"
    gen_queued.provider = "fal"
    gen_queued.request_snapshot_json = {"chat_session_id": "sess-1", "aspect_ratio": "1:1", "resolution": "1K"}
    gen_queued.created_at = None
    gen_queued.finished_at = None
    gen_queued.error = None
    gen_queued.assets = []

    gen_succeeded = MagicMock()
    gen_succeeded.id = 3
    gen_succeeded.status = "succeeded"
    gen_succeeded.prompt_user = "A completed prompt"
    gen_succeeded.prompt_final = None
    gen_succeeded.model = "test-model"
    gen_succeeded.provider = "fal"
    gen_succeeded.request_snapshot_json = {"chat_session_id": "sess-1", "aspect_ratio": "1:1", "resolution": "1K"}
    gen_succeeded.created_at = None
    gen_succeeded.finished_at = None
    gen_succeeded.error = None
    gen_succeeded.assets = []

    mock_session = MagicMock()

    with patch("app.api.generation.crud.list_queue_generations") as mock_list:
        mock_list.return_value = [gen_running, gen_queued, gen_succeeded]

        res = get_queue(session=mock_session)

        assert res["total_active"] == 2
        assert len(res["active"]) == 2
        assert res["active"][0]["id"] == 1
        assert res["active"][0]["status"] == "running"
        assert res["active"][1]["id"] == 2
        assert res["active"][1]["status"] == "queued"
        assert len(res["recent"]) == 1
        assert res["recent"][0]["id"] == 3
        assert res["recent"][0]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_cancel_job():
    """Test cancel_job successfully cancels generation."""
    gen = MagicMock()
    gen.id = 42
    gen.status = "cancelled"

    mock_session = MagicMock()

    with patch("app.api.generation.generation_service.cancel_generation", return_value=gen):
        res = cancel_job(generation_id=42, session=mock_session)
        assert res["success"] is True
        assert res["status"] == "cancelled"
        assert res["job_id"] == 42


@pytest.mark.asyncio
async def test_cancel_job_not_found():
    """Test cancel_job raises 404 when generation is not found."""
    mock_session = MagicMock()

    with patch("app.api.generation.generation_service.cancel_generation", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            cancel_job(generation_id=999, session=mock_session)
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_retry_job():
    """Test retry_job creates a new generation and enqueues it."""
    old_gen = MagicMock()
    old_gen.id = 10

    new_gen = MagicMock()
    new_gen.id = 11
    new_gen.status = "queued"
    new_gen.request_snapshot_json = {"chat_session_id": "sess-abc"}

    mock_session = MagicMock()
    mock_bg = MagicMock()

    with patch("app.api.generation.crud.get_generation", return_value=old_gen), \
         patch("app.api.generation.generation_service.create_generation_from_snapshot", return_value=new_gen) as mock_clone, \
         patch("app.api.generation.generation_service.enqueue") as mock_enqueue:

        res = retry_job(
            generation_id=10,
            background_tasks=mock_bg,
            session=mock_session,
        )

        assert res["job_id"] == 11
        assert res["status"] == "queued"
        assert res["session_token"] == "sess-abc"
        mock_clone.assert_called_once_with(mock_session, old_gen)
        mock_enqueue.assert_called_once_with(mock_bg, 11)


@pytest.mark.asyncio
async def test_retry_job_not_found():
    """Test retry_job raises 404 when original generation is not found."""
    mock_session = MagicMock()
    mock_bg = MagicMock()

    with patch("app.api.generation.crud.get_generation", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            retry_job(
                generation_id=999,
                background_tasks=mock_bg,
                session=mock_session,
            )
        assert exc_info.value.status_code == 404
