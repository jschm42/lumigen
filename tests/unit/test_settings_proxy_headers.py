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