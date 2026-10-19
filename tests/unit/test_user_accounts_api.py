"""Tests for account self-service, password reset and admin user management APIs."""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.models import AppSetting, PasswordResetToken, User
from app.services.user_service import hash_reset_token

ADMIN_PASSWORD = "admin-pass-123"
USER_PASSWORD = "user-pass-123"


@pytest.fixture
def api(app_module):
    """Return a fresh TestClient with empty user, token and settings tables."""
    with TestClient(app_module.app) as client:
        with app_module.SessionLocal() as session:
            session.query(PasswordResetToken).delete()
            session.query(AppSetting).delete()
            session.query(User).delete()
            session.commit()
        yield client


def _setup_admin(client: TestClient) -> dict:
    res = client.post("/api/auth/setup", json={"username": "boss", "password": ADMIN_PASSWORD})
    assert res.status_code == 200, res.text
    return res.json()["user"]


def _create_user(client: TestClient, **overrides) -> dict:
    payload = {"username": "alice", "password": USER_PASSWORD, "role": "user", **overrides}
    res = client.post("/api/admin/users", json=payload)
    assert res.status_code == 200, res.text
    return res.json()


def _login(app_module, username: str, password: str) -> TestClient:
    client = TestClient(app_module.app)
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return client


def _extract_reset_token(caplog: pytest.LogCaptureFixture) -> str:
    for record in caplog.records:
        match = re.search(r"reset-password\?token=([A-Za-z0-9_\-]+)", record.getMessage())
        if match:
            return match.group(1)
    raise AssertionError("No reset link was logged")


def test_setup_rejects_short_password(api: TestClient):
    res = api.post("/api/auth/setup", json={"username": "boss", "password": "short"})
    assert res.status_code == 400
    assert "at least 8" in res.json()["detail"]


def test_status_exposes_profile_and_ui_settings(api: TestClient):
    _setup_admin(api)
    status = api.get("/api/auth/status").json()
    assert status["authenticated"] is True
    assert status["user"]["username"] == "boss"
    assert status["user"]["last_login_at"]
    assert status["ui_settings"] == {"show_token_usage": False, "cost_currency": "USD"}
    assert "password_hash" not in status["user"]


def test_account_profile_update_and_conflicts(api: TestClient):
    _setup_admin(api)
    _create_user(api, email="alice@example.com")

    res = api.patch("/api/account", json={"email": "Boss@Example.com", "display_name": "The Boss"})
    assert res.status_code == 200
    assert res.json()["email"] == "boss@example.com"
    assert res.json()["display_name"] == "The Boss"

    conflict = api.patch("/api/account", json={"email": "ALICE@example.com"})
    assert conflict.status_code == 409

    invalid = api.patch("/api/account", json={"email": "not-an-email"})
    assert invalid.status_code == 400

    taken = api.patch("/api/account", json={"username": "Alice"})
    assert taken.status_code == 409


def test_login_with_email(api: TestClient, app_module):
    _setup_admin(api)
    _create_user(api, email="alice@example.com")
    client = _login(app_module, "alice@example.com", USER_PASSWORD)
    assert client.get("/api/account").json()["username"] == "alice"


def test_password_change_invalidates_other_sessions(api: TestClient, app_module):
    _setup_admin(api)
    _create_user(api)
    first = _login(app_module, "alice", USER_PASSWORD)
    second = _login(app_module, "alice", USER_PASSWORD)

    wrong = first.post(
        "/api/account/password",
        json={"current_password": "nope-nope-nope", "new_password": "brand-new-pass"},
    )
    assert wrong.status_code == 400

    ok = first.post(
        "/api/account/password",
        json={"current_password": USER_PASSWORD, "new_password": "brand-new-pass"},
    )
    assert ok.status_code == 200

    assert first.get("/api/account").status_code == 200
    assert second.get("/api/auth/status").json()["authenticated"] is False
    _login(app_module, "alice", "brand-new-pass")


def test_forgot_and_reset_password_flow(api: TestClient, app_module, caplog):
    _setup_admin(api)
    _create_user(api)
    old_session = _login(app_module, "alice", USER_PASSWORD)

    anon = TestClient(app_module.app)
    with caplog.at_level(logging.WARNING):
        res = anon.post("/api/auth/password/forgot", json={"identifier": "alice"})
    assert res.status_code == 200
    token = _extract_reset_token(caplog)

    assert anon.post("/api/auth/password/validate-token", json={"token": token}).json()["valid"]

    weak = anon.post("/api/auth/password/reset", json={"token": token, "new_password": "short"})
    assert weak.status_code == 400

    done = anon.post(
        "/api/auth/password/reset", json={"token": token, "new_password": "reset-pass-456"}
    )
    assert done.status_code == 200

    reused = anon.post(
        "/api/auth/password/reset", json={"token": token, "new_password": "another-pass-789"}
    )
    assert reused.status_code == 400
    assert old_session.get("/api/auth/status").json()["authenticated"] is False
    _login(app_module, "alice", "reset-pass-456")


def test_forgot_password_does_not_reveal_unknown_accounts(api: TestClient, app_module):
    _setup_admin(api)
    anon = TestClient(app_module.app)
    known = anon.post("/api/auth/password/forgot", json={"identifier": "boss"})
    unknown = anon.post("/api/auth/password/forgot", json={"identifier": "ghost"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_expired_reset_token_is_rejected(api: TestClient, app_module):
    admin = _setup_admin(api)
    with app_module.SessionLocal() as session:
        session.add(
            PasswordResetToken(
                user_id=admin["id"],
                token_hash=hash_reset_token("expired-token"),
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        session.commit()
    res = api.post(
        "/api/auth/password/reset", json={"token": "expired-token", "new_password": "whatever-123"}
    )
    assert res.status_code == 400


def test_admin_reset_link_works(api: TestClient, app_module):
    _setup_admin(api)
    user = _create_user(api)
    res = api.post(f"/api/admin/users/{user['id']}/reset-link")
    assert res.status_code == 200
    token = res.json()["reset_url"].split("token=")[1]
    anon = TestClient(app_module.app)
    assert anon.post(
        "/api/auth/password/reset", json={"token": token, "new_password": "from-admin-link"}
    ).status_code == 200


def test_admin_api_requires_admin_role(api: TestClient, app_module):
    _setup_admin(api)
    _create_user(api)
    alice = _login(app_module, "alice", USER_PASSWORD)
    assert alice.get("/api/admin/users").status_code == 403
    assert alice.post(
        "/api/admin/users", json={"username": "mallory", "password": "mallory-pass", "role": "admin"}
    ).status_code == 403
    assert TestClient(app_module.app).get("/api/admin/users").status_code == 401


def test_admin_guards_against_lockout(api: TestClient):
    admin = _setup_admin(api)
    assert api.delete(f"/api/admin/users/{admin['id']}").status_code == 400
    assert api.patch(f"/api/admin/users/{admin['id']}", json={"role": "user"}).status_code == 400
    assert api.patch(f"/api/admin/users/{admin['id']}", json={"is_active": False}).status_code == 400


def test_admin_updates_and_deactivates_user(api: TestClient, app_module):
    _setup_admin(api)
    user = _create_user(api)
    alice = _login(app_module, "alice", USER_PASSWORD)

    res = api.patch(
        f"/api/admin/users/{user['id']}",
        json={"role": "admin", "email": "alice@example.com", "is_active": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["role"] == "admin" and body["is_active"] is False
    assert alice.get("/api/auth/status").json()["authenticated"] is False

    duplicate = api.post("/api/admin/users", json={"username": "ALICE", "password": USER_PASSWORD})
    assert duplicate.status_code == 409
    bad_role = api.post(
        "/api/admin/users", json={"username": "bob", "password": USER_PASSWORD, "role": "root"}
    )
    assert bad_role.status_code == 400


def test_admin_set_password(api: TestClient, app_module):
    _setup_admin(api)
    user = _create_user(api)
    res = api.post(f"/api/admin/users/{user['id']}/password", json={"password": "set-by-admin-1"})
    assert res.status_code == 200
    _login(app_module, "alice", "set-by-admin-1")


def test_ui_settings_roundtrip(api: TestClient):
    _setup_admin(api)
    res = api.put("/api/admin/settings", json={"show_token_usage": True, "unknown": 1})
    assert res.status_code == 200
    assert res.json() == {"show_token_usage": True, "cost_currency": "USD"}
    assert api.get("/api/auth/status").json()["ui_settings"]["show_token_usage"] is True
    assert api.put("/api/admin/settings", json={"show_token_usage": "yes"}).status_code == 400
