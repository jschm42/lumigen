from __future__ import annotations

from cryptography.fernet import Fernet


class _FakeSession:
    pass


def _override_session(fake_session: _FakeSession):
    def _dependency():
        yield fake_session

    return _dependency


def test_admin_apikeys_section_renders(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.crud, "list_model_configs", lambda _session: [])
    monkeypatch.setattr(app_module.crud, "list_dimension_presets", lambda _session: [])
    monkeypatch.setattr(app_module.crud, "list_categories", lambda _session: [])
    monkeypatch.setattr(app_module.crud, "list_users", lambda _session: [])
    monkeypatch.setattr(app_module.crud, "get_enhancement_config", lambda _session: None)
    monkeypatch.setattr(app_module.crud, "list_provider_api_keys", lambda _session: [])

    response = client.get("/admin?section=apikeys")
    assert response.status_code == 200
    assert "API Keys" in response.text
    assert "section=apikeys" in response.text


def test_admin_update_provider_api_key_saves_and_redirects(
    client, app_module, monkeypatch
) -> None:
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(
        app_module.settings, "provider_config_key", key, raising=False
    )
    monkeypatch.setattr(
        app_module.model_config_service._settings, "provider_config_key", key, raising=False
    )

    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    upserted: dict = {}

    def fake_upsert(session, provider, api_key_encrypted):  # type: ignore[no-untyped-def]
        upserted["provider"] = provider
        upserted["encrypted"] = api_key_encrypted

    monkeypatch.setattr(app_module.crud, "upsert_provider_api_key", fake_upsert)

    response = client.post(
        "/admin/provider-api-keys/openai/update",
        data={"api_key": "my-secret-key"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin?section=apikeys&message=Saved"
    assert upserted["provider"] == "openai"
    assert upserted["encrypted"] != "my-secret-key"


def test_admin_clear_provider_api_key_deletes_and_redirects(
    client, app_module, monkeypatch
) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    deleted: list[str] = []
    monkeypatch.setattr(
        app_module.crud,
        "delete_provider_api_key",
        lambda _session, provider: deleted.append(provider) or True,
    )

    response = client.post(
        "/admin/provider-api-keys/openai/update",
        data={"clear_api_key": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin?section=apikeys&message=Saved"
    assert "openai" in deleted


def test_admin_update_provider_api_key_unknown_provider_returns_404(
    client, app_module
) -> None:
    response = client.post(
        "/admin/provider-api-keys/nonexistent/update",
        data={"api_key": "key"},
        follow_redirects=False,
    )
    assert response.status_code == 404


def test_admin_update_provider_api_key_no_key_no_clear_is_noop(
    client, app_module, monkeypatch
) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    upserted: list = []
    deleted: list = []
    monkeypatch.setattr(app_module.crud, "upsert_provider_api_key", lambda *a: upserted.append(a))
    monkeypatch.setattr(app_module.crud, "delete_provider_api_key", lambda *a: deleted.append(a))

    # Post with empty api_key and no clear_api_key
    response = client.post(
        "/admin/provider-api-keys/openai/update",
        data={"api_key": ""},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert not upserted
    assert not deleted
