from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


profile_categories = Table(
    "profile_categories",
    Base.metadata,
    Column("profile_id", ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "category_id",
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


asset_categories = Table(
    "asset_categories",
    Base.metadata,
    Column("asset_id", ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "category_id",
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class StorageTemplate(Base, TimestampMixin):
    __tablename__ = "storage_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    base_dir: Mapped[str] = mapped_column(String(1024), nullable=False)
    template: Mapped[str] = mapped_column(String(1024), nullable=False)

    profiles: Mapped[list[Profile]] = relationship(back_populates="storage_template")


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    model_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_configs.id", ondelete="SET NULL"),
        nullable=True,
    )
    base_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aspect_ratio: Mapped[str | None] = mapped_column(String(32), nullable=True)
    n_images: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_format: Mapped[str] = mapped_column(
        String(16), default="png", nullable=False
    )
    upscale_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    params_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )

    storage_template_id: Mapped[int] = mapped_column(
        ForeignKey("storage_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )

    storage_template: Mapped[StorageTemplate] = relationship(back_populates="profiles")
    model_config: Mapped[ModelConfig | None] = relationship(
        back_populates="profiles"
    )
    generations: Mapped[list[Generation]] = relationship(back_populates="profile")
    categories: Mapped[list[Category]] = relationship(
        secondary=profile_categories,
        back_populates="profiles",
    )


class ModelConfig(Base, TimestampMixin):
    __tablename__ = "model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    enhancement_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(
        String(4096), nullable=True
    )
    use_custom_api_key: Mapped[bool] = mapped_column(
        Boolean(), default=False, nullable=False
    )

    profiles: Mapped[list[Profile]] = relationship(back_populates="model_config")


class EnhancementConfig(Base, TimestampMixin):
    __tablename__ = "enhancement_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(
        String(4096), nullable=True
    )


class DimensionPreset(Base, TimestampMixin):
    __tablename__ = "dimension_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)

    profiles: Mapped[list[Profile]] = relationship(
        secondary=profile_categories,
        back_populates="categories",
    )
    assets: Mapped[list[Asset]] = relationship(
        secondary=asset_categories,
        back_populates="categories",
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True, nullable=False)


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_session_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    last_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_thumb_size: Mapped[str] = mapped_column(
        String(10), default="md", nullable=False
    )

    last_profile: Mapped[Profile | None] = relationship()


class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    profile_name: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_user: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_final: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    storage_template_snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    request_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    failure_sidecar_path: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    profile: Mapped[Profile | None] = relationship(back_populates="generations")
    assets: Mapped[list[Asset]] = relationship(
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
    file_path: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    sidecar_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    thumbnail_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    mime: Mapped[str] = mapped_column(String(64), nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    generation: Mapped[Generation] = relationship(back_populates="assets")
    categories: Mapped[list[Category]] = relationship(
        secondary=asset_categories,
        back_populates="assets",
    )
