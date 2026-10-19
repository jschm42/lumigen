from __future__ import annotations

import importlib
import os
import re
import tempfile
from pathlib import Path
from typing import Any

# Point every module-level ``get_settings()`` call at a throw-away directory *before* any
# ``app`` module is imported, so no test can ever read or wipe the developer's ./data/app.db.
_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="lumigen-tests-"))
os.environ.setdefault("DATA_DIR", str(_TEST_DATA_DIR))
os.environ.setdefault("DEFAULT_BASE_DIR", str(_TEST_DATA_DIR / "images"))
os.environ.setdefault("SQLITE_PATH", str(_TEST_DATA_DIR / "app.db"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _isolated_test_database():
    """Create the ORM schema in the throw-away test database once per session."""
    from app.db.engine import init_db

    init_db()
    yield


@pytest.fixture
def app_module(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "data"
    base_dir = data_dir / "images"
    sqlite_path = data_dir / "test.db"

    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("DEFAULT_BASE_DIR", str(base_dir))
    monkeypatch.setenv("SQLITE_PATH", str(sqlite_path))
    monkeypatch.setenv("SESSION_HTTPS_ONLY", "false")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-session-secret")

    get_settings.cache_clear()

    import app.db.engine as engine_module

    importlib.reload(engine_module)

    import app.main as main_module

    main_module = importlib.reload(main_module)
    return main_module


@pytest.fixture
def anon_client(app_module):
    with TestClient(app_module.app) as test_client:
        yield test_client
    app_module.app.dependency_overrides.clear()


def _extract_login_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def _extract_meta_csrf(html: str) -> str:
    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]*)"', html)
    assert match is not None
    return match.group(1)


@pytest.fixture
def client(app_module):
    with TestClient(app_module.app) as test_client:
        with app_module.SessionLocal() as session:
            session.query(app_module.User).delete()
            session.commit()

        login_page = test_client.get("/login")
        login_token = _extract_login_csrf(login_page.text)
        login_response = test_client.post(
            "/login",
            data={
                "username": "test-admin",
                "password": "test-admin-pass-123",
                "csrf_token": login_token,
                "next": "/",
            },
            follow_redirects=False,
        )
        assert login_response.status_code == 303
        assert login_response.headers.get("location") == "/"

        root_response = test_client.get("/")
        csrf_token = _extract_meta_csrf(root_response.text)

        original_post = test_client.post

        def post_with_csrf(url: str, *args: Any, **kwargs: Any):
            data = kwargs.get("data")
            json_payload = kwargs.get("json")
            headers = dict(kwargs.get("headers") or {})

            if json_payload is not None:
                headers.setdefault("X-CSRF-Token", csrf_token)
                kwargs["headers"] = headers
            else:
                if data is None:
                    kwargs["data"] = {"csrf_token": csrf_token}
                elif isinstance(data, dict):
                    if "csrf_token" not in data:
                        data = dict(data)
                        data["csrf_token"] = csrf_token
                        kwargs["data"] = data
            return original_post(url, *args, **kwargs)

        test_client.post = post_with_csrf  # type: ignore[method-assign]
        yield test_client
    app_module.app.dependency_overrides.clear()
