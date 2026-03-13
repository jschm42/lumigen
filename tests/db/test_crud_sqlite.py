from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import crud
from app.db.models import Base, Generation


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with SessionLocal() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_storage_template_and_profile_crud_flow(db_session: Session) -> None:
    default_template = crud.ensure_default_storage_template(
        db_session,
        base_dir=Path("./data/images"),
        template="/{profile}/{yyyy}/{slug}.{ext}",
    )
    assert default_template.name == "default"
    assert crud.ensure_default_storage_template(
        db_session,
        base_dir=Path("./data/images"),
        template="/ignored",
    ).id == default_template.id

    model = crud.create_model_config(
        db_session,
        name="default-model",
        provider="stub",
        model="stub-v1",
        enhancement_prompt=None,
        api_key_encrypted=None,
        use_custom_api_key=False,
    )
    cat_a = crud.create_category(db_session, name="Concept")
    cat_b = crud.create_category(db_session, name="Final")

    profile = crud.create_profile(
        db_session,
        name="Default Profile",
        provider="stub",
        model="stub-v1",
        model_config_id=model.id,
        base_prompt="base",
        negative_prompt=None,
        width=512,
        height=512,
        aspect_ratio=None,
        n_images=1,
        seed=42,
        output_format="png",
        upscale_model=None,
        params_json={"cfg": 1},
        categories=[cat_a, cat_b],
        storage_template_id=default_template.id,
    )

    listed_profiles = crud.list_profiles(db_session)
    assert len(listed_profiles) == 1
    loaded = crud.get_profile(db_session, profile.id)
    assert loaded is not None
    assert loaded.name == "Default Profile"
    assert sorted(item.name for item in loaded.categories) == ["Concept", "Final"]

    updated = crud.update_profile(db_session, loaded, name="Renamed Profile", n_images=2)
    assert updated.name == "Renamed Profile"
    assert updated.n_images == 2

    model_loaded = crud.get_model_config_by_name(db_session, "default-model")
    assert model_loaded is not None
    assert model_loaded.provider == "stub"

    preset = crud.create_dimension_preset(db_session, name="sq-512", width=512, height=512)
    assert crud.get_dimension_preset(db_session, preset.id) is not None
    preset = crud.update_dimension_preset(db_session, preset, width=768, height=768)
    assert preset.width == 768
    assert preset.height == 768
    assert len(crud.list_dimension_presets(db_session)) == 1
    crud.delete_dimension_preset(db_session, preset)
    assert crud.get_dimension_preset(db_session, preset.id) is None

    model_loaded = crud.get_model_config(db_session, model.id)
    model_loaded = crud.update_model_config(db_session, model_loaded, model="stub-v2")
    assert model_loaded.model == "stub-v2"
    assert len(crud.list_model_configs(db_session)) == 1

    category = crud.get_category(db_session, cat_a.id)
    updated_cat = crud.update_category(db_session, category, name="Concept Art")
    assert updated_cat.name == "Concept Art"
    selected_categories = crud.list_categories_by_ids(db_session, [cat_b.id, cat_a.id])
    assert [item.name for item in selected_categories] == ["Concept Art", "Final"]
    assert [item.name for item in crud.list_categories(db_session)] == ["Concept Art", "Final"]

    crud.delete_profile(db_session, updated)
    assert crud.get_profile(db_session, profile.id) is None

    crud.delete_category(db_session, updated_cat)
    assert crud.get_category(db_session, cat_a.id) is None

    model_to_delete = crud.get_model_config(db_session, model.id)
    crud.delete_model_config(db_session, model_to_delete)
    assert crud.get_model_config(db_session, model.id) is None


def test_generation_asset_and_session_preference_crud_flow(db_session: Session) -> None:
    storage_template = crud.ensure_default_storage_template(
        db_session,
        base_dir=Path("./data/images"),
        template="/{profile}/{yyyy}/{slug}.{ext}",
    )
    model = crud.create_model_config(
        db_session,
        name="stub-model",
        provider="stub",
        model="stub-v1",
        enhancement_prompt=None,
        api_key_encrypted=None,
        use_custom_api_key=False,
    )
    profile = crud.create_profile(
        db_session,
        name="P1",
        provider="stub",
        model="stub-v1",
        model_config_id=model.id,
        base_prompt="bp",
        negative_prompt=None,
        width=512,
        height=512,
        aspect_ratio=None,
        n_images=1,
        seed=None,
        output_format="png",
        upscale_model=None,
        params_json={},
        categories=[],
        storage_template_id=storage_template.id,
    )

    generation = crud.create_generation(
        db_session,
        Generation(
            profile_id=profile.id,
            profile_name=profile.name,
            prompt_user="user",
            prompt_final="final",
            provider="stub",
            model="stub-v1",
            status="queued",
            error=None,
            profile_snapshot_json={"p": 1},
            storage_template_snapshot_json={"base_dir": "."},
            request_snapshot_json={"r": 1},
            failure_sidecar_path=None,
        ),
    )
    loaded_generation = crud.get_generation(db_session, generation.id)
    assert loaded_generation is not None

    from app.db.models import Asset

    asset = Asset(
        generation_id=generation.id,
        file_path="a.png",
        sidecar_path="a.png.json",
        thumbnail_path=".thumbs/a.webp",
        width=100,
        height=100,
        mime="image/png",
        meta_json={"k": "v"},
        categories=[],
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    loaded_with_assets = crud.get_generation(db_session, generation.id, with_assets=True)
    assert loaded_with_assets is not None
    assert len(loaded_with_assets.assets) == 1

    loaded_asset = crud.get_asset(db_session, asset.id, with_generation=True)
    assert loaded_asset is not None
    assert loaded_asset.generation is not None

    prefs = crud.upsert_chat_session_preferences(
        db_session,
        chat_session_id="session:abc",
        last_profile_id=profile.id,
        last_thumb_size="sm",
    )
    assert prefs.chat_session_id == "session:abc"
    assert prefs.last_thumb_size == "sm"

    prefs = crud.upsert_chat_session_preferences(
        db_session,
        chat_session_id="session:abc",
        last_profile_id=profile.id,
        last_thumb_size="lg",
    )
    loaded_session = crud.get_chat_session(db_session, "session:abc")
    assert loaded_session is not None
    assert loaded_session.last_thumb_size == "lg"
    assert loaded_session.last_profile_id == profile.id

    enhancement = crud.upsert_enhancement_config(
        db_session,
        provider="openai",
        model="gpt-4.1-mini",
        api_key_encrypted="enc1",
    )
    assert enhancement.provider == "openai"

    enhancement = crud.upsert_enhancement_config(
        db_session,
        provider="openrouter",
        model="or-model",
        api_key_encrypted="enc2",
    )
    loaded_enhancement = crud.get_enhancement_config(db_session)
    assert loaded_enhancement is not None
    assert loaded_enhancement.provider == "openrouter"
    assert loaded_enhancement.api_key_encrypted == "enc2"


def test_topaz_upscale_model_crud_flow(db_session: Session) -> None:
    created = crud.create_topaz_upscale_model(
        db_session,
        name="Topaz Standard",
        model_identifier="fal-ai/topaz/upscale/image",
        params_json={"creativity": 0.25},
        is_enabled=True,
    )
    assert created.id is not None

    by_name = crud.get_topaz_upscale_model_by_name(db_session, "Topaz Standard")
    assert by_name is not None
    assert by_name.model_identifier == "fal-ai/topaz/upscale/image"

    listed_enabled = crud.list_topaz_upscale_models(db_session, enabled_only=True)
    assert len(listed_enabled) == 1

    updated = crud.update_topaz_upscale_model(
        db_session,
        by_name,
        params_json={"creativity": 0.6},
        is_enabled=False,
    )
    assert updated.params_json == {"creativity": 0.6}
    assert updated.is_enabled is False

    listed_enabled = crud.list_topaz_upscale_models(db_session, enabled_only=True)
    assert listed_enabled == []

    loaded = crud.get_topaz_upscale_model(db_session, created.id)
    assert loaded is not None
    crud.delete_topaz_upscale_model(db_session, loaded)
    assert crud.get_topaz_upscale_model(db_session, created.id) is None
