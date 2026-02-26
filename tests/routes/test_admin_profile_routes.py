from __future__ import annotations

from types import SimpleNamespace


class _FakeSession:
    pass


def _override_session(fake_session: _FakeSession):
    def _dependency():
        yield fake_session

    return _dependency


def test_admin_create_dimension_preset_success(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    called: dict[str, object] = {}

    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    def fake_create(session, name, width, height):  # type: ignore[no-untyped-def]
        called["session"] = session
        called["name"] = name
        called["width"] = width
        called["height"] = height

    monkeypatch.setattr(app_module.crud, "create_dimension_preset", fake_create)

    response = client.post(
        "/admin/dimension-presets",
        data={"name": "Square", "width": "1024", "height": "1024"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin?section=dimensions&message=Saved"
    assert called == {
        "session": fake_session,
        "name": "Square",
        "width": 1024,
        "height": 1024,
    }


def test_admin_update_dimension_preset_not_found_returns_404(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.crud, "get_dimension_preset", lambda _session, _id: None)

    response = client.post(
        "/admin/dimension-presets/21/update",
        data={"name": "Square", "width": "1", "height": "1"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Dimension preset not found"


def test_admin_create_category_validation_redirects_error(client, app_module) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    response = client.post(
        "/admin/categories",
        data={"name": "   "},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "section=categories" in response.headers["location"]
    assert "error=Category+name+is+required" in response.headers["location"]


def test_admin_update_category_success(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    category = SimpleNamespace(id=8, name="Old")
    called: dict[str, object] = {}

    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.crud, "get_category", lambda _session, _id: category)

    def fake_update(session, db_category, name):  # type: ignore[no-untyped-def]
        called["session"] = session
        called["db_category"] = db_category
        called["name"] = name

    monkeypatch.setattr(app_module.crud, "update_category", fake_update)

    response = client.post(
        "/admin/categories/8/update",
        data={"name": " Portrait "},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin?section=categories&message=Saved"
    assert called == {"session": fake_session, "db_category": category, "name": "Portrait"}


def test_admin_create_model_config_rejects_unsupported_provider(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.provider_registry, "provider_names", lambda: ["openai"])

    response = client.post(
        "/admin/model-configs",
        data={"name": "Cfg", "provider": "stub", "model": "m1"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unsupported provider"


def test_admin_create_model_config_requires_api_key_when_custom_enabled(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.provider_registry, "provider_names", lambda: ["stub"])

    response = client.post(
        "/admin/model-configs",
        data={
            "name": "Cfg",
            "provider": "stub",
            "model": "stub-v1",
            "use_custom_api_key": "true",
            "api_key": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "section=models" in response.headers["location"]
    assert "API+key+is+required+when+using+custom+API+key" in response.headers["location"]


def test_admin_update_model_config_keeps_existing_encrypted_key(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    config = SimpleNamespace(id=4, api_key_encrypted="enc-old")
    called: dict[str, object] = {}

    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.provider_registry, "provider_names", lambda: ["stub"])
    monkeypatch.setattr(app_module.crud, "get_model_config", lambda _session, _id: config)

    def fake_update(session, db_config, **kwargs):  # type: ignore[no-untyped-def]
        called["session"] = session
        called["db_config"] = db_config
        called.update(kwargs)

    monkeypatch.setattr(app_module.crud, "update_model_config", fake_update)

    response = client.post(
        "/admin/model-configs/4/update",
        data={
            "name": "Cfg",
            "provider": "stub",
            "model": "stub-v2",
            "use_custom_api_key": "true",
            "api_key": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin?section=models&message=Saved"
    assert called["session"] is fake_session
    assert called["db_config"] is config
    assert called["api_key_encrypted"] == "enc-old"
    assert called["use_custom_api_key"] is True


def test_admin_update_model_config_clear_api_key(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    config = SimpleNamespace(id=4, api_key_encrypted="enc-old")
    called: dict[str, object] = {}

    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.provider_registry, "provider_names", lambda: ["stub"])
    monkeypatch.setattr(app_module.crud, "get_model_config", lambda _session, _id: config)

    def fake_update(session, db_config, **kwargs):  # type: ignore[no-untyped-def]
        called["session"] = session
        called["db_config"] = db_config
        called.update(kwargs)

    monkeypatch.setattr(app_module.crud, "update_model_config", fake_update)

    response = client.post(
        "/admin/model-configs/4/update",
        data={
            "name": "Cfg",
            "provider": "stub",
            "model": "stub-v2",
            "use_custom_api_key": "true",
            "clear_api_key": "true",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin?section=models&message=Saved"
    assert called["api_key_encrypted"] is None


def test_admin_update_enhancement_unsupported_provider_returns_404(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.provider_registry, "provider_names", lambda: ["openai"])

    response = client.post(
        "/admin/enhancement",
        data={"provider": "stub", "model": "x"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unsupported provider"


def test_admin_update_enhancement_clear_existing_key(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    called: dict[str, object] = {}

    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.provider_registry, "provider_names", lambda: ["stub"])
    monkeypatch.setattr(
        app_module.crud,
        "get_enhancement_config",
        lambda _session: SimpleNamespace(api_key_encrypted="enc-old"),
    )

    def fake_upsert(session, **kwargs):  # type: ignore[no-untyped-def]
        called["session"] = session
        called.update(kwargs)

    monkeypatch.setattr(app_module.crud, "upsert_enhancement_config", fake_upsert)

    response = client.post(
        "/admin/enhancement",
        data={"provider": "stub", "model": "improve-v1", "clear_api_key": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin?section=enhancement&message=Saved"
    assert called["session"] is fake_session
    assert called["provider"] == "stub"
    assert called["model"] == "improve-v1"
    assert called["api_key_encrypted"] is None


def test_create_profile_openrouter_ignores_size_and_saves_params(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    called: dict[str, object] = {}

    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(
        app_module.crud,
        "get_model_config",
        lambda _session, _id: SimpleNamespace(id=3, provider="openrouter", model="or-model"),
    )
    monkeypatch.setattr(app_module.crud, "list_categories_by_ids", lambda _session, _ids: [])
    monkeypatch.setattr(app_module, "resolve_default_storage_template_id", lambda _session: None)

    def fake_create_profile(session, **kwargs):  # type: ignore[no-untyped-def]
        called["session"] = session
        called.update(kwargs)

    monkeypatch.setattr(app_module.crud, "create_profile", fake_create_profile)

    response = client.post(
        "/profiles",
        data={
            "name": "Openrouter Profile",
            "model_config_id": "3",
            "width": "0",
            "height": "0",
            "openrouter_aspect_ratio": "1:1",
            "openrouter_image_size": "1K",
            "n_images": "0",
            "output_format": "WEBP",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/profiles"
    assert called["session"] is fake_session
    assert called["provider"] == "openrouter"
    assert called["width"] is None
    assert called["height"] is None
    assert called["n_images"] == 1
    assert called["output_format"] == "webp"
    assert called["params_json"]["image_config"]["aspect_ratio"] == "1:1"
    assert called["params_json"]["image_config"]["image_size"] == "1K"


def test_create_profile_category_mismatch_returns_error_redirect(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(
        app_module.crud,
        "get_model_config",
        lambda _session, _id: SimpleNamespace(id=1, provider="stub", model="stub-v1"),
    )
    monkeypatch.setattr(
        app_module.crud,
        "list_categories_by_ids",
        lambda _session, _ids: [SimpleNamespace(id=1, name="Only One")],
    )

    response = client.post(
        "/profiles",
        data={
            "name": "Profile",
            "model_config_id": "1",
            "category_ids": ["1", "2"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/profiles?create=1&error=")
    assert "selected%20categories%20do%20not%20exist" in response.headers["location"]


def test_update_profile_not_found_returns_404(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.crud, "get_profile", lambda _session, _id: None)

    response = client.post(
        "/profiles/99/update",
        data={"name": "Profile", "model_config_id": "1"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found"


def test_update_profile_success_with_standard_provider(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    called: dict[str, object] = {}

    profile = SimpleNamespace(id=2, params_json={"existing": True})
    model_config = SimpleNamespace(id=9, provider="openai", model="gpt-image-1")

    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.crud, "get_profile", lambda _session, _id: profile)
    monkeypatch.setattr(app_module.crud, "get_model_config", lambda _session, _id: model_config)
    monkeypatch.setattr(
        app_module.crud,
        "list_categories_by_ids",
        lambda _session, _ids: [SimpleNamespace(id=1, name="Portrait")],
    )

    def fake_update(session, db_profile, **kwargs):  # type: ignore[no-untyped-def]
        called["session"] = session
        called["db_profile"] = db_profile
        called.update(kwargs)

    monkeypatch.setattr(app_module.crud, "update_profile", fake_update)
    monkeypatch.setattr(app_module, "validate_profile_upscale_model", lambda _value: None)

    response = client.post(
        "/profiles/2/update",
        data={
            "name": " Updated Profile ",
            "model_config_id": "9",
            "width": "640",
            "height": "832",
            "n_images": "2",
            "seed": "123",
            "output_format": "JPG",
            "category_ids": ["1"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/profiles"
    assert called["session"] is fake_session
    assert called["db_profile"] is profile
    assert called["name"] == "Updated Profile"
    assert called["provider"] == "openai"
    assert called["model"] == "gpt-image-1"
    assert called["width"] == 640
    assert called["height"] == 832
    assert called["n_images"] == 2
    assert called["seed"] == 123
    assert called["output_format"] == "jpg"
    assert called["params_json"]["existing"] is True
    assert len(called["categories"]) == 1


def test_update_profile_validation_error_redirects_edit_dialog(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    profile = SimpleNamespace(id=4, params_json={})

    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.crud, "get_profile", lambda _session, _id: profile)
    monkeypatch.setattr(
        app_module.crud,
        "get_model_config",
        lambda _session, _id: SimpleNamespace(id=4, provider="openai", model="gpt-image-1"),
    )

    response = client.post(
        "/profiles/4/update",
        data={
            "name": "Profile",
            "model_config_id": "4",
            "width": "0",
            "height": "512",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/profiles?edit_id=4&error=")
    assert "Width%20must%20be%20greater%20than%200" in response.headers["location"]
