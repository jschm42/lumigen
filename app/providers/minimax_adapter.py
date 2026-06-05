from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from app.config import Settings
from app.providers.base import (
    ProviderAdapter,
    ProviderConfigError,
    ProviderError,
    ProviderGenerationRequest,
    ProviderGenerationResult,
    ProviderImage,
    ProviderRateLimitError,
    ProviderServiceUnavailableError,
)

# Curated list of MiniMax (Hailuo) image-generation model IDs returned by
# ``list_models`` when no API-driven listing is available.
_KNOWN_MODELS: list[str] = [
    "image-01",
    "image-01-live",
]

# Allowed aspect ratios for the MiniMax API. Source: the official image
# generation guide (https://platform.minimax.io/docs/guides/image-generation).
_ALLOWED_ASPECT_RATIOS: set[str] = {
    "1:1",
    "16:9",
    "9:16",
    "4:3",
    "3:4",
    "2:3",
    "3:2",
    "5:4",
    "4:5",
    "21:9",
}


class MiniMaxAdapter(ProviderAdapter):
    """Provider adapter for the MiniMax (Hailuo) image-generation API."""

    name = "minimax"
    display_name = "MiniMax (Hailuo)"
    homepage_url = "https://platform.minimax.io"
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        """Return the curated list of MiniMax image-generation model IDs."""
        _ = settings
        return list(_KNOWN_MODELS)

    async def generate(
        self, request: ProviderGenerationRequest, settings: Settings
    ) -> ProviderGenerationResult:
        """Submit a text-to-image request to MiniMax and return the result."""
        api_key = request.api_key or settings.minimax_api_key
        if not api_key:
            raise ProviderConfigError(
                "MiniMax adapter requires MINIMAX_API_KEY in .env or a custom API key."
            )

        url = settings.minimax_base_url.rstrip("/") + "/v1/image_generation"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        output_format = self._normalize_output_format(request.output_format)
        payload = self._build_payload(request, output_format=output_format)
        self._log_request("POST", url, headers, payload)

        timeout = httpx.Timeout(
            settings.llm_generate_timeout_seconds,
            connect=settings.llm_generate_connect_timeout_seconds,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 429:
            raise ProviderRateLimitError("MiniMax rate limit reached (429).")
        if response.status_code == 503:
            raise ProviderServiceUnavailableError(
                "MiniMax service unavailable (503)."
            )
        if response.status_code >= 500:
            raise ProviderServiceUnavailableError(
                f"MiniMax upstream error ({response.status_code})."
            )
        if response.status_code >= 400:
            message = self._extract_error_message(response)
            raise ProviderError(
                f"MiniMax request failed ({response.status_code}): {message}"
            )

        try:
            body = response.json()
        except Exception as exc:
            raise ProviderError("MiniMax returned a non-JSON response.") from exc

        width, height = self._resolve_dimensions(request)
        mime = self._mime_from_format(output_format)
        return ProviderGenerationResult(
            images=[
                self._build_image(
                    encoded=encoded, mime=mime, width=width, height=height, idx=idx
                )
                for idx, encoded in enumerate(self._extract_base64_list(body), start=1)
            ],
            raw_meta={
                "provider": self.name,
                "model": request.model,
                "count": len(self._extract_base64_list(body)),
            },
        )

    def _build_payload(
        self, request: ProviderGenerationRequest, *, output_format: str
    ) -> dict[str, Any]:
        """Return the MiniMax request body for a text-to-image generation."""
        payload: dict[str, Any] = {
            "model": request.model,
            "prompt": request.prompt,
            "aspect_ratio": self._resolve_aspect_ratio(request),
            "response_format": "base64",
        }
        n_images = max(1, int(request.n_images))
        if n_images > 1:
            payload["n"] = n_images

        if isinstance(request.params, dict):
            subject_reference = request.params.get("subject_reference")
            if subject_reference and not request.input_images:
                payload["subject_reference"] = subject_reference

        if request.input_images:
            payload["subject_reference"] = self._build_subject_reference(
                request.input_images
            )

        return payload

    def _build_subject_reference(
        self, input_images: list[Any]
    ) -> list[dict[str, str]]:
        """Encode input images as data URLs for ``subject_reference``."""
        references: list[dict[str, str]] = []
        for image in input_images:
            if not image.data or not image.mime:
                continue
            encoded = base64.b64encode(image.data).decode("ascii")
            data_url = f"data:{image.mime};base64,{encoded}"
            references.append({"type": "character", "image_file": data_url})
        return references

    def _extract_base64_list(self, body: dict[str, Any]) -> list[str]:
        """Extract the list of base64 image strings from a MiniMax response."""
        data = body.get("data")
        if not isinstance(data, dict):
            return []
        image_base64 = data.get("image_base64")
        if not isinstance(image_base64, list):
            return []
        return [str(item) for item in image_base64 if str(item).strip()]

    def _build_image(
        self,
        *,
        encoded: str,
        mime: str,
        width: int,
        height: int,
        idx: int,
    ) -> ProviderImage:
        """Decode a single base64 image string into a :class:`ProviderImage`."""
        try:
            image_bytes = base64.b64decode(encoded)
        except Exception as exc:
            raise ProviderError(
                f"Failed to decode MiniMax image payload at index {idx}."
            ) from exc
        return ProviderImage(
            data=image_bytes,
            mime=mime,
            width=width,
            height=height,
            meta={"provider": self.name, "index": idx},
        )

    def _resolve_aspect_ratio(self, request: ProviderGenerationRequest) -> str:
        """Return an aspect ratio string accepted by the MiniMax API."""
        if isinstance(request.params, dict):
            raw = request.params.get("aspect_ratio")
            if isinstance(raw, str) and raw.strip() in _ALLOWED_ASPECT_RATIOS:
                return raw.strip()
        if request.width and request.height:
            ratio = self._aspect_from_dimensions(
                int(request.width), int(request.height)
            )
            if ratio in _ALLOWED_ASPECT_RATIOS:
                return ratio
        return "1:1"

    @staticmethod
    def _aspect_from_dimensions(width: int, height: int) -> str:
        """Return the closest ``W:H`` string for the given pixel dimensions."""
        if width <= 0 or height <= 0:
            return "1:1"
        from math import gcd

        divisor = gcd(width, height)
        return f"{width // divisor}:{height // divisor}"

    def _resolve_dimensions(
        self, request: ProviderGenerationRequest
    ) -> tuple[int, int]:
        if request.width and request.height:
            return int(request.width), int(request.height)
        return 1024, 1024

    def _normalize_output_format(self, value: str | None) -> str:
        raw = (value or "png").strip().lower().lstrip(".")
        if raw in {"jpg", "jpeg"}:
            return "jpeg"
        if raw in {"png", "webp"}:
            return raw
        return "png"

    def _mime_from_format(self, fmt: str) -> str:
        if fmt == "jpeg":
            return "image/jpeg"
        if fmt == "webp":
            return "image/webp"
        return "image/png"

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except Exception:
            text = response.text.strip()
            return text[:400] if text else "Unknown error"

        if isinstance(data, dict):
            for key in ("message", "error", "detail", "msg"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, dict):
                    nested = value.get("message")
                    if isinstance(nested, str) and nested.strip():
                        return nested.strip()
        text = str(data)
        return text[:400]
