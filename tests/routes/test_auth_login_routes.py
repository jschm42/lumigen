from __future__ import annotations

import re
import uuid


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def _extract_meta_csrf_token(html: str) -> str:
    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]*)"', html)
    assert match is not None
    return match.group(1)


def test_login_page_shows_onboarding_when_no_users(anon_client, app_module) -> None:
    with app_module.SessionLocal() as session:
        session.query(app_module.User).delete()
        session.commit()

    response = anon_client.get("/login")

    assert response.status_code == 200
    assert "Ersteinrichtung" in response.text


def test_onboarding_creates_first_admin_and_allows_admin_access(anon_client, app_module) -> None:
    with app_module.SessionLocal() as session:
        session.query(app_module.User).delete()
        session.commit()

    login_page = anon_client.get("/login")
    token = _extract_csrf_token(login_page.text)

    response = anon_client.post(
        "/login",
        data={
            "username": "admin",
            "password": "supersecure123",
            "csrf_token": token,
            "next": "/",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"

    admin_response = anon_client.get("/admin", follow_redirects=False)
    assert admin_response.status_code == 200
    assert "Admin" in admin_response.text


def test_user_role_cannot_access_admin_page(anon_client, app_module) -> None:
    admin_name = f"admin-{uuid.uuid4().hex[:8]}"
    user_name = f"user-{uuid.uuid4().hex[:8]}"

    with app_module.SessionLocal() as session:
        app_module.crud.create_user(
            session,
            username=admin_name,
            password_hash=app_module.auth_service.hash_password("admin-pass-123"),
            role="admin",
            is_active=True,
        )
        app_module.crud.create_user(
            session,
            username=user_name,
            password_hash=app_module.auth_service.hash_password("user-pass-123"),
            role="user",
            is_active=True,
        )

    login_page = anon_client.get("/login")
    token = _extract_csrf_token(login_page.text)
    login_response = anon_client.post(
        "/login",
        data={
            "username": user_name,
            "password": "user-pass-123",
            "csrf_token": token,
            "next": "/",
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 303

    admin_response = anon_client.get("/admin", follow_redirects=False)
    assert admin_response.status_code == 303
    assert "error=Admin+access+required" in admin_response.headers["location"]


def test_admin_can_reset_onboarding_when_enabled(client, app_module) -> None:
    app_module.settings.auth_allow_onboarding_reset = True

    page = client.get("/admin?section=users")
    token = _extract_meta_csrf_token(page.text)

    response = client.post(
        "/admin/dev/reset-onboarding",
        data={"csrf_token": token},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")

    with app_module.SessionLocal() as session:
        assert app_module.crud.count_users(session) == 0
