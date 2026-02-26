from __future__ import annotations

from types import SimpleNamespace

from app.providers.base import ProviderError


class _FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.commits = 0

    def add(self, item) -> None:  # type: ignore[no-untyped-def]
        self.added.append(item)

    def commit(self) -> None:
        self.commits += 1


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
