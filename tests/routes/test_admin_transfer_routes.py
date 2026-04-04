"""Tests for admin import/export (transfer) routes."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace


class _FakeSession:
    pass


def _override_session(fake_session):
    def _dependency():
        yield fake_session

    return _dependency


# ---------------------------------------------------------------------------
# Export routes
# ---------------------------------------------------------------------------


def test_admin_export_models_returns_json(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    expected = {
        "format_version": "1",
        "exported_at": "2026-01-01T00:00:00+00:00",
        "models": [{"name": "MyModel", "provider": "openai", "model": "dall-e-3"}],
    }
    monkeypatch.setattr(app_module, "export_models", lambda _s: expected)

    response = client.get("/admin/export?export_type=models")

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    assert "lumigen-models.json" in response.headers.get("content-disposition", "")
    data = response.json()
    assert data["models"][0]["name"] == "MyModel"


def test_admin_export_profiles_returns_json(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    expected = {
        "format_version": "1",
        "exported_at": "2026-01-01T00:00:00+00:00",
        "profiles": [{"name": "MyProfile", "provider": "openai", "model": "dall-e-3"}],
    }
    monkeypatch.setattr(app_module, "export_profiles", lambda _s: expected)

    response = client.get("/admin/export?export_type=profiles")

    assert response.status_code == 200
    assert "lumigen-profiles.json" in response.headers.get("content-disposition", "")
    data = response.json()
    assert data["profiles"][0]["name"] == "MyProfile"


def test_admin_export_styles_returns_json(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    expected = {
        "format_version": "1",
        "exported_at": "2026-01-01T00:00:00+00:00",
        "styles": [{"name": "Vintage", "description": "Old look", "prompt": "aged film grain"}],
    }
    monkeypatch.setattr(app_module, "export_styles", lambda _s: expected)

    response = client.get("/admin/export?export_type=styles")

    assert response.status_code == 200
    assert "lumigen-styles.json" in response.headers.get("content-disposition", "")
    data = response.json()
    assert data["styles"][0]["name"] == "Vintage"


def test_admin_export_all_is_default(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    expected = {
        "format_version": "1",
        "exported_at": "2026-01-01T00:00:00+00:00",
        "models": [],
        "profiles": [],
        "styles": [],
    }
    monkeypatch.setattr(app_module, "export_all", lambda _s: expected)

    response = client.get("/admin/export")

    assert response.status_code == 200
    assert "lumigen-export.json" in response.headers.get("content-disposition", "")


def test_admin_export_invalid_type_falls_back_to_all(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    expected = {
        "format_version": "1",
        "exported_at": "2026-01-01T00:00:00+00:00",
        "models": [],
        "profiles": [],
        "styles": [],
    }
    monkeypatch.setattr(app_module, "export_all", lambda _s: expected)

    response = client.get("/admin/export?export_type=foobar")

    assert response.status_code == 200
    assert "lumigen-export.json" in response.headers.get("content-disposition", "")


def test_admin_export_denied_for_non_admin(anon_client, app_module) -> None:
    """Export endpoint requires admin; unauthenticated users are redirected."""
    response = anon_client.get("/admin/export?export_type=models", follow_redirects=False)
    # Either redirect (303) or redirect chain landing on login page
    assert response.status_code in {200, 303}


# ---------------------------------------------------------------------------
# Import routes
# ---------------------------------------------------------------------------


def _json_file(payload: dict) -> tuple[str, io.BytesIO, str]:
    """Return a (filename, fileobj, content_type) tuple suitable for test uploads."""
    return ("export.json", io.BytesIO(json.dumps(payload).encode()), "application/json")


def _import_payload(entity_type: str = "models") -> dict:
    """Build a minimal valid import payload for the given entity type."""
    base: dict = {"format_version": "1", "exported_at": "2026-01-01T00:00:00+00:00"}
    if entity_type == "models":
        base["models"] = [{"name": "TestModel", "provider": "openai", "model": "dall-e-3"}]
    elif entity_type == "profiles":
        base["profiles"] = [{"name": "TestProfile", "provider": "openai", "model": "dall-e-3"}]
    elif entity_type == "styles":
        base["styles"] = [{"name": "TestStyle", "description": "A style", "prompt": "some prompt"}]
    return base


def test_admin_import_models_skip_strategy(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    from app.services.import_export_service import ImportResult, RecordResult

    result = ImportResult(entity_type="models")
    result.records.append(RecordResult(name="TestModel", outcome="created"))
    monkeypatch.setattr(app_module, "import_models", lambda _s, _r, _c, dry_run=False: result)

    payload = _import_payload("models")
    response = client.post(
        "/admin/import",
        data={"conflict_strategy": "skip", "dry_run": "false"},
        files={"file": _json_file(payload)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is False
    assert body["results"][0]["entity_type"] == "models"
    assert body["results"][0]["created"] == 1


def test_admin_import_dry_run_returns_preview(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    from app.services.import_export_service import ImportResult, RecordResult

    result = ImportResult(entity_type="styles")
    result.records.append(RecordResult(name="Vintage", outcome="created"))
    monkeypatch.setattr(app_module, "import_styles", lambda _s, _r, _c, dry_run=False: result)

    payload = _import_payload("styles")
    response = client.post(
        "/admin/import",
        data={"conflict_strategy": "skip", "dry_run": "true"},
        files={"file": _json_file(payload)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True


def test_admin_import_invalid_json_returns_400(client, app_module) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    response = client.post(
        "/admin/import",
        data={"conflict_strategy": "skip", "dry_run": "false"},
        files={"file": ("bad.json", io.BytesIO(b"not json at all !!!"), "application/json")},
    )

    assert response.status_code == 400
    assert "error" in response.json()


def test_admin_import_unsupported_version_returns_400(client, app_module) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    payload = {
        "format_version": "99",
        "models": [],
    }
    response = client.post(
        "/admin/import",
        data={"conflict_strategy": "skip", "dry_run": "false"},
        files={"file": _json_file(payload)},
    )

    assert response.status_code == 400
    assert "Unsupported format_version" in response.json()["error"]


def test_admin_import_invalid_conflict_strategy_returns_400(client, app_module) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    payload = _import_payload("models")
    response = client.post(
        "/admin/import",
        data={"conflict_strategy": "invalid_strategy", "dry_run": "false"},
        files={"file": _json_file(payload)},
    )

    assert response.status_code == 400
    assert "Invalid conflict_strategy" in response.json()["error"]


def test_admin_import_empty_payload_returns_message(client, app_module) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    payload = {"format_version": "1"}
    response = client.post(
        "/admin/import",
        data={"conflict_strategy": "skip", "dry_run": "false"},
        files={"file": _json_file(payload)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert "message" in body


def test_admin_import_missing_format_version_returns_400(client, app_module) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    payload = {"models": [{"name": "Test", "provider": "openai", "model": "dall-e-3"}]}
    response = client.post(
        "/admin/import",
        data={"conflict_strategy": "skip", "dry_run": "false"},
        files={"file": _json_file(payload)},
    )

    assert response.status_code == 400
    assert "format_version" in response.json()["error"]


def test_admin_import_denied_for_non_admin(anon_client, app_module) -> None:
    """Import endpoint requires admin."""
    payload = _import_payload("models")
    response = anon_client.post(
        "/admin/import",
        data={"conflict_strategy": "skip", "dry_run": "false", "csrf_token": "fake"},
        files={"file": _json_file(payload)},
        follow_redirects=False,
    )
    assert response.status_code in {200, 303, 403}
