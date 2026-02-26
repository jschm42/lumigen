from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture
def app_module(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "data"
    base_dir = data_dir / "images"
    sqlite_path = data_dir / "test.db"

    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("DEFAULT_BASE_DIR", str(base_dir))
    monkeypatch.setenv("SQLITE_PATH", str(sqlite_path))

    get_settings.cache_clear()

    import app.main as main_module

    main_module = importlib.reload(main_module)
    return main_module


@pytest.fixture
def client(app_module):
    with TestClient(app_module.app) as test_client:
        yield test_client
    app_module.app.dependency_overrides.clear()
