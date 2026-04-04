from __future__ import annotations

from types import SimpleNamespace

import pytest


class _FakeSession:
    pass


def _override_session(fake_session: _FakeSession):
    def _dependency():
        yield fake_session

    return _dependency


def test_admin_create_style_success(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    called: dict = {}

    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    created_style = SimpleNamespace(id=1, name="Cinematic", image_path=None)

    def fake_create(session, **fields):
        called["fields"] = fields
        return created_style

    monkeypatch.setattr(app_module.crud, "create_style", fake_create)

    response = client.post(
        "/admin/styles",
        data={
            "name": "Cinematic",
            "description": "Cinematic look and feel",
            "prompt": "cinematic lighting, dramatic shadows",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "section=styles" in response.headers["location"]
    assert "message=Saved" in response.headers["location"]
    assert called["fields"]["name"] == "Cinematic"
    assert called["fields"]["description"] == "Cinematic look and feel"
    assert called["fields"]["prompt"] == "cinematic lighting, dramatic shadows"


def test_admin_create_style_name_too_long(client, app_module) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    response = client.post(
        "/admin/styles",
        data={
            "name": "A" * 31,
            "description": "desc",
            "prompt": "some prompt",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "section=styles" in response.headers["location"]
    assert "error=" in response.headers["location"]


def test_admin_create_style_empty_name(client, app_module) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    response = client.post(
        "/admin/styles",
        data={
            "name": "   ",
            "description": "desc",
            "prompt": "some prompt",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "section=styles" in response.headers["location"]
    assert "error=" in response.headers["location"]


def test_admin_update_style_success(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    existing_style = SimpleNamespace(id=5, name="Vintage", description="Old style", prompt="old prompt", image_path=None)
    called: dict = {}

    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.crud, "get_style", lambda _s, _id: existing_style)

    def fake_update(session, style, **fields):
        called["style"] = style
        called["fields"] = fields

    monkeypatch.setattr(app_module.crud, "update_style", fake_update)

    response = client.post(
        "/admin/styles/5/update",
        data={
            "name": "Vintage Updated",
            "description": "Updated description",
            "prompt": "new cinematic prompt",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "section=styles" in response.headers["location"]
    assert "message=Saved" in response.headers["location"]
    assert called["style"] is existing_style
    assert called["fields"]["name"] == "Vintage Updated"


def test_admin_update_style_not_found(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.crud, "get_style", lambda _s, _id: None)

    response = client.post(
        "/admin/styles/99/update",
        data={
            "name": "X",
            "description": "desc",
            "prompt": "prompt",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Style not found"


def test_admin_delete_style_success(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    existing_style = SimpleNamespace(id=3, name="Neon", image_path=None)
    deleted = []

    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.crud, "get_style", lambda _s, _id: existing_style)
    monkeypatch.setattr(app_module.crud, "delete_style", lambda _s, style: deleted.append(style))

    response = client.post(
        "/admin/styles/3/delete",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "section=styles" in response.headers["location"]
    assert "message=Deleted" in response.headers["location"]
    assert len(deleted) == 1
    assert deleted[0] is existing_style


def test_admin_delete_style_not_found(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.crud, "get_style", lambda _s, _id: None)

    response = client.post(
        "/admin/styles/99/delete",
        data={},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Style not found"
