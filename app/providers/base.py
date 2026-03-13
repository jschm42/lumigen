from __future__ import annotations

import json
import logging
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
        """
        safe_headers = {
            k: ("***" if "key" in k.lower() or "auth" in k.lower() else v)
            for k, v in headers.items()
        }
        self._logger.debug(
            "[%s] → %s %s\nHeaders: %s\nPayload: %s",
            self.name,
            method.upper(),
            url,
            json.dumps(safe_headers, indent=2),
            json.dumps(payload, indent=2, default=str) if payload is not None else "(none)",
        )

    @abstractmethod
    async def generate(
        self, request: ProviderGenerationRequest, settings: Settings
    ) -> ProviderGenerationResult:
        """Send *request* to the provider and return the generation result."""
        raise NotImplementedError

    async def list_models(self, settings: Settings) -> list[str]:
        """Return the list of model IDs available from this provider. Defaults to an empty list."""
        return []
