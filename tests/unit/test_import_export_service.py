"""Unit tests for the import/export service."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.import_export_service import (
    SUPPORTED_FORMAT_VERSIONS,
    ImportResult,
    RecordResult,
    _unique_name,
    export_all,
    export_models,
    export_profiles,
    export_styles,
    import_models,
    import_profiles,
    import_styles,
    validate_import_payload,
)


# ---------------------------------------------------------------------------
# validate_import_payload
# ---------------------------------------------------------------------------


def test_validate_payload_valid_minimal() -> None:
    error, version, profiles, models, styles = validate_import_payload({"format_version": "1"})
    assert error is None
    assert version == "1"
    assert profiles == []
    assert models == []
    assert styles == []


def test_validate_payload_non_dict_raises() -> None:
    error, *_ = validate_import_payload([1, 2, 3])
    assert error is not None
    assert "must be a JSON object" in error


def test_validate_payload_missing_version_raises() -> None:
    error, *_ = validate_import_payload({"models": []})
    assert error is not None
    assert "format_version" in error


def test_validate_payload_unsupported_version_raises() -> None:
    error, *_ = validate_import_payload({"format_version": "99"})
    assert error is not None
    assert "Unsupported format_version" in error


def test_validate_payload_profiles_not_list_raises() -> None:
    error, *_ = validate_import_payload({"format_version": "1", "profiles": "not a list"})
    assert error is not None
    assert "'profiles' must be a JSON array" in error


def test_validate_payload_models_not_list_raises() -> None:
    error, *_ = validate_import_payload({"format_version": "1", "models": {"name": "oops"}})
    assert error is not None
    assert "'models' must be a JSON array" in error


def test_validate_payload_styles_not_list_raises() -> None:
    error, *_ = validate_import_payload({"format_version": "1", "styles": 42})
    assert error is not None
    assert "'styles' must be a JSON array" in error


# ---------------------------------------------------------------------------
# _unique_name
# ---------------------------------------------------------------------------


def test_unique_name_no_conflict() -> None:
    assert _unique_name("MyName", set(), 50) == "MyName"


def test_unique_name_single_conflict() -> None:
    result = _unique_name("MyName", {"MyName"}, 50)
    assert result == "MyName (2)"


def test_unique_name_multiple_conflicts() -> None:
    existing = {"MyName", "MyName (2)", "MyName (3)"}
    result = _unique_name("MyName", existing, 50)
    assert result == "MyName (4)"


def test_unique_name_respects_max_len() -> None:
    # Base name is 28 chars; max_len is 30; suffix (2) is 4 chars
    base = "A" * 28
    existing = {base}
    result = _unique_name(base, existing, 30)
    assert len(result) <= 30
    assert "(2)" in result


# ---------------------------------------------------------------------------
# ImportResult
# ---------------------------------------------------------------------------


def test_import_result_counts() -> None:
    r = ImportResult(entity_type="models")
    r.records.extend(
        [
            RecordResult(name="A", outcome="created"),
            RecordResult(name="B", outcome="updated"),
            RecordResult(name="C", outcome="skipped"),
            RecordResult(name="D", outcome="failed", reason="oops"),
        ]
    )
    assert r.created == 1
    assert r.updated == 1
    assert r.skipped == 1
    assert r.failed == 1


def test_import_result_to_dict() -> None:
    r = ImportResult(entity_type="styles")
    r.records.append(RecordResult(name="Vintage", outcome="created"))
    d = r.to_dict()
    assert d["entity_type"] == "styles"
    assert d["created"] == 1
    assert d["failed"] == 0
    assert d["records"][0]["name"] == "Vintage"
    assert d["records"][0]["outcome"] == "created"


# ---------------------------------------------------------------------------
# export helpers (light smoke tests)
# ---------------------------------------------------------------------------


def _make_model(name="M", provider="openai", model="dall-e-3"):
    """Create a mock ModelConfig-like namespace for use in service unit tests."""
    return SimpleNamespace(
        name=name,
        provider=provider,
        model=model,
        enhancement_prompt=None,
        use_custom_api_key=False,
    )


def _make_style(name="Vintage", description="Old", prompt="grain"):
    """Create a mock Style-like namespace for use in service unit tests."""
    return SimpleNamespace(name=name, description=description, prompt=prompt)


def _make_profile(name="P", provider="openai", model="dall-e-3"):
    """Create a mock Profile-like namespace for use in service unit tests."""
    return SimpleNamespace(
        name=name,
        provider=provider,
        model=model,
        model_config=None,
        base_prompt=None,
        negative_prompt=None,
        width=None,
        height=None,
        aspect_ratio=None,
        n_images=1,
        seed=None,
        output_format="png",
        upscale_provider=None,
        upscale_model=None,
        params_json={},
    )


def test_export_models_structure() -> None:
    session = MagicMock()
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_model_configs.return_value = [_make_model()]
        result = export_models(session)

    assert result["format_version"] == "1"
    assert "exported_at" in result
    assert len(result["models"]) == 1
    m = result["models"][0]
    assert m["name"] == "M"
    assert m["provider"] == "openai"
    assert m["model"] == "dall-e-3"
    assert m["use_custom_api_key"] is False
    assert "api_key_encrypted" not in m


def test_export_styles_structure() -> None:
    session = MagicMock()
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_styles.return_value = [_make_style()]
        result = export_styles(session)

    assert result["format_version"] == "1"
    assert len(result["styles"]) == 1
    s = result["styles"][0]
    assert s["name"] == "Vintage"
    assert "image_path" not in s


def test_export_profiles_structure() -> None:
    session = MagicMock()
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_profiles.return_value = [_make_profile()]
        result = export_profiles(session)

    assert result["format_version"] == "1"
    assert len(result["profiles"]) == 1
    p = result["profiles"][0]
    assert p["name"] == "P"
    assert p["model_config_name"] is None
    assert "params_json" in p


def test_export_all_structure() -> None:
    session = MagicMock()
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_model_configs.return_value = [_make_model()]
        mock_crud.list_profiles.return_value = [_make_profile()]
        mock_crud.list_styles.return_value = [_make_style()]
        result = export_all(session)

    assert "models" in result
    assert "profiles" in result
    assert "styles" in result
    assert result["format_version"] == "1"


# ---------------------------------------------------------------------------
# import_models
# ---------------------------------------------------------------------------


def test_import_models_creates_new() -> None:
    session = MagicMock()
    new_model = SimpleNamespace(name="NewModel")
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_model_configs.return_value = []
        mock_crud.get_model_config_by_name.return_value = None
        mock_crud.create_model_config.return_value = new_model

        result = import_models(
            session,
            [{"name": "NewModel", "provider": "openai", "model": "dall-e-3"}],
            "skip",
        )

    assert result.created == 1
    assert result.failed == 0


def test_import_models_skip_existing() -> None:
    session = MagicMock()
    existing = SimpleNamespace(name="ExistingModel")
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_model_configs.return_value = [existing]
        mock_crud.get_model_config_by_name.return_value = existing

        result = import_models(
            session,
            [{"name": "ExistingModel", "provider": "openai", "model": "dall-e-3"}],
            "skip",
        )

    assert result.skipped == 1
    assert result.created == 0


def test_import_models_overwrite_existing() -> None:
    session = MagicMock()
    existing = SimpleNamespace(name="ExistingModel")
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_model_configs.return_value = [existing]
        mock_crud.get_model_config_by_name.return_value = existing
        mock_crud.update_model_config.return_value = existing

        result = import_models(
            session,
            [{"name": "ExistingModel", "provider": "openai", "model": "dall-e-3"}],
            "overwrite",
        )

    assert result.updated == 1
    assert result.failed == 0


def test_import_models_rename_existing() -> None:
    session = MagicMock()
    existing = SimpleNamespace(name="ExistingModel")
    new_model = SimpleNamespace(name="ExistingModel (2)")
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_model_configs.return_value = [existing]
        mock_crud.get_model_config_by_name.return_value = existing
        mock_crud.create_model_config.return_value = new_model

        result = import_models(
            session,
            [{"name": "ExistingModel", "provider": "openai", "model": "dall-e-3"}],
            "rename",
        )

    assert result.created == 1
    created_name = result.records[0].name
    assert created_name == "ExistingModel (2)"


def test_import_models_dry_run_no_db_write() -> None:
    session = MagicMock()
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_model_configs.return_value = []
        mock_crud.get_model_config_by_name.return_value = None

        result = import_models(
            session,
            [{"name": "DryModel", "provider": "openai", "model": "dall-e-3"}],
            "skip",
            dry_run=True,
        )

    mock_crud.create_model_config.assert_not_called()
    assert result.created == 1


def test_import_models_missing_required_field() -> None:
    session = MagicMock()
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_model_configs.return_value = []

        result = import_models(
            session,
            [{"name": "MissingProvider", "model": "dall-e-3"}],  # no provider
            "skip",
        )

    assert result.failed == 1
    assert "provider" in result.records[0].reason


def test_import_models_name_too_long() -> None:
    session = MagicMock()
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_model_configs.return_value = []

        result = import_models(
            session,
            [{"name": "A" * 51, "provider": "openai", "model": "dall-e-3"}],
            "skip",
        )

    assert result.failed == 1
    assert "exceeds" in result.records[0].reason


def test_import_models_invalid_conflict_strategy() -> None:
    session = MagicMock()
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_model_configs.return_value = []
        with pytest.raises(ValueError, match="Invalid conflict_strategy"):
            import_models(session, [], "invalid")


# ---------------------------------------------------------------------------
# import_styles
# ---------------------------------------------------------------------------


def test_import_styles_creates_new() -> None:
    session = MagicMock()
    new_style = SimpleNamespace(name="Vintage")
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_styles.return_value = []
        mock_crud.create_style.return_value = new_style

        result = import_styles(
            session,
            [{"name": "Vintage", "description": "Old look", "prompt": "aged grain"}],
            "skip",
        )

    assert result.created == 1


def test_import_styles_skip_existing() -> None:
    session = MagicMock()
    existing = SimpleNamespace(name="Vintage")
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_styles.return_value = [existing]

        result = import_styles(
            session,
            [{"name": "Vintage", "description": "Old look", "prompt": "aged grain"}],
            "skip",
        )

    assert result.skipped == 1


def test_import_styles_overwrite_existing() -> None:
    session = MagicMock()
    existing = SimpleNamespace(name="Vintage")
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_styles.return_value = [existing]
        mock_crud.update_style.return_value = existing

        result = import_styles(
            session,
            [{"name": "Vintage", "description": "New look", "prompt": "new grain"}],
            "overwrite",
        )

    assert result.updated == 1


def test_import_styles_dry_run_no_db_write() -> None:
    session = MagicMock()
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_styles.return_value = []

        result = import_styles(
            session,
            [{"name": "DryStyle", "description": "desc", "prompt": "prompt"}],
            "skip",
            dry_run=True,
        )

    mock_crud.create_style.assert_not_called()
    assert result.created == 1


def test_import_styles_missing_description() -> None:
    session = MagicMock()
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_styles.return_value = []

        result = import_styles(
            session,
            [{"name": "X", "prompt": "some prompt"}],  # no description
            "skip",
        )

    assert result.failed == 1


def test_import_styles_prompt_too_long() -> None:
    session = MagicMock()
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_styles.return_value = []

        result = import_styles(
            session,
            [{"name": "X", "description": "desc", "prompt": "p" * 1001}],
            "skip",
        )

    assert result.failed == 1
    assert "exceeds" in result.records[0].reason


# ---------------------------------------------------------------------------
# import_profiles
# ---------------------------------------------------------------------------


def test_import_profiles_creates_new() -> None:
    session = MagicMock()
    storage_template = SimpleNamespace(id=1, name="default")
    new_profile = SimpleNamespace(name="TestProfile")
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_profiles.return_value = []
        mock_crud.list_model_configs.return_value = []
        mock_crud.get_model_config_by_name.return_value = None
        mock_crud.ensure_default_storage_template.return_value = storage_template
        mock_crud.create_profile.return_value = new_profile

        result = import_profiles(
            session,
            [{"name": "TestProfile", "provider": "openai", "model": "dall-e-3"}],
            "skip",
        )

    assert result.created == 1


def test_import_profiles_skip_existing() -> None:
    session = MagicMock()
    existing = SimpleNamespace(name="TestProfile")
    storage_template = SimpleNamespace(id=1, name="default")
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_profiles.return_value = [existing]
        mock_crud.list_model_configs.return_value = []
        mock_crud.ensure_default_storage_template.return_value = storage_template

        result = import_profiles(
            session,
            [{"name": "TestProfile", "provider": "openai", "model": "dall-e-3"}],
            "skip",
        )

    assert result.skipped == 1


def test_import_profiles_dry_run_no_db_write() -> None:
    session = MagicMock()
    storage_template = SimpleNamespace(id=1, name="default")
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_profiles.return_value = []
        mock_crud.list_model_configs.return_value = []
        mock_crud.ensure_default_storage_template.return_value = storage_template

        result = import_profiles(
            session,
            [{"name": "DryProfile", "provider": "openai", "model": "dall-e-3"}],
            "skip",
            dry_run=True,
        )

    mock_crud.create_profile.assert_not_called()
    assert result.created == 1


def test_import_profiles_links_model_config_by_name() -> None:
    session = MagicMock()
    storage_template = SimpleNamespace(id=1, name="default")
    model_config = SimpleNamespace(id=42, name="MyModelConfig")
    created = []

    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_profiles.return_value = []
        mock_crud.list_model_configs.return_value = [model_config]
        mock_crud.ensure_default_storage_template.return_value = storage_template

        def fake_create(session, **fields):
            created.append(fields)
            return SimpleNamespace(**fields)

        mock_crud.create_profile.side_effect = fake_create

        import_profiles(
            session,
            [
                {
                    "name": "LinkedProfile",
                    "provider": "openai",
                    "model": "dall-e-3",
                    "model_config_name": "MyModelConfig",
                }
            ],
            "skip",
        )

    assert created[0]["model_config_id"] == 42


def test_import_profiles_name_too_long() -> None:
    session = MagicMock()
    storage_template = SimpleNamespace(id=1, name="default")
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_profiles.return_value = []
        mock_crud.list_model_configs.return_value = []
        mock_crud.ensure_default_storage_template.return_value = storage_template

        result = import_profiles(
            session,
            [{"name": "P" * 51, "provider": "openai", "model": "dall-e-3"}],
            "skip",
        )

    assert result.failed == 1


# ---------------------------------------------------------------------------
# Round-trip: export then import
# ---------------------------------------------------------------------------


def test_round_trip_models_export_import() -> None:
    """Exported model data can be re-imported as a new record."""
    session = MagicMock()
    model = SimpleNamespace(
        name="RoundTrip",
        provider="openai",
        model="dall-e-3",
        enhancement_prompt="enhance this",
        use_custom_api_key=False,
    )
    # Export
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_model_configs.return_value = [model]
        exported = export_models(session)

    # Import into empty DB
    with patch("app.services.import_export_service.crud") as mock_crud:
        mock_crud.list_model_configs.return_value = []
        mock_crud.create_model_config.return_value = model
        result = import_models(session, exported["models"], "skip")

    assert result.created == 1
    assert result.records[0].name == "RoundTrip"
