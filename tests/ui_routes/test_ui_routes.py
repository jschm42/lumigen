from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace


class _ScalarResult:
    def __init__(self, values):  # type: ignore[no-untyped-def]
        self._values = list(values)

    def all(self):  # type: ignore[no-untyped-def]
        return list(self._values)


class _FakeSession:
    def __init__(self, generations=None, scalar_value=None):  # type: ignore[no-untyped-def]
        self._generations = generations or []
        self._scalar_value = scalar_value

    def scalars(self, _query):
        return _ScalarResult(self._generations)

    def scalar(self, _query):  # type: ignore[no-untyped-def]
        return self._scalar_value


def _override_session(fake_session: _FakeSession):
    def _dependency():
        yield fake_session

    return _dependency


def test_generate_page_renders_chat_shell_and_htmx_form(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession(generations=[])
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    monkeypatch.setattr(
        app_module.crud,
        "list_profiles",
        lambda _session: [
            SimpleNamespace(
                id=1,
                name="Default",
                provider="stub",
                model="stub-v1",
                model_config_id=1,
                width=512,
                height=512,
                n_images=1,
                seed=None,
            )
        ],
    )
    monkeypatch.setattr(app_module.crud, "list_dimension_presets", lambda _session: [])
    monkeypatch.setattr(app_module.crud, "get_enhancement_config", lambda _session: None)
    monkeypatch.setattr(app_module.crud, "get_chat_session", lambda _session, _token: None)
    monkeypatch.setattr(
        app_module,
        "build_session_items",
        lambda _session, offset=0, limit=10, max_days=30: (
            [
                {
                    "token": "session:abc",
                    "label": "Session",
                    "subtitle": "",
                    "age": "",
                    "time_category": "today",
                    "latest_created_at": None,
                }
            ],
            False,
        ),
    )

    response = client.get("/?workspace_view=chat&conversation=session:abc")
    body = response.text

    assert response.status_code == 200
    assert 'data-chat-shell' in body
    assert 'hx-post="/generate"' in body
    assert 'data-generation-form' in body
    assert 'data-input-preview' in body
    assert 'Start a new session with a prompt in the input field below.' in body
    assert 'data-load-more-sessions' not in body
    assert 'Settings...' in body
    assert 'data-user-settings-dialog' in body
    assert 'data-user-theme-select' in body
    assert '<option value="system">System</option>' in body


def test_generate_page_keeps_selected_older_session_visible(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession(generations=[])
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    monkeypatch.setattr(
        app_module.crud,
        "list_profiles",
        lambda _session: [
            SimpleNamespace(
                id=1,
                name="Default",
                provider="stub",
                model="stub-v1",
                model_config_id=1,
                width=512,
                height=512,
                n_images=1,
                seed=None,
            )
        ],
    )
    monkeypatch.setattr(app_module.crud, "list_dimension_presets", lambda _session: [])
    monkeypatch.setattr(app_module.crud, "get_enhancement_config", lambda _session: None)
    monkeypatch.setattr(app_module.crud, "get_chat_session", lambda _session, _token: None)

    all_sessions = []
    for idx in range(25):
        token = f"session:{idx:03d}"
        all_sessions.append(
            {
                "token": token,
                "label": f"Session {idx:03d}",
                "subtitle": "",
                "age": "",
                "time_category": "lastyear",
                "time_category_label": "Last year",
                "latest_created_at": None,
            }
        )

    monkeypatch.setattr(
        app_module,
        "build_session_items",
        lambda _session, offset=0, limit=10, max_days=None: (all_sessions, False),
    )
    monkeypatch.setattr(
        app_module,
        "list_generations_for_session_token",
        lambda _session, _token: [],
    )

    response = client.get("/?workspace_view=chat&conversation=session:022")
    body = response.text

    assert response.status_code == 200
    assert "Session 022" in body
    assert "bg-sky-300/20 text-sky-100" in body


def test_job_status_chat_fragment_renders_input_thumbnails_above_prompt(client, app_module) -> None:
    generation = SimpleNamespace(
        id=10,
        status="succeeded",
        prompt_user="Prompt with references",
        profile_name="Default",
        provider="stub",
        model="stub-v1",
        request_snapshot_json={
            "input_images": [
                {"name": "a.png", "mime": "image/png", "b64": "YWJj"},
                {"name": "b.png", "mime": "image/png", "b64": "ZGVm"},
            ]
        },
        error=None,
        failure_sidecar_path=None,
        assets=[],
    )
    fake_session = _FakeSession(scalar_value=generation)
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    response = client.get("/jobs/10?view=chat")
    body = response.text

    assert response.status_code == 200
    assert 'id="chat-generation-10"' in body
    assert 'src="/generations/10/input-images/0"' in body
    assert 'src="/generations/10/input-images/1"' in body
    assert 'Prompt with references' in body


def test_job_status_chat_fragment_renders_add_to_input_button_on_assets(client, app_module) -> None:
    asset = SimpleNamespace(id=42, mime="image/webp", file_path="some/path/image.webp")
    generation = SimpleNamespace(
        id=20,
        status="succeeded",
        prompt_user="A cat on a mat",
        profile_name="Default",
        provider="stub",
        model="stub-v1",
        request_snapshot_json={},
        error=None,
        failure_sidecar_path=None,
        assets=[asset],
    )
    fake_session = _FakeSession(scalar_value=generation)
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    response = client.get("/jobs/20?view=chat")
    body = response.text

    assert response.status_code == 200
    assert 'data-add-to-input="42"' in body
    assert 'add_photo_alternate' in body


def test_generation_input_image_thumbnail_endpoint_returns_image_bytes(client, app_module) -> None:
    generation = SimpleNamespace(
        id=14,
        request_snapshot_json={
            "input_images": [
                {"name": "x.png", "mime": "image/png", "b64": "YWJj"},
            ]
        },
    )
    fake_session = _FakeSession(scalar_value=generation)
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    response = client.get("/generations/14/input-images/0")

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("image/png")
    assert response.content == b"abc"


def test_generate_page_gallery_workspace_renders_embedded_iframe(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession(generations=[])
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    monkeypatch.setattr(app_module.crud, "list_profiles", lambda _session: [])
    monkeypatch.setattr(app_module.crud, "list_dimension_presets", lambda _session: [])
    monkeypatch.setattr(app_module.crud, "get_enhancement_config", lambda _session: None)
    monkeypatch.setattr(app_module.crud, "get_chat_session", lambda _session, _token: None)
    monkeypatch.setattr(
        app_module,
        "build_session_items",
        lambda _session, offset=0, limit=10, max_days=30: ([], False),
    )

    response = client.get("/?workspace_view=gallery&conversation=new")
    body = response.text

    assert response.status_code == 200
    assert 'title="workspace"' in body
    assert 'src="/gallery?embedded=1"' in body


def test_gallery_page_renders_filters_and_empty_state(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    monkeypatch.setattr(
        app_module.gallery_service,
        "list_assets",
        lambda _session, **_kwargs: SimpleNamespace(items=[], page=1, pages=1, total=0),
    )
    monkeypatch.setattr(
        app_module.gallery_service,
        "list_filter_options",
        lambda _session: SimpleNamespace(profile_names=["Default"], providers=["stub"], categories=[]),
    )

    response = client.get("/gallery?thumb_size=lg")
    body = response.text

    assert response.status_code == 200
    assert 'data-gallery-thumb-size="lg"' in body
    assert 'No assets found for current filters.' in body
    assert 'data-gallery-bulk-form' in body
    assert 'name="time_preset"' in body
    assert 'name="date_from"' in body
    assert 'name="date_to"' in body
    assert 'value="today" selected' in body
    assert 'Last 7 days' in body
    assert 'Last 30 days' in body
    assert 'Last 60 days' in body
    assert 'Last 120 days' in body
    assert 'Last year' in body
    assert '>Older<' in body
    assert 'value="custom"' in body


def test_gallery_page_custom_date_range_overrides_preset(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    captured: dict[str, object] = {}

    def _list_assets(_session, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(items=[], page=1, pages=1, total=0)

    monkeypatch.setattr(app_module.gallery_service, "list_assets", _list_assets)
    monkeypatch.setattr(
        app_module.gallery_service,
        "list_filter_options",
        lambda _session: SimpleNamespace(profile_names=["Default"], providers=["stub"], categories=[]),
    )

    response = client.get(
        "/gallery?time_preset=custom&date_from=2026-03-01&date_to=2026-03-02"
    )
    body = response.text

    assert response.status_code == 200
    assert captured.get("created_after") == datetime(2026, 3, 1, 0, 0, 0)
    created_before = captured.get("created_before")
    assert isinstance(created_before, datetime)
    assert created_before.date().isoformat() == "2026-03-02"
    assert 'name="date_from" value="2026-03-01"' in body
    assert 'name="date_to" value="2026-03-02"' in body


def test_admin_page_renders_sections_and_key_warning(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(app_module.settings, "provider_config_key", None)

    monkeypatch.setattr(app_module.crud, "list_model_configs", lambda _session: [])
    monkeypatch.setattr(app_module.crud, "list_dimension_presets", lambda _session: [])
    monkeypatch.setattr(app_module.crud, "list_categories", lambda _session: [])
    monkeypatch.setattr(app_module.crud, "get_enhancement_config", lambda _session: None)

    response = client.get("/admin?section=models")
    body = response.text

    assert response.status_code == 200
    assert "Manage models, presets, categories" in body
    assert "PROVIDER_CONFIG_KEY is missing" in body
    assert "/admin?section=categories" in body


def test_job_cancel_htmx_chat_returns_chat_fragment(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    generation = SimpleNamespace(
        id=9,
        status="running",
        prompt_user="Test prompt",
        profile_name="Default",
        provider="stub",
        model="stub-v1",
        request_snapshot_json={},
        error=None,
        failure_sidecar_path=None,
        assets=[],
    )
    monkeypatch.setattr(
        app_module.generation_service,
        "cancel_generation",
        lambda _session, _generation_id: generation,
    )

    response = client.post(
        "/jobs/9/cancel?view=chat",
        headers={"HX-Request": "true"},
    )
    body = response.text

    assert response.status_code == 200
    assert 'id="chat-generation-9"' in body
    assert 'hx-get="/jobs/9?view=chat"' in body
    assert "Generating..." in body


def test_delete_asset_htmx_returns_flash_fragment(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(
        app_module.generation_service,
        "delete_asset",
        lambda _session, _asset_id: True,
    )

    response = client.post(
        "/assets/21/delete",
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "Asset deleted" in response.text
    assert 'role="alert"' in response.text


def test_delete_generation_htmx_returns_flash_fragment(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(
        app_module.generation_service,
        "delete_generation",
        lambda _session, _generation_id: True,
    )

    response = client.post(
        "/generations/34/delete",
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "Generation deleted" in response.text
    assert 'role="alert"' in response.text


def test_gallery_page_renders_star_controls_and_rating_filters(client, app_module, monkeypatch) -> None:
    asset = SimpleNamespace(
        id=12,
        rating=4,
        generation=SimpleNamespace(profile_name="Profile Hidden", provider="provider-hidden"),
        categories=[],
    )
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    monkeypatch.setattr(
        app_module.gallery_service,
        "list_assets",
        lambda _session, **_kwargs: SimpleNamespace(items=[asset], page=1, pages=1, total=1),
    )
    monkeypatch.setattr(
        app_module.gallery_service,
        "list_filter_options",
        lambda _session: SimpleNamespace(profile_names=[], providers=[], categories=[]),
    )

    response = client.get("/gallery?min_rating=3&thumb_size=md")
    body = response.text

    assert response.status_code == 200
    assert 'name="min_rating"' in body
    assert 'Unrated only' in body
    assert 'action="/assets/12/rating"' in body
    assert 'data-rating-form' in body
    assert 'data-rating-star' in body
    assert 'data-current-rating="4"' in body
    assert 'data-asset-detail-url="/assets/12"' in body
    assert 'data-asset-detail-dialog' in body
    assert 'id="asset-detail-dialog-content"' in body
    assert 'data-asset-detail-close' in body
    assert '>X</button>' in body
    assert 'hx-target="#asset-detail-dialog-content"' in body
    assert 'data-asset-detail-trigger' in body
    assert 'Profile Hidden | provider-hidden' not in body


def test_asset_detail_page_hides_asset_header_and_shows_original_size_button(client, app_module, monkeypatch) -> None:
    asset = SimpleNamespace(
        id=44,
        generation=SimpleNamespace(
            id=5,
            profile_id=1,
            status="succeeded",
            provider="stub",
            model="stub-v1",
            prompt_final="prompt",
            failure_sidecar_path=None,
            profile_snapshot_json={},
            storage_template_snapshot_json={},
            request_snapshot_json={},
        ),
        categories=[],
        width=1024,
        height=1024,
        mime="image/png",
        file_path="images/x.png",
        thumbnail_path=".thumbs/x.webp",
        sidecar_path="images/x.png.json",
        meta_json={},
    )
    fake_session = _FakeSession(scalar_value=asset)
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(
        app_module.crud,
        "list_profiles",
        lambda _session: [SimpleNamespace(id=1, name="Default")],
    )

    response = client.get("/assets/44")
    body = response.text

    assert response.status_code == 200
    assert "Asset #44" not in body
    assert "Details, metadata, and actions for this asset." not in body
    assert 'max-h-[75vh]' in body
    assert 'href="/assets/44/file"' in body
    assert 'Original size' in body


def test_asset_detail_htmx_returns_dialog_fragment_only(client, app_module, monkeypatch) -> None:
    asset = SimpleNamespace(
        id=45,
        generation=SimpleNamespace(
            id=6,
            profile_id=1,
            status="succeeded",
            provider="stub",
            model="stub-v1",
            prompt_final="prompt",
            failure_sidecar_path=None,
            profile_snapshot_json={},
            storage_template_snapshot_json={},
            request_snapshot_json={},
        ),
        categories=[],
        width=1024,
        height=1024,
        mime="image/png",
        file_path="images/y.png",
        thumbnail_path=".thumbs/y.webp",
        sidecar_path="images/y.png.json",
        meta_json={},
    )
    fake_session = _FakeSession(scalar_value=asset)
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )
    monkeypatch.setattr(
        app_module.crud,
        "list_profiles",
        lambda _session: [SimpleNamespace(id=1, name="Default")],
    )

    response = client.get("/assets/45", headers={"HX-Request": "true"})
    body = response.text

    assert response.status_code == 200
    assert "<!doctype html>" not in body
    assert 'id="asset-image-45"' in body
    assert 'href="/assets/45/file"' in body
    assert 'Original size' in body


def test_generate_page_renders_user_menu_popup(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession(generations=[])
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(
        fake_session
    )

    monkeypatch.setattr(app_module.crud, "list_profiles", lambda _session: [])
    monkeypatch.setattr(app_module.crud, "list_dimension_presets", lambda _session: [])
    monkeypatch.setattr(app_module.crud, "get_enhancement_config", lambda _session: None)
    monkeypatch.setattr(app_module.crud, "get_chat_session", lambda _session, _token: None)
    monkeypatch.setattr(
        app_module,
        "build_session_items",
        lambda _session, offset=0, limit=10, max_days=30: ([], False),
    )

    response = client.get("/")
    body = response.text

    assert response.status_code == 200
    assert 'data-user-menu-toggle' in body
    assert 'data-user-menu' in body
    assert 'data-user-menu-container' in body
    assert 'href="/logout"' in body
    assert 'test-admin' in body
    app_version = getattr(app_module, "APP_VERSION", None) or getattr(
        app_module, "app_version", None
    )
    if app_version:
        assert app_version in body
