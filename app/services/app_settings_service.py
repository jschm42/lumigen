"""Runtime studio settings that admins can change from the UI."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db import crud

# Setting key -> (default value, python type). Only these keys are accepted.
UI_SETTING_DEFAULTS: dict[str, tuple[Any, type]] = {
    "show_token_usage": (False, bool),
}


class AppSettingsService:
    """Read and update the whitelisted studio-wide UI settings."""

    def get_ui_settings(self, session: Session) -> dict[str, Any]:
        """Return every known UI setting, falling back to its default value."""
        result: dict[str, Any] = {}
        for key, (default, value_type) in UI_SETTING_DEFAULTS.items():
            value = crud.get_app_setting(session, key, default)
            result[key] = value if isinstance(value, value_type) else default
        return result

    def update_ui_settings(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist known keys from *payload* (unknown keys are ignored) and return all settings.

        Raises ``ValueError`` when a value has the wrong type.
        """
        for key, value in payload.items():
            spec = UI_SETTING_DEFAULTS.get(key)
            if spec is None:
                continue
            _default, value_type = spec
            if not isinstance(value, value_type):
                raise ValueError(f"Setting '{key}' must be of type {value_type.__name__}.")
            crud.set_app_setting(session, key, value)
        return self.get_ui_settings(session)
