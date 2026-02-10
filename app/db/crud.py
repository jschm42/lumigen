from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Asset,
    EnhancementConfig,
    GalleryFolder,
    Generation,
    ModelConfig,
    Profile,
    StorageTemplate,
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


def list_profiles(session: Session) -> list[Profile]:
    stmt = (
        select(Profile)
        .options(
            selectinload(Profile.storage_template), selectinload(Profile.model_config)
        )
        .order_by(Profile.name.asc())
    )
    return list(session.scalars(stmt).all())


def list_model_configs(session: Session) -> list[ModelConfig]:
    stmt = select(ModelConfig).order_by(ModelConfig.name.asc())
    return list(session.scalars(stmt).all())


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
            selectinload(Profile.storage_template), selectinload(Profile.model_config)
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
            selectinload(Asset.generation), selectinload(Asset.gallery_folder)
        )
    return session.scalar(stmt)


def list_gallery_folders(session: Session) -> list[GalleryFolder]:
    stmt = select(GalleryFolder).order_by(GalleryFolder.path.asc())
    return list(session.scalars(stmt).all())


def get_gallery_folder(session: Session, folder_id: int) -> Optional[GalleryFolder]:
    stmt = select(GalleryFolder).where(GalleryFolder.id == folder_id)
    return session.scalar(stmt)


def get_gallery_folder_by_path(session: Session, path: str) -> Optional[GalleryFolder]:
    stmt = select(GalleryFolder).where(GalleryFolder.path == path)
    return session.scalar(stmt)


def create_gallery_folder(session: Session, path: str) -> GalleryFolder:
    folder = GalleryFolder(path=path)
    session.add(folder)
    session.commit()
    session.refresh(folder)
    return folder
