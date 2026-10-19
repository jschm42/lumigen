from __future__ import annotations

from app.config import Settings


def test_proxy_header_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.proxy_headers_enabled is False
    assert settings.proxy_headers_trusted_hosts == "127.0.0.1"


def test_proxy_header_settings_can_be_overridden() -> None:
    settings = Settings(
        _env_file=None,
        proxy_headers_enabled=True,
        proxy_headers_trusted_hosts="*",
    )

    assert settings.proxy_headers_enabled is True
    assert settings.proxy_headers_trusted_hosts == "*"

def test_max_upload_size_mb_defaults_to_none() -> None:
    settings = Settings(_env_file=None)

    assert settings.max_upload_size_mb is None


def test_max_upload_size_mb_can_be_set() -> None:
    settings = Settings(_env_file=None, max_upload_size_mb=10)

    assert settings.max_upload_size_mb == 10


def test_llm_timeout_settings_have_safe_defaults_without_env_file() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_models_timeout_seconds == 30.0
    assert settings.llm_models_connect_timeout_seconds == 10.0
    assert settings.llm_generate_timeout_seconds == 60.0
    assert settings.llm_generate_connect_timeout_seconds == 10.0
    assert settings.llm_enhancement_timeout_seconds == 60.0
    assert settings.llm_enhancement_connect_timeout_seconds == 10.0
    assert settings.provider_openrouter_generate_timeout_seconds == 120.0
    assert settings.provider_google_generate_timeout_seconds == 240.0
    assert settings.provider_google_generate_connect_timeout_seconds == 15.0
    assert settings.provider_bfl_download_timeout_seconds == 60.0
    assert settings.provider_bfl_download_connect_timeout_seconds == 30.0
