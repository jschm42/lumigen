from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings


@dataclass
class ProviderGenerationRequest:
    """Parameters for a single image-generation request sent to a provider."""

    prompt: str
    width: int | None
    height: int | None
    n_images: int
    seed: int | None
    output_format: str
    model: str
    api_key: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    input_images: list[ProviderInputImage] = field(default_factory=list)


@dataclass
class ProviderInputImage:
    """Raw image bytes with MIME type, used as input for image-to-image generation."""

    data: bytes
    mime: str


@dataclass
class ProviderImage:
    """A single generated image together with its dimensions and optional metadata."""

    data: bytes
    mime: str
    width: int
    height: int
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderGenerationResult:
    """The result of a generation request: a list of images and optional raw metadata."""

    images: list[ProviderImage]
    raw_meta: dict[str, Any] = field(default_factory=dict)


class ProviderError(RuntimeError):
    """Base exception for all provider-related errors."""


class ProviderConfigError(ProviderError):
    """Raised when a provider is misconfigured (e.g. missing or invalid API key)."""


class ProviderRateLimitError(ProviderError):
    """Raised when the provider returns a rate-limit (429) response."""


class ProviderServiceUnavailableError(ProviderError):
    """Raised when the provider service is temporarily unavailable (e.g. 503)."""


class ProviderAdapter(ABC):
    """Abstract base class for all provider adapters."""
    name: str
    display_name: str = ""
    homepage_url: str = ""
    _logger: logging.Logger = logging.getLogger(__name__)

    def _log_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Logs an outgoing provider HTTP request at DEBUG level.

        Sensitive header values (containing 'key' or 'auth') are masked.
        Base64-encoded image data inside the payload is also redacted to
        avoid flooding the log with multi-megabyte image strings.
        """
        safe_headers = {
            k: ("***" if "key" in k.lower() or "auth" in k.lower() else v)
            for k, v in headers.items()
        }
        safe_payload = self._scrub_base64_in_payload(payload) if payload is not None else None
        self._logger.debug(
            "[%s] → %s %s\nHeaders: %s\nPayload: %s",
            self.name,
            method.upper(),
            url,
            json.dumps(safe_headers, indent=2),
            json.dumps(safe_payload, indent=2, default=str) if safe_payload is not None else "(none)",
        )

    @classmethod
    def _scrub_base64_in_payload(cls, value: Any) -> Any:
        """Return a copy of *value* with base64 image data redacted.

        Replaces ``data:<mime>;base64,<data>`` strings (anywhere they appear)
        and string values whose key path looks like a base64 image field
        (e.g. ``b64_json``, ``image_base64``) with a short placeholder that
        preserves the original length. Other data is left untouched.
        """
        return cls._scrub_base64_value(value, "")

    @classmethod
    def _scrub_base64_value(cls, value: Any, key: str) -> Any:
        """Apply per-key heuristics before falling back to the generic scrubber."""
        if isinstance(value, dict):
            return {
                k: cls._scrub_base64_value(v, f"{key}.{k}" if key else str(k))
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [cls._scrub_base64_value(item, key) for item in value]
        if isinstance(value, tuple):
            return tuple(cls._scrub_base64_value(item, key) for item in value)
        if isinstance(value, str):
            if cls._is_base64_key(key):
                return f"<base64 blob: {len(value)} chars>"
            return cls._scrub_base64_string(value)
        return value

    @staticmethod
    def _is_base64_key(key: str) -> bool:
        """Return True if *key* is a known field name that carries base64 image data."""
        normalized = key.strip().lower()
        if not normalized:
            return False
        return any(
            token in normalized
            for token in (
                "b64",
                "base64",
                "bytesbase64encoded",
                "bytes_base64_encoded",
                "input_image",
                "image_url",
                "image_b64",
                "image_base64",
                "subject_reference",
            )
        ) or normalized in {
            "data",
            "image",
            "mask",
            "url",
        }

    @staticmethod
    def _scrub_base64_string(value: str) -> str:
        """Redact embedded ``data:...;base64,...`` URLs in a free-form string value."""
        if not value or "base64," not in value.lower():
            return value
        data_url_re = re.compile(r"data:[^;,\s]+;base64,[A-Za-z0-9+/=_\-]+", re.IGNORECASE)

        def _replace_data_url(match: re.Match[str]) -> str:
            prefix, payload = match.group(0).split(",", 1)
            return f"{prefix},<base64 image: {len(payload)} chars>"

        return data_url_re.sub(_replace_data_url, value)

    @abstractmethod
    async def generate(
        self, request: ProviderGenerationRequest, settings: Settings
    ) -> ProviderGenerationResult:
        """Send *request* to the provider and return the generation result."""
        raise NotImplementedError

    async def list_models(self, settings: Settings) -> list[str]:
        """Return the list of model IDs available from this provider. Defaults to an empty list."""
        return []
