from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class StorageTemplate(Base, TimestampMixin):
    __tablename__ = "storage_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    base_dir: Mapped[str] = mapped_column(String(1024), nullable=False)
    template: Mapped[str] = mapped_column(String(1024), nullable=False)

    profiles: Mapped[list["Profile"]] = relationship(back_populates="storage_template")


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    model_config_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("model_configs.id", ondelete="SET NULL"),
        nullable=True,
    )
    base_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    negative_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    aspect_ratio: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    n_images: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_format: Mapped[str] = mapped_column(
        String(16), default="png", nullable=False
    )
    params_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )

    storage_template_id: Mapped[int] = mapped_column(
        ForeignKey("storage_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )

    storage_template: Mapped[StorageTemplate] = relationship(back_populates="profiles")
    model_config: Mapped[Optional["ModelConfig"]] = relationship(
        back_populates="profiles"
    )
    generations: Mapped[list["Generation"]] = relationship(back_populates="profile")


class GalleryFolder(Base, TimestampMixin):
    __tablename__ = "gallery_folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)

    assets: Mapped[list["Asset"]] = relationship(back_populates="gallery_folder")


class ModelConfig(Base, TimestampMixin):
    __tablename__ = "model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(
        String(4096), nullable=True
    )

    profiles: Mapped[list["Profile"]] = relationship(back_populates="model_config")


class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    profile_name: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_user: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_final: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    profile_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    storage_template_snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    request_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    failure_sidecar_path: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    profile: Mapped[Optional[Profile]] = relationship(back_populates="generations")
    assets: Mapped[list["Asset"]] = relationship(
        back_populates="generation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generation_id: Mapped[int] = mapped_column(
        ForeignKey("generations.id", ondelete="CASCADE"),
        nullable=False,
    )
    gallery_folder_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("gallery_folders.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_path: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    sidecar_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    thumbnail_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    mime: Mapped[str] = mapped_column(String(64), nullable=False)
    meta_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    generation: Mapped[Generation] = relationship(back_populates="assets")
    gallery_folder: Mapped[Optional[GalleryFolder]] = relationship(
        back_populates="assets"
    )
