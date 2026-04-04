from __future__ import annotations

from pathlib import Path

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Asset,
    Category,
    ChatSession,
    DimensionPreset,
    EnhancementConfig,
    Generation,
    ModelConfig,
    Profile,
    ProviderApiKey,
    StorageTemplate,
    Style,
    TopazUpscaleModel,
    User,
)


def ensure_default_storage_template(
    session: Session, base_dir: Path, template: str
) -> StorageTemplate:
    """Return the ``default`` storage template, creating it if none exists yet."""
    existing_default = session.scalar(
        select(StorageTemplate).where(StorageTemplate.name == "default")
    )
    if existing_default:
        return existing_default

    any_template = session.scalar(select(StorageTemplate).limit(1))
    if any_template:
        return any_template

    row = StorageTemplate(
        name="default", base_dir=base_dir.resolve().as_posix(), template=template
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_storage_templates(session: Session) -> list[StorageTemplate]:
    """Return all storage templates ordered by name."""
    stmt = select(StorageTemplate).order_by(StorageTemplate.name.asc())
    return list(session.scalars(stmt).all())


def count_users(session: Session) -> int:
    """Return the total number of users in the database."""
    stmt = select(User.id)
    return len(list(session.scalars(stmt).all()))


def list_users(session: Session) -> list[User]:
    """Return all users ordered by username."""
    stmt = select(User).order_by(User.username.asc())
    return list(session.scalars(stmt).all())


def count_admin_users(session: Session, *, active_only: bool = True) -> int:
    """Return the number of admin users, optionally restricting to active accounts."""
    stmt = select(User.id).where(User.role == "admin")
    if active_only:
        stmt = stmt.where(User.is_active.is_(True))
    return len(list(session.scalars(stmt).all()))


def get_user(session: Session, user_id: int) -> User | None:
    """Return a user by primary key, or ``None`` if not found."""
    stmt = select(User).where(User.id == user_id)
    return session.scalar(stmt)


def get_user_by_username(session: Session, username: str) -> User | None:
    """Return a user by username (case-sensitive), or ``None`` if not found."""
    stmt = select(User).where(User.username == username)
    return session.scalar(stmt)


def create_user(session: Session, **fields) -> User:
    """Create a new user row from the given field values and return it."""
    row = User(**fields)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_user(session: Session, user: User, **fields) -> User:
    """Update the given user's fields and return the refreshed instance."""
    for key, value in fields.items():
        setattr(user, key, value)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def delete_user(session: Session, user: User) -> None:
    """Delete the given user from the database."""
    session.delete(user)
    session.commit()


def delete_all_users(session: Session) -> None:
    """Delete every user row. Intended for testing and onboarding-reset scenarios only."""
    session.query(User).delete()
    session.commit()


def list_profiles(session: Session) -> list[Profile]:
    """Return all profiles with their related storage template, model config, and categories."""
    stmt = (
        select(Profile)
        .options(
            selectinload(Profile.storage_template),
            selectinload(Profile.model_config),
            selectinload(Profile.categories),
        )
        .order_by(Profile.name.asc())
    )
    return list(session.scalars(stmt).all())


def list_model_configs(session: Session) -> list[ModelConfig]:
    """Return all model configurations ordered by name."""
    stmt = select(ModelConfig).order_by(ModelConfig.name.asc())
    return list(session.scalars(stmt).all())


def list_topaz_upscale_models(
    session: Session, *, enabled_only: bool = False
) -> list[TopazUpscaleModel]:
    """Return Topaz upscale model configurations ordered by name."""
    stmt = select(TopazUpscaleModel)
    if enabled_only:
        stmt = stmt.where(TopazUpscaleModel.is_enabled.is_(True))
    stmt = stmt.order_by(TopazUpscaleModel.name.asc())
    return list(session.scalars(stmt).all())


def get_topaz_upscale_model(
    session: Session, topaz_model_id: int
) -> TopazUpscaleModel | None:
    """Return a Topaz upscale model by primary key, or ``None`` if not found."""
    stmt = select(TopazUpscaleModel).where(TopazUpscaleModel.id == topaz_model_id)
    return session.scalar(stmt)


def get_topaz_upscale_model_by_name(
    session: Session, name: str
) -> TopazUpscaleModel | None:
    """Return a Topaz upscale model by name, or ``None`` if not found."""
    stmt = select(TopazUpscaleModel).where(TopazUpscaleModel.name == name)
    return session.scalar(stmt)


def create_topaz_upscale_model(session: Session, **fields) -> TopazUpscaleModel:
    """Create a new Topaz upscale model row and return it."""
    row = TopazUpscaleModel(**fields)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_topaz_upscale_model(
    session: Session,
    topaz_model: TopazUpscaleModel,
    **fields,
) -> TopazUpscaleModel:
    """Update a Topaz upscale model's fields and return the refreshed instance."""
    for key, value in fields.items():
        setattr(topaz_model, key, value)
    session.add(topaz_model)
    session.commit()
    session.refresh(topaz_model)
    return topaz_model


def delete_topaz_upscale_model(
    session: Session, topaz_model: TopazUpscaleModel
) -> None:
    """Delete the given Topaz upscale model from the database."""
    session.delete(topaz_model)
    session.commit()


def list_dimension_presets(session: Session) -> list[DimensionPreset]:
    """Return all dimension presets ordered by name."""
    stmt = select(DimensionPreset).order_by(DimensionPreset.name.asc())
    return list(session.scalars(stmt).all())


def list_categories(session: Session) -> list[Category]:
    """Return all categories ordered by name."""
    stmt = select(Category).order_by(Category.name.asc())
    return list(session.scalars(stmt).all())


def list_categories_by_ids(session: Session, category_ids: list[int]) -> list[Category]:
    """Return the categories whose IDs are in *category_ids*, ordered by name."""
    if not category_ids:
        return []
    stmt = select(Category).where(Category.id.in_(category_ids)).order_by(Category.name.asc())
    return list(session.scalars(stmt).all())


def get_category(session: Session, category_id: int) -> Category | None:
    """Return a category by primary key, or ``None`` if not found."""
    stmt = select(Category).where(Category.id == category_id)
    return session.scalar(stmt)


def create_category(session: Session, **fields) -> Category:
    """Create a new category from the given field values and return it."""
    row = Category(**fields)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_category(session: Session, category: Category, **fields) -> Category:
    """Update the given category's fields and return the refreshed instance."""
    for key, value in fields.items():
        setattr(category, key, value)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def delete_category(session: Session, category: Category) -> None:
    """Delete the given category from the database."""
    session.delete(category)
    session.commit()


def get_model_config(session: Session, model_config_id: int) -> ModelConfig | None:
    """Return a model configuration by primary key, or ``None`` if not found."""
    stmt = select(ModelConfig).where(ModelConfig.id == model_config_id)
    return session.scalar(stmt)


def get_model_config_by_name(session: Session, name: str) -> ModelConfig | None:
    """Return a model configuration by name, or ``None`` if not found."""
    stmt = select(ModelConfig).where(ModelConfig.name == name)
    return session.scalar(stmt)


def create_model_config(session: Session, **fields) -> ModelConfig:
    """Create a new model configuration from the given field values and return it."""
    row = ModelConfig(**fields)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_dimension_preset(
    session: Session, preset_id: int
) -> DimensionPreset | None:
    """Return a dimension preset by primary key, or ``None`` if not found."""
    stmt = select(DimensionPreset).where(DimensionPreset.id == preset_id)
    return session.scalar(stmt)


def create_dimension_preset(session: Session, **fields) -> DimensionPreset:
    """Create a new dimension preset from the given field values and return it."""
    row = DimensionPreset(**fields)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_dimension_preset(
    session: Session, preset: DimensionPreset, **fields
) -> DimensionPreset:
    """Update the given dimension preset's fields and return the refreshed instance."""
    for key, value in fields.items():
        setattr(preset, key, value)
    session.add(preset)
    session.commit()
    session.refresh(preset)
    return preset


def delete_dimension_preset(session: Session, preset: DimensionPreset) -> None:
    """Delete the given dimension preset from the database."""
    session.delete(preset)
    session.commit()


def update_model_config(
    session: Session, model_config: ModelConfig, **fields
) -> ModelConfig:
    """Update the given model configuration's fields and return the refreshed instance."""
    for key, value in fields.items():
        setattr(model_config, key, value)
    session.add(model_config)
    session.commit()
    session.refresh(model_config)
    return model_config


def delete_model_config(session: Session, model_config: ModelConfig) -> None:
    """Delete the given model configuration from the database."""
    session.delete(model_config)
    session.commit()


def get_enhancement_config(session: Session) -> EnhancementConfig | None:
    """Return the singleton enhancement configuration row, or ``None`` if not configured."""
    stmt = select(EnhancementConfig).order_by(EnhancementConfig.id.asc())
    return session.scalar(stmt)


def get_provider_api_key(session: Session, provider: str) -> ProviderApiKey | None:
    """Return the stored API key row for *provider*, or ``None`` if not set."""
    stmt = select(ProviderApiKey).where(ProviderApiKey.provider == provider)
    return session.scalar(stmt)


def list_provider_api_keys(session: Session) -> list[ProviderApiKey]:
    """Return all stored provider API key rows ordered by provider name."""
    stmt = select(ProviderApiKey).order_by(ProviderApiKey.provider.asc())
    return list(session.scalars(stmt).all())


def upsert_provider_api_key(
    session: Session, provider: str, api_key_encrypted: str
) -> ProviderApiKey:
    """Insert or update the encrypted API key for *provider* and return the row."""
    existing = get_provider_api_key(session, provider)
    if existing:
        existing.api_key_encrypted = api_key_encrypted
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    row = ProviderApiKey(provider=provider, api_key_encrypted=api_key_encrypted)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def delete_provider_api_key(session: Session, provider: str) -> bool:
    """Delete the stored API key for *provider*. Returns ``True`` if a row was deleted."""
    existing = get_provider_api_key(session, provider)
    if not existing:
        return False
    session.delete(existing)
    session.commit()
    return True


def upsert_enhancement_config(
    session: Session,
    provider: str,
    model: str,
    api_key_encrypted: str | None,
) -> EnhancementConfig:
    """Insert or update the singleton enhancement configuration and return it."""
    existing = get_enhancement_config(session)
    if existing:
        existing.provider = provider
        existing.model = model
        existing.api_key_encrypted = api_key_encrypted
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    row = EnhancementConfig(
        provider=provider,
        model=model,
        api_key_encrypted=api_key_encrypted,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_profile(session: Session, profile_id: int) -> Profile | None:
    """Return a profile by primary key with related data eagerly loaded, or ``None``."""
    stmt = (
        select(Profile)
        .options(
            selectinload(Profile.storage_template),
            selectinload(Profile.model_config),
            selectinload(Profile.categories),
        )
        .where(Profile.id == profile_id)
    )
    return session.scalar(stmt)


def create_profile(session: Session, **fields) -> Profile:
    """Create a new profile from the given field values and return it."""
    profile = Profile(**fields)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def update_profile(session: Session, profile: Profile, **fields) -> Profile:
    """Update the given profile's fields and return the refreshed instance."""
    for key, value in fields.items():
        setattr(profile, key, value)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def delete_profile(session: Session, profile: Profile) -> None:
    """Delete the given profile from the database."""
    session.delete(profile)
    session.commit()


def create_generation(session: Session, generation: Generation) -> Generation:
    """Persist a new generation row and return the refreshed instance."""
    session.add(generation)
    session.commit()
    session.refresh(generation)
    return generation


def get_generation(
    session: Session, generation_id: int, with_assets: bool = False
) -> Generation | None:
    """Return a generation by primary key, optionally with assets loaded, or ``None``."""
    stmt: Select[tuple[Generation]] = select(Generation).where(
        Generation.id == generation_id
    )
    if with_assets:
        stmt = stmt.options(selectinload(Generation.assets))
    return session.scalar(stmt)


def get_asset(
    session: Session, asset_id: int, with_generation: bool = True
) -> Asset | None:
    """Return an asset by primary key, optionally with its generation loaded, or ``None``."""
    stmt: Select[tuple[Asset]] = select(Asset).where(Asset.id == asset_id)
    if with_generation:
        stmt = stmt.options(
            selectinload(Asset.generation), selectinload(Asset.categories)
        )
    return session.scalar(stmt)


def get_chat_session(session: Session, chat_session_id: str) -> ChatSession | None:
    """Return a chat session by its string ID with the last profile eagerly loaded, or ``None``."""
    stmt = (
        select(ChatSession)
        .options(selectinload(ChatSession.last_profile))
        .where(ChatSession.chat_session_id == chat_session_id)
    )
    return session.scalar(stmt)


def upsert_chat_session_preferences(
    session: Session,
    chat_session_id: str,
    last_profile_id: int | None = None,
    last_thumb_size: str | None = None,
) -> ChatSession:
    """Persist UI preferences for a chat session, creating the row if it does not yet exist."""
    existing = get_chat_session(session, chat_session_id)
    if existing:
        if last_profile_id is not None:
            existing.last_profile_id = last_profile_id
        if last_thumb_size is not None:
            existing.last_thumb_size = last_thumb_size
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    row = ChatSession(
        chat_session_id=chat_session_id,
        last_profile_id=last_profile_id,
        last_thumb_size=last_thumb_size or "md",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_styles(session: Session) -> list[Style]:
    """Return all styles ordered by name."""
    stmt = select(Style).order_by(Style.name.asc())
    return list(session.scalars(stmt).all())


def get_style(session: Session, style_id: int) -> Style | None:
    """Return a style by primary key, or ``None`` if not found."""
    stmt = select(Style).where(Style.id == style_id)
    return session.scalar(stmt)


def get_styles_by_ids(session: Session, style_ids: list[int]) -> list[Style]:
    """Return the styles whose IDs are in *style_ids*, ordered by name."""
    if not style_ids:
        return []
    stmt = select(Style).where(Style.id.in_(style_ids)).order_by(Style.name.asc())
    return list(session.scalars(stmt).all())


def create_style(session: Session, **fields) -> Style:
    """Create a new style from the given field values and return it."""
    row = Style(**fields)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_style(session: Session, style: Style, **fields) -> Style:
    """Update the given style's fields and return the refreshed instance."""
    for key, value in fields.items():
        setattr(style, key, value)
    session.add(style)
    session.commit()
    session.refresh(style)
    return style


def delete_style(session: Session, style: Style) -> None:
    """Delete the given style from the database."""
    session.delete(style)
    session.commit()
