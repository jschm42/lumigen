from __future__ import annotations

from pathlib import Path
from typing import Optional

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
    StorageTemplate,
    User,
)


def ensure_default_storage_template(
    session: Session, base_dir: Path, template: str
) -> StorageTemplate:
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
    stmt = select(StorageTemplate).order_by(StorageTemplate.name.asc())
    return list(session.scalars(stmt).all())


def count_users(session: Session) -> int:
    stmt = select(User.id)
    return len(list(session.scalars(stmt).all()))


def list_users(session: Session) -> list[User]:
    stmt = select(User).order_by(User.username.asc())
    return list(session.scalars(stmt).all())


def count_admin_users(session: Session, *, active_only: bool = True) -> int:
    stmt = select(User.id).where(User.role == "admin")
    if active_only:
        stmt = stmt.where(User.is_active.is_(True))
    return len(list(session.scalars(stmt).all()))


def get_user(session: Session, user_id: int) -> Optional[User]:
    stmt = select(User).where(User.id == user_id)
    return session.scalar(stmt)


def get_user_by_username(session: Session, username: str) -> Optional[User]:
    stmt = select(User).where(User.username == username)
    return session.scalar(stmt)


def create_user(session: Session, **fields) -> User:
    row = User(**fields)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_user(session: Session, user: User, **fields) -> User:
    for key, value in fields.items():
        setattr(user, key, value)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def delete_user(session: Session, user: User) -> None:
    session.delete(user)
    session.commit()


def delete_all_users(session: Session) -> None:
    session.query(User).delete()
    session.commit()


def list_profiles(session: Session) -> list[Profile]:
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
    stmt = select(ModelConfig).order_by(ModelConfig.name.asc())
    return list(session.scalars(stmt).all())


def list_dimension_presets(session: Session) -> list[DimensionPreset]:
    stmt = select(DimensionPreset).order_by(DimensionPreset.name.asc())
    return list(session.scalars(stmt).all())


def list_categories(session: Session) -> list[Category]:
    stmt = select(Category).order_by(Category.name.asc())
    return list(session.scalars(stmt).all())


def list_categories_by_ids(session: Session, category_ids: list[int]) -> list[Category]:
    if not category_ids:
        return []
    stmt = select(Category).where(Category.id.in_(category_ids)).order_by(Category.name.asc())
    return list(session.scalars(stmt).all())


def get_category(session: Session, category_id: int) -> Optional[Category]:
    stmt = select(Category).where(Category.id == category_id)
    return session.scalar(stmt)


def create_category(session: Session, **fields) -> Category:
    row = Category(**fields)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_category(session: Session, category: Category, **fields) -> Category:
    for key, value in fields.items():
        setattr(category, key, value)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def delete_category(session: Session, category: Category) -> None:
    session.delete(category)
    session.commit()


def get_model_config(session: Session, model_config_id: int) -> Optional[ModelConfig]:
    stmt = select(ModelConfig).where(ModelConfig.id == model_config_id)
    return session.scalar(stmt)


def get_model_config_by_name(session: Session, name: str) -> Optional[ModelConfig]:
    stmt = select(ModelConfig).where(ModelConfig.name == name)
    return session.scalar(stmt)


def create_model_config(session: Session, **fields) -> ModelConfig:
    row = ModelConfig(**fields)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_dimension_preset(
    session: Session, preset_id: int
) -> Optional[DimensionPreset]:
    stmt = select(DimensionPreset).where(DimensionPreset.id == preset_id)
    return session.scalar(stmt)


def create_dimension_preset(session: Session, **fields) -> DimensionPreset:
    row = DimensionPreset(**fields)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_dimension_preset(
    session: Session, preset: DimensionPreset, **fields
) -> DimensionPreset:
    for key, value in fields.items():
        setattr(preset, key, value)
    session.add(preset)
    session.commit()
    session.refresh(preset)
    return preset


def delete_dimension_preset(session: Session, preset: DimensionPreset) -> None:
    session.delete(preset)
    session.commit()


def update_model_config(
    session: Session, model_config: ModelConfig, **fields
) -> ModelConfig:
    for key, value in fields.items():
        setattr(model_config, key, value)
    session.add(model_config)
    session.commit()
    session.refresh(model_config)
    return model_config


def delete_model_config(session: Session, model_config: ModelConfig) -> None:
    session.delete(model_config)
    session.commit()


def get_enhancement_config(session: Session) -> Optional[EnhancementConfig]:
    stmt = select(EnhancementConfig).order_by(EnhancementConfig.id.asc())
    return session.scalar(stmt)


def upsert_enhancement_config(
    session: Session,
    provider: str,
    model: str,
    api_key_encrypted: Optional[str],
) -> EnhancementConfig:
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


def get_profile(session: Session, profile_id: int) -> Optional[Profile]:
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
    profile = Profile(**fields)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def update_profile(session: Session, profile: Profile, **fields) -> Profile:
    for key, value in fields.items():
        setattr(profile, key, value)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def delete_profile(session: Session, profile: Profile) -> None:
    session.delete(profile)
    session.commit()


def create_generation(session: Session, generation: Generation) -> Generation:
    session.add(generation)
    session.commit()
    session.refresh(generation)
    return generation


def get_generation(
    session: Session, generation_id: int, with_assets: bool = False
) -> Optional[Generation]:
    stmt: Select[tuple[Generation]] = select(Generation).where(
        Generation.id == generation_id
    )
    if with_assets:
        stmt = stmt.options(selectinload(Generation.assets))
    return session.scalar(stmt)


def get_asset(
    session: Session, asset_id: int, with_generation: bool = True
) -> Optional[Asset]:
    stmt: Select[tuple[Asset]] = select(Asset).where(Asset.id == asset_id)
    if with_generation:
        stmt = stmt.options(
            selectinload(Asset.generation), selectinload(Asset.categories)
        )
    return session.scalar(stmt)


def get_chat_session(session: Session, chat_session_id: str) -> Optional[ChatSession]:
    stmt = (
        select(ChatSession)
        .options(selectinload(ChatSession.last_profile))
        .where(ChatSession.chat_session_id == chat_session_id)
    )
    return session.scalar(stmt)


def upsert_chat_session_preferences(
    session: Session,
    chat_session_id: str,
    last_profile_id: Optional[int] = None,
    last_thumb_size: Optional[str] = None,
) -> ChatSession:
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
