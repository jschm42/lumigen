from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi.responses import Response as FastAPIResponse
from PIL import Image


def _FakeSession():
    class FakeSession:
        def __init__(self):
            self.added = []
            self.committed = False
            self.deleted = []

        def add(self, item):
            self.added.append(item)

        def commit(self):
            self.committed = True

        def delete(self, item):
            self.deleted.append(item)

        def scalar(self, query):
            # Fallback mock method
            return None

        def scalars(self, query):
            class FakeResult:
                def all(self):
                    return []
            return FakeResult()

        def refresh(self, item):
            pass

    return FakeSession()

def _override_session(fake_session):
    def _dependency():
        yield fake_session
    return _dependency

def test_generate_page_renders_artbook_title(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    # Mock DB functions to avoid DB calls
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
                params_json={},
            )
        ],
    )
    monkeypatch.setattr(app_module.crud, "list_dimension_presets", lambda *a: [])
    monkeypatch.setattr(app_module.crud, "list_styles", lambda *a: [])
    monkeypatch.setattr(app_module.crud, "get_enhancement_config", lambda *a: None)

    # Mock build_session_items to return a predefined session
    session_data = {
        "token": "session-123",
        "profile_label": "My Artbook",
        "custom_title": "Gorgeous Title",
        "latest_generation_id": 1,
        "started_at": None,
        "latest_created_at": None,
        "latest_status": "succeeded",
        "asset_ids": set(),
        "default_cover_asset_id": None,
        "custom_cover_asset_id": None,
        "cover_thumb_url": "",
        "active_filter_label": "All artbooks",
    }
    monkeypatch.setattr(
        app_module,
        "build_session_items",
        lambda *a, **kw: ([session_data], False),
    )

    # Mock resolve_artbook_title_for_token to return "Gorgeous Title"
    monkeypatch.setattr(
        app_module,
        "resolve_artbook_title_for_token",
        lambda *a: "Gorgeous Title",
    )

    response = client.get("/?workspace_view=chat&conversation=session-123")
    assert response.status_code == 200
    assert "Gorgeous Title" in response.text

def test_chat_delete_generation_htmx(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    # Mock validation of CSRF token
    monkeypatch.setattr(app_module, "is_csrf_valid", lambda *a: True)

    fake_gen = SimpleNamespace(
        id=123,
        request_snapshot_json={"chat_session_id": "session-123", "prompt_user": "cat"},
    )
    monkeypatch.setattr(app_module.crud, "get_generation", lambda _s, _id: fake_gen)

    response = client.post(
        "/generations/123/chat-delete",
        data={"csrf_token": "valid_token"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert fake_gen.request_snapshot_json["chat_deleted"] is True
    assert fake_gen in fake_session.added
    assert fake_session.committed is True

def test_chat_delete_generation_non_htmx(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    monkeypatch.setattr(app_module, "is_csrf_valid", lambda *a: True)

    fake_gen = SimpleNamespace(
        id=123,
        request_snapshot_json={"chat_session_id": "session-123"},
    )
    monkeypatch.setattr(app_module.crud, "get_generation", lambda _s, _id: fake_gen)

    response = client.post(
        "/generations/123/chat-delete",
        data={"csrf_token": "valid_token"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/?workspace_view=chat" in response.headers["location"]

def test_generation_input_image_thumbnail_generation(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    # Create dummy PNG image in-memory
    im = Image.new("RGBA", (100, 100), (255, 0, 0, 0))
    img_io = BytesIO()
    im.save(img_io, "PNG")
    png_bytes = img_io.getvalue()
    b64_str = base64.b64encode(png_bytes).decode("utf-8")

    fake_gen = SimpleNamespace(
        id=123,
        request_snapshot_json={
            "input_images": [
                {"mime": "image/png", "b64": b64_str}
            ]
        }
    )

    # Mock scalar query to return fake_gen
    def fake_scalar(query):
        return fake_gen
    fake_session.scalar = fake_scalar

    response = client.get("/generations/123/input-images/0")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    # Verify we can open the returned response content with PIL and it is indeed a WebP image
    resp_img = Image.open(BytesIO(response.content))
    assert resp_img.format == "WEBP"
    assert resp_img.size[0] <= 384 and resp_img.size[1] <= 384

def test_asset_thumbnail_auto_generation(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    # Mock asset details
    class FakeAsset:
        id = 456
        file_path = "some/file.png"
        thumbnail_path = "some/thumb.webp"
        mime = "image/png"
        generation = SimpleNamespace(
            storage_template_snapshot_json={"base_dir": "fake_base"}
        )

    fake_asset = FakeAsset()
    def fake_scalar(query):
        return fake_asset
    fake_session.scalar = fake_scalar

    # Mock path existence checks
    path_exists = {}
    # Resolve the path inside fake_exists to make it absolute for matching
    def fake_exists(self):
        return path_exists.get(Path(self).as_posix(), False) or path_exists.get(str(Path(self).resolve().as_posix()), False)
    monkeypatch.setattr(Path, "exists", fake_exists)

    # original image exists, but thumbnail does not
    path_exists[str(Path("fake_base/some/file.png").resolve().as_posix())] = True
    path_exists[str(Path("fake_base/some/thumb.webp").resolve().as_posix())] = False

    # Mock generation_service.asset_absolute_path to return Path instances
    monkeypatch.setattr(
        app_module.generation_service,
        "asset_absolute_path",
        lambda asset, which: Path("fake_base") / (asset.file_path if which == "file" else asset.thumbnail_path),
    )

    thumbnail_created = []
    # Mock thumbnail_service.create_thumbnail to create the file (make it exist)
    def fake_create_thumbnail(base_dir, file_path):
        thumbnail_created.append((base_dir, file_path))
        path_exists[str(Path("fake_base/some/thumb.webp").resolve().as_posix())] = True
        return Path("some/thumb.webp")
    monkeypatch.setattr(app_module.thumbnail_service, "create_thumbnail", fake_create_thumbnail)

    # Mock FileResponse using FastAPIResponse to avoid actual filesystem reading during tests
    class MockFileResponse(FastAPIResponse):
        def __init__(self, path, media_type, **kwargs):
            super().__init__(content=b"fake_webp_data", media_type=media_type)
            self.path = path

    monkeypatch.setattr(app_module, "FileResponse", MockFileResponse)

    response = client.get("/assets/456/thumb")
    assert response.status_code == 200
    assert len(thumbnail_created) == 1
    assert thumbnail_created[0] == (Path("fake_base").resolve(), "some/file.png")


def test_chat_generation_item_renders_asset_delete_button(client, app_module, monkeypatch) -> None:
    fake_session = _FakeSession()
    app_module.app.dependency_overrides[app_module.get_session] = _override_session(fake_session)

    asset = SimpleNamespace(id=999, mime="image/webp", file_path="some/image.webp")
    generation = SimpleNamespace(
        id=888,
        status="succeeded",
        prompt_user="Delete me",
        profile_name="Default",
        provider="stub",
        model="stub-v1",
        request_snapshot_json={},
        error=None,
        failure_sidecar_path=None,
        assets=[asset],
    )

    def fake_scalar(query):
        return generation
    fake_session.scalar = fake_scalar

    response = client.get("/jobs/888?view=chat")
    assert response.status_code == 200
    body = response.text
    assert 'action="/assets/999/delete"' in body
    assert 'hx-post="/assets/999/delete"' in body
    assert 'hx-swap="none"' in body
    assert 'data-confirm-message="Delete this image?"' in body
    assert 'bi-trash' in body
