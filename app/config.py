from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# App version
VERSION = "0.1.0"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Lumigen"
    app_version: str = VERSION
    log_level: str = "INFO"

    data_dir: Path = Path("./data")
    sqlite_path: Path = Path("./data/app.db")
    default_base_dir: Path = Path("./data/images")
    default_storage_template: str = "/{profile}/{yyyy}/{mm}/{slug}-{gen_id}-{idx}.{ext}"

    default_page_size: int = 24
    max_slug_length: int = 64
    thumb_max_px: int = 384

    provider_default_max_concurrent: int = 2
    provider_default_min_interval_ms: int = 250
    provider_default_retry_max_attempts: int = 4
    provider_default_retry_base_delay_ms: int = 400
    provider_default_retry_max_delay_ms: int = 5000

    provider_stub_max_concurrent: int = 4
    provider_stub_min_interval_ms: int = 50

    provider_openai_max_concurrent: int = 1
    provider_openai_min_interval_ms: int = 800

    provider_openrouter_max_concurrent: int = 1
    provider_openrouter_min_interval_ms: int = 800

    provider_google_max_concurrent: int = 1
    provider_google_min_interval_ms: int = 800

    provider_bfl_max_concurrent: int = 1
    provider_bfl_min_interval_ms: int = 800

    provider_config_key: str | None = None

    session_secret_key: str = "dev-insecure-session-key-change-me"
    session_cookie_name: str = "lumigen_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 7
    session_https_only: bool = False
    proxy_headers_enabled: bool = False
    proxy_headers_trusted_hosts: str = "127.0.0.1"
    csrf_token_ttl_seconds: int = 60 * 60 * 8
    auth_allow_onboarding_reset: bool = False

    upscaler_command: str | None = None
    upscaler_model_dir: Path = Path("./data/models/realesrgan")

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    google_api_key: str | None = None
    google_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    bfl_api_key: str | None = None

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.sqlite_path.resolve().as_posix()}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
