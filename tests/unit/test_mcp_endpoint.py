"""Tests for the MCP endpoint (/mcp) used by external apps such as TaleWeaver."""
from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

TOKEN = "test-mcp-token"
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


@pytest.fixture
def mcp_app(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Return the reloaded ``app.main`` module with an MCP token configured."""
    monkeypatch.setenv("MCP_API_TOKEN", TOKEN)
    monkeypatch.setenv("MCP_MAX_WAIT_SECONDS", "30")
    module = request.getfixturevalue("app_module")
    # The generation job opens its own sessions; point it at the reloaded test database.
    monkeypatch.setattr("app.services.generation_service.SessionLocal", module.SessionLocal)
    monkeypatch.setattr("app.services.model_config_service.SessionLocal", module.SessionLocal)
    from app.api.generation import model_config_service

    monkeypatch.setattr(model_config_service, "get_default_api_key", lambda provider: "stub-key")
    return module


@pytest.fixture
def mcp_client(mcp_app):
    """Return a test client without a browser session."""
    with TestClient(mcp_app.app) as test_client:
        yield test_client


def _rpc(client: TestClient, method: str, params: dict[str, Any] | None = None, token: str = TOKEN):
    headers = dict(MCP_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return client.post("/mcp", headers=headers, content=json.dumps(body))


def _call_tool(client: TestClient, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = _rpc(client, "tools/call", {"name": name, "arguments": arguments})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "result" in payload, payload
    return payload["result"]


def _seed_stub_model(mcp_app, name: str = "Stub Model") -> int:
    from app.db.models import ModelConfig

    with mcp_app.SessionLocal() as session:
        cfg = ModelConfig(name=name, provider="stub", model="stub-default")
        session.add(cfg)
        session.commit()
        return cfg.id


def test_mcp_endpoint_is_disabled_without_token(app_module):
    with TestClient(app_module.app) as client:
        response = _rpc(client, "tools/list", token="anything")
    assert response.status_code == 404


def test_mcp_endpoint_rejects_wrong_token(mcp_client):
    response = _rpc(mcp_client, "tools/list", token="wrong")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_mcp_endpoint_rejects_missing_token(mcp_client):
    response = _rpc(mcp_client, "tools/list", token="")
    assert response.status_code == 401


def test_mcp_lists_image_tools(mcp_client):
    response = _rpc(mcp_client, "tools/list")
    assert response.status_code == 200, response.text
    names = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert {
        "list_models",
        "list_profiles",
        "list_categories",
        "generate_image",
        "get_generation",
        "get_image",
    } <= names


def test_mcp_generate_image_with_model_and_categories(mcp_app, mcp_client):
    model_id = _seed_stub_model(mcp_app)

    models = _call_tool(mcp_client, "list_models", {})
    assert [m["name"] for m in models["structuredContent"]["models"]] == ["Stub Model"]

    result = _call_tool(
        mcp_client,
        "generate_image",
        {
            "prompt": "A lighthouse in a storm",
            "model": "stub model",
            "categories": ["TaleWeaver"],
            "include_images": "thumbnail",
        },
    )
    assert result.get("isError") is not True, result
    summary = result["structuredContent"]
    assert summary["status"] == "succeeded"
    assert summary["model"] == "stub-default"
    assert summary["model_config_id"] == model_id
    assert summary["images"], summary
    images = [block for block in result["content"] if block["type"] == "image"]
    assert len(images) == len(summary["images"])
    assert images[0]["data"]

    from app.db import crud

    with mcp_app.SessionLocal() as session:
        category = crud.get_category_by_name(session, "TaleWeaver")
        assert category is not None
        generation = crud.get_generation(session, summary["job_id"])
        assert generation.request_snapshot_json["category_ids"] == [category.id]

    image = _call_tool(mcp_client, "get_image", {"asset_id": summary["images"][0]["asset_id"]})
    assert image["content"][0]["type"] == "image"


def test_mcp_generate_image_without_wait_returns_job(mcp_app, mcp_client):
    _seed_stub_model(mcp_app)
    result = _call_tool(
        mcp_client, "generate_image", {"prompt": "A castle", "model": "Stub Model", "wait": False}
    )
    job_id = result["structuredContent"]["job_id"]
    status = _call_tool(mcp_client, "get_generation", {"job_id": job_id})
    assert status["structuredContent"]["job_id"] == job_id


def test_mcp_generate_image_reports_unknown_model(mcp_client):
    result = _call_tool(mcp_client, "generate_image", {"prompt": "A castle", "model": "nope"})
    assert result["isError"] is True
    assert "Unknown model 'nope'" in result["content"][0]["text"]
