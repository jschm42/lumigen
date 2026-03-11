from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest


def test_parse_optional_int(app_module) -> None:
    assert app_module.parse_optional_int(None) is None
    assert app_module.parse_optional_int("  ") is None
    assert app_module.parse_optional_int("42") == 42
    with pytest.raises(ValueError):
        app_module.parse_optional_int("x")


def test_apply_openrouter_image_config_non_openrouter_removes_image_config_keys(app_module) -> None:
    payload = {
        "foo": "bar",
        "image_config": {
            "aspect_ratio": "16:9",
            "image_size": "2K",
            "keep": "yes",
        },
    }
    merged = app_module.apply_openrouter_image_config(
        params_json=payload,
        provider="openai",
        aspect_ratio="",
        image_size="",
    )

    assert merged["foo"] == "bar"
    assert merged["image_config"] == {"keep": "yes"}


def test_apply_openrouter_image_config_validates_and_sets_values(app_module) -> None:
    merged = app_module.apply_openrouter_image_config(
        params_json={"a": 1},
        provider="openrouter",
        aspect_ratio="16:9",
        image_size="2k",
    )
    assert merged["image_config"]["aspect_ratio"] == "16:9"
    assert merged["image_config"]["image_size"] == "2K"

    with pytest.raises(ValueError, match="aspect ratio"):
        app_module.apply_openrouter_image_config(
            params_json={},
            provider="openrouter",
            aspect_ratio="10:9",
            image_size="",
        )

    with pytest.raises(ValueError, match="image size"):
        app_module.apply_openrouter_image_config(
            params_json={},
            provider="openrouter",
            aspect_ratio="",
            image_size="8K",
        )


def test_apply_openrouter_image_config_allow_clear_behavior(app_module) -> None:
    merged = app_module.apply_openrouter_image_config(
        params_json={"image_config": {"aspect_ratio": "1:1", "image_size": "1K"}},
        provider="openrouter",
        aspect_ratio="",
        image_size="",
        allow_clear=False,
    )
    assert merged["image_config"]["aspect_ratio"] == "1:1"
    assert merged["image_config"]["image_size"] == "1K"


def test_normalizers_and_safe_gallery_return_to(app_module) -> None:
    assert app_module.normalize_thumb_size("sm") == "sm"
    assert app_module.normalize_thumb_size("bad") == "md"
    assert app_module.normalize_category_ids([3, 1, 1, -1, 0]) == [1, 3]

    assert app_module.safe_gallery_return_to("/gallery?page=2") == "/gallery?page=2"
    assert app_module.safe_gallery_return_to("https://evil.example") == "/gallery"

    assert app_module.normalize_admin_section("models") == "models"
    assert app_module.normalize_admin_section("nope") == "models"


def test_name_normalization_constraints(app_module) -> None:
    assert app_module.normalize_category_name("  Cat  ") == "Cat"
    assert app_module.normalize_profile_name("  P  ") == "P"
    assert app_module.normalize_model_config_name("  M  ") == "M"

    with pytest.raises(ValueError):
        app_module.normalize_category_name("")
    with pytest.raises(ValueError):
        app_module.normalize_profile_name(" " * 51)
    with pytest.raises(ValueError):
        app_module.normalize_model_config_name(" " * 51)


def test_generation_session_helpers(app_module) -> None:
    token_from_snapshot = app_module.generation_session_token(
        SimpleNamespace(
            request_snapshot_json={"chat_session_id": "session:abc"},
            profile_id=2,
            profile_name="Profile",
        )
    )
    assert token_from_snapshot == "session:abc"

    token_from_profile_id = app_module.generation_session_token(
        SimpleNamespace(
            request_snapshot_json={},
            profile_id=2,
            profile_name="Profile",
        )
    )
    assert token_from_profile_id == "profile:2"

    token_from_profile_name = app_module.generation_session_token(
        SimpleNamespace(
            request_snapshot_json={},
            profile_id=None,
            profile_name="Hello World",
        )
    )
    assert token_from_profile_name == "profile-name:hello-world"

    assert (
        app_module.generation_session_title(
            SimpleNamespace(request_snapshot_json={"chat_session_title": "  My Title  "})
        )
        == "My Title"
    )
    assert app_module.generation_chat_hidden(SimpleNamespace(request_snapshot_json={"chat_hidden": True})) is True
    assert app_module.generation_session_archived(SimpleNamespace(request_snapshot_json={"chat_archived": True})) is True
    assert app_module.generation_chat_deleted(SimpleNamespace(request_snapshot_json={"chat_deleted": True})) is True


def test_redirect_builders(app_module) -> None:
    response = app_module.generate_workspace_redirect(
        conversation="session:abc",
        workspace_view="unknown",
        error="oops",
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/?workspace_view=chat&conversation=session%3Aabc")
    assert "error=oops" in response.headers["location"]

    gallery_response = app_module.gallery_redirect(
        "/gallery?page=1",
        message="ok",
        error="warn",
    )
    assert gallery_response.status_code == 303
    assert "message=ok" in gallery_response.headers["location"]
    assert "error=warn" in gallery_response.headers["location"]

    admin_response = app_module.admin_redirect("categories", message="saved")
    assert admin_response.status_code == 303
    assert admin_response.headers["location"] == "/admin?section=categories&message=saved"


def test_format_session_helpers(app_module) -> None:
    now = datetime.now()
    assert app_module.format_session_timestamp(None) == ""
    assert app_module.format_session_timestamp(datetime.min) == ""
    assert app_module.format_session_timestamp(now).count(":") == 1

    age_today = app_module.format_session_age(now)
    assert age_today.endswith("h") or age_today == "0h"

    category_today = app_module.get_session_time_category(now)
    assert category_today == "today"

    assert app_module.get_session_time_category(now - timedelta(days=20)) == "last30days"
    assert app_module.get_session_time_category(now - timedelta(days=50)) == "last60days"
    assert app_module.get_session_time_category(now - timedelta(days=100)) == "last120days"
    assert app_module.get_session_time_category(now - timedelta(days=300)) == "lastyear"
    assert app_module.get_session_time_category(now - timedelta(days=500)) == "older"


def test_normalize_time_preset_supports_extended_values(app_module) -> None:
    assert app_module.normalize_time_preset("today") == "today"
    assert app_module.normalize_time_preset("last_60_days") == "last_60_days"
    assert app_module.normalize_time_preset("last_120_days") == "last_120_days"
    assert app_module.normalize_time_preset("last_year") == "last_year"
    assert app_module.normalize_time_preset("older") == "older"
    assert app_module.normalize_time_preset("nope") == "today"


def test_parse_proxy_trusted_hosts(app_module) -> None:
    assert app_module.parse_proxy_trusted_hosts("") == "127.0.0.1"
    assert app_module.parse_proxy_trusted_hosts("   ") == "127.0.0.1"
    assert app_module.parse_proxy_trusted_hosts("*") == "*"
    assert app_module.parse_proxy_trusted_hosts("127.0.0.1") == ["127.0.0.1"]
    assert app_module.parse_proxy_trusted_hosts("127.0.0.1, 10.0.0.1") == [
        "127.0.0.1",
        "10.0.0.1",
    ]
