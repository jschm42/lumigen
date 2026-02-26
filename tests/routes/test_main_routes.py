from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.providers.base import ProviderError


class _FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.commits = 0
        self._scalar_value = None
        self._scalars_result = []

    def add(self, item) -> None:  # type: ignore[no-untyped-def]
        self.added.append(item)

    def commit(self) -> None:
        self.commits += 1

    def scalar(self, _query):  # type: ignore[no-untyped-def]
        return self._scalar_value

    def scalars(self, _query):  # type: ignore[no-untyped-def]
        return SimpleNamespace(all=lambda: list(self._scalars_result))


def _override_session(fake_session: _FakeSession):
    def _dependency():
        yield fake_session

    return _dependency


def test_provider_models_success(client, app_module, monkeypatch) -> None:
    async def fake_list_models(provider: str) -> list[str]:
        assert provider == "stub"
        return ["model-b", "model-a"]

    monkeypatch.setattr(app_module.provider_registry, "list_models", fake_list_models)

    response = client.get("/api/providers/stub/models")
    payload = response.json()

    assert response.status_code == 200
    assert payload["provider"] == "stub"
    assert payload["models"] == ["model-b", "model-a"]
    assert payload["error"] is None


def test_provider_models_error_returns_payload(client, app_module, monkeypatch) -> None:
    async def failing_list_models(provider: str) -> list[str]:
        _ = provider
        raise ProviderError("provider unavailable")

    monkeypatch.setattr(
        app_module.provider_registry, "list_models", failing_list_models
    )

    response = client.get("/api/providers/openai/models")
    payload = response.json()

    assert response.status_code == 200
    assert payload["provider"] == "openai"
    assert payload["models"] == []
    assert payload["error"] == "provider unavailable"


def test_session_preferences_rejects_invalid_chat_session_id(client) -> None:
    response = client.post(
        "/api/session-preferences",
        json={"chat_session_id": "new", "last_profile_id": 3, "last_thumb_size": "md"},
    )

    assert response.status_code == 400
    assert response.json() == {"success": False, "error": "Invalid session ID"}


def test_session_preferences_success_calls_crud(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    called: dict[str, object] = {}

    def fake_upsert(session, chat_session_id, last_profile_id, last_thumb_size):  # type: ignore[no-untyped-def]
        called["session"] = session
        called["chat_session_id"] = chat_session_id
        called["last_profile_id"] = last_profile_id
        called["last_thumb_size"] = last_thumb_size

    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(
        app_module.crud, "upsert_chat_session_preferences", fake_upsert
    )

    response = client.post(
        "/api/session-preferences",
        json={"chat_session_id": "session:abc", "last_profile_id": 2, "last_thumb_size": "lg"},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "error": None}
    assert called == {
        "session": fake_session,
        "chat_session_id": "session:abc",
        "last_profile_id": 2,
        "last_thumb_size": "lg",
    }


def test_rename_session_updates_generations_and_redirects(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    generation_one = SimpleNamespace(request_snapshot_json={"foo": "bar"})
    generation_two = SimpleNamespace(request_snapshot_json={})

    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(
        app_module,
        "list_generations_for_session_token",
        lambda _session, _token: [generation_one, generation_two],
    )

    response = client.post(
        "/sessions/rename",
        data={
            "session_token": "session:abc",
            "title": "My Session",
            "active_conversation": "session:abc",
            "workspace_view": "chat",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/?workspace_view=chat&conversation=session%3Aabc"
    assert generation_one.request_snapshot_json["chat_session_title"] == "My Session"
    assert generation_two.request_snapshot_json["chat_session_title"] == "My Session"
    assert fake_session.commits == 1
    assert len(fake_session.added) == 2


def test_generate_submit_rejects_non_positive_width(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    profile = SimpleNamespace(provider="stub", upscale_model=None, params_json={})
    monkeypatch.setattr(app_module.crud, "get_profile", lambda _session, _id: profile)

    class _FakeGenerationService:
        def __init__(self) -> None:
            self.create_called = False

        def create_generation_from_profile(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs
            self.create_called = True
            raise AssertionError("Must not be called on validation error")

        def enqueue(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args, kwargs

    fake_generation_service = _FakeGenerationService()
    monkeypatch.setattr(app_module, "generation_service", fake_generation_service)

    response = client.post(
        "/generate",
        data={"prompt_user": "prompt", "profile_id": "1", "width": "0"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "error=Width+must+be+greater+than+0" in response.headers["location"]
    assert fake_generation_service.create_called is False


def test_bulk_set_categories_rejects_missing_assets(client, app_module) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    response = client.post(
        "/assets/bulk-set-categories",
        data={"asset_ids": [], "category_ids": ["1"]},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "No+assets+selected" in response.headers["location"]


def test_bulk_set_categories_rejects_missing_categories(client, app_module) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    response = client.post(
        "/assets/bulk-set-categories",
        data={"asset_ids": ["1"], "category_ids": []},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "Select+at+least+one+category" in response.headers["location"]


def test_bulk_set_categories_updates_assets_and_reports_missing(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    existing_asset = SimpleNamespace(id=1, categories=[])
    fake_session._scalars_result = [existing_asset]
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(
        app_module.crud,
        "list_categories_by_ids",
        lambda _session, _ids: [SimpleNamespace(id=2, name="Portrait")],
    )

    response = client.post(
        "/assets/bulk-set-categories",
        data={"asset_ids": ["1", "2"], "category_ids": ["2"], "return_to": "/gallery?page=2"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "Updated+categories+for+1+asset%28s%29" in response.headers["location"]
    assert "1+asset%28s%29+not+found" in response.headers["location"]
    assert fake_session.commits == 1
    assert len(fake_session.added) == 1


def test_bulk_delete_assets_handles_no_selection(client, app_module) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    response = client.post(
        "/assets/bulk-delete",
        data={"asset_ids": []},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "No+assets+selected" in response.headers["location"]


def test_bulk_delete_assets_reports_deleted_and_failures(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    monkeypatch.setattr(
        app_module.generation_service,
        "delete_asset",
        lambda _session, asset_id: asset_id == 1,
    )

    response = client.post(
        "/assets/bulk-delete",
        data={"asset_ids": ["1", "2"], "return_to": "/gallery?thumb_size=lg"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "Deleted+1+asset%28s%29" in response.headers["location"]
    assert "1+asset%28s%29+could+not+be+deleted" in response.headers["location"]


def test_delete_asset_not_found_returns_404(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.generation_service, "delete_asset", lambda _session, _id: False)

    response = client.post("/assets/77/delete")
    assert response.status_code == 404
    assert response.json()["detail"] == "Asset not found"


def test_delete_generation_not_found_returns_404(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.generation_service, "delete_generation", lambda _session, _id: False)

    response = client.post("/generations/77/delete")
    assert response.status_code == 404
    assert response.json()["detail"] == "Generation not found"


def test_rerun_generation_not_found_returns_404(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.crud, "get_generation", lambda _session, _id: None)

    response = client.post("/generations/5/rerun")
    assert response.status_code == 404
    assert response.json()["detail"] == "Generation not found"


def test_asset_file_missing_asset_returns_404(client, app_module) -> None:
    fake_session = _FakeSession()
    fake_session._scalar_value = None
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    response = client.get("/assets/8/file")
    assert response.status_code == 404
    assert response.json()["detail"] == "Asset not found"


def test_asset_download_and_thumb_missing_file_returns_404(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    fake_session._scalar_value = SimpleNamespace(
        id=9,
        mime="image/png",
        file_path="images/a.png",
        generation=SimpleNamespace(),
    )
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(
        app_module.generation_service,
        "asset_absolute_path",
        lambda _asset, which="file": Path("Z:/definitely-missing-file"),
    )

    download_response = client.get("/assets/9/download")
    thumb_response = client.get("/assets/9/thumb")

    assert download_response.status_code == 404
    assert download_response.json()["detail"] == "Asset file missing"
    assert thumb_response.status_code == 404
    assert thumb_response.json()["detail"] == "Thumbnail missing"
