"""Runtime studio settings that admins can change from the UI."""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.db import crud

# Setting key -> (default value, python type). Only these keys are accepted.
UI_SETTING_DEFAULTS: dict[str, tuple[Any, type]] = {
    "show_token_usage": (False, bool),
    # ISO 4217 code used for all configured model prices and displayed costs.
    "cost_currency": ("USD", str),
    # Limits for agentic GIF animations (see docs/concepts/agentic-gif-animation.md).
    "animation_max_frames": (24, int),
    "animation_max_dimension_px": (512, int),
    "animation_max_file_size_mb": (10, int),
    "animation_default_frame_ms": (100, int),
}

# Hard caps for integer settings: (minimum, maximum). Values outside are rejected.
INT_SETTING_RANGES: dict[str, tuple[int, int]] = {
    "animation_max_frames": (2, 64),
    "animation_max_dimension_px": (128, 1024),
    "animation_max_file_size_mb": (1, 50),
    "animation_default_frame_ms": (20, 1000),
}

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def _matches_type(value: Any, value_type: type) -> bool:
    """Return True if *value* is of *value_type*; booleans never count as integers."""
    if value_type is int and isinstance(value, bool):
        return False
    return isinstance(value, value_type)


class AppSettingsService:
    """Read and update the whitelisted studio-wide UI settings."""

    def get_ui_settings(self, session: Session) -> dict[str, Any]:
        """Return every known UI setting, falling back to its default value.

        Stored integers outside their allowed range also fall back to the default.
        """
        result: dict[str, Any] = {}
        for key, (default, value_type) in UI_SETTING_DEFAULTS.items():
            value = crud.get_app_setting(session, key, default)
            if not _matches_type(value, value_type):
                value = default
            bounds = INT_SETTING_RANGES.get(key)
            if bounds is not None and not bounds[0] <= value <= bounds[1]:
                value = default
            result[key] = value
        return result

    def update_ui_settings(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist known keys from *payload* (unknown keys are ignored) and return all settings.

        Raises ``ValueError`` when a value has the wrong type or is out of range.
        """
        for key, value in payload.items():
            spec = UI_SETTING_DEFAULTS.get(key)
            if spec is None:
                continue
            _default, value_type = spec
            if not _matches_type(value, value_type):
                raise ValueError(f"Setting '{key}' must be of type {value_type.__name__}.")
            if key == "cost_currency":
                value = value.strip().upper()
                if not _CURRENCY_RE.match(value):
                    raise ValueError("Currency must be a 3-letter ISO 4217 code (e.g. USD, EUR).")
            bounds = INT_SETTING_RANGES.get(key)
            if bounds is not None and not bounds[0] <= value <= bounds[1]:
                raise ValueError(f"Setting '{key}' must be between {bounds[0]} and {bounds[1]}.")
            crud.set_app_setting(session, key, value)
        return self.get_ui_settings(session)
