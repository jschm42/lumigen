from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Asset, Generation, Profile, StorageTemplate


def ensure_default_storage_template(session: Session, base_dir: Path, template: str) -> StorageTemplate:
    existing_default = session.scalar(select(StorageTemplate).where(StorageTemplate.name == "default"))
    if existing_default:
        return existing_default

    any_template = session.scalar(select(StorageTemplate).limit(1))
    if any_template:
        return any_template

    row = StorageTemplate(name="default", base_dir=base_dir.resolve().as_posix(), template=template)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_storage_templates(session: Session) -> list[StorageTemplate]:
    stmt = select(StorageTemplate).order_by(StorageTemplate.name.asc())
    return list(session.scalars(stmt).all())


def list_profiles(session: Session) -> list[Profile]:
    stmt = select(Profile).options(selectinload(Profile.storage_template)).order_by(Profile.name.asc())
    return list(session.scalars(stmt).all())


def get_profile(session: Session, profile_id: int) -> Optional[Profile]:
    stmt = (
        select(Profile)
        .options(selectinload(Profile.storage_template))
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


def get_generation(session: Session, generation_id: int, with_assets: bool = False) -> Optional[Generation]:
    stmt: Select[tuple[Generation]] = select(Generation).where(Generation.id == generation_id)
    if with_assets:
        stmt = stmt.options(selectinload(Generation.assets))
    return session.scalar(stmt)


def get_asset(session: Session, asset_id: int, with_generation: bool = True) -> Optional[Asset]:
    stmt: Select[tuple[Asset]] = select(Asset).where(Asset.id == asset_id)
    if with_generation:
        stmt = stmt.options(selectinload(Asset.generation))
    return session.scalar(stmt)
