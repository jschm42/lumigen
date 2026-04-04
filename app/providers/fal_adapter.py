from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError

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

# Curated list of popular FAL.ai image-generation models returned by list_models
# when no API-driven listing is available.
_KNOWN_MODELS: list[str] = [
    "fal-ai/flux/schnell",
    "fal-ai/flux/dev",
    "fal-ai/flux-pro",
    "fal-ai/flux-pro/v1.1",
    "fal-ai/flux-pro/v1.1-ultra",
    "fal-ai/stable-diffusion-xl",
    "fal-ai/aura-flow",
]

_LEGACY_FAL_IMAGE_SIZE_TO_ASPECT_RATIO: dict[str, str] = {
    "square_hd": "1:1",
    "square": "1:1",
    "portrait_4_3": "3:4",
    "portrait_16_9": "9:16",
    "landscape_4_3": "4:3",
    "landscape_16_9": "16:9",
}


class FalAdapter(ProviderAdapter):
    """Provider adapter for the FAL.ai image-generation API (queue-based)."""

    name = "fal"
    BASE_URL = "https://fal.run"
    QUEUE_URL = "https://queue.fal.run"
    MAX_POLL_ATTEMPTS = 90
    POLL_INTERVAL = 2.0  # seconds
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        """Return a curated list of popular FAL.ai image-generation model IDs."""
        return list(_KNOWN_MODELS)

    async def generate(
        self, request: ProviderGenerationRequest, settings: Settings
    ) -> ProviderGenerationResult:
        """Submit a generation request to FAL.ai via the queue API and return images.

        Posts to the queue endpoint, polls for completion, downloads image URLs,
        and returns a ``ProviderGenerationResult`` with the generated images.
        """
        api_key = request.api_key or settings.fal_api_key
        if not api_key:
            raise ProviderConfigError(
                "FAL adapter requires FAL_API_KEY in .env or a custom API key."
            )

        if request.input_images:
            raise ProviderError(
                "FAL provider does not support input images."
            )

        queue_url = f"{self.QUEUE_URL}/{request.model}"
        headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_payload(request)
        self._log_request("POST", queue_url, headers, payload)

        timeout = httpx.Timeout(60.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(queue_url, headers=headers, json=payload)

            if response.status_code == 429:
                raise ProviderRateLimitError("FAL rate limit reached (429).")
            if response.status_code == 503:
                raise ProviderServiceUnavailableError(
                    "FAL service unavailable (503)."
                )
            if response.status_code >= 500:
                raise ProviderServiceUnavailableError(
                    f"FAL upstream error ({response.status_code})."
                )
            if response.status_code >= 400:
                message = self._extract_error_message(response)
                raise ProviderError(
                    f"FAL request failed ({response.status_code}): {message}"
                )

            try:
                submit_result = response.json()
            except Exception as exc:
                raise ProviderError("FAL returned a non-JSON response.") from exc

            request_id = submit_result.get("request_id")
            if not request_id:
                raise ProviderError(
                    f"FAL did not return a request_id. Response: {submit_result}"
                )

            images = await self._poll_for_result(
                client, request.model, request_id, api_key, request
            )

        return ProviderGenerationResult(
            images=images,
            raw_meta={
                "provider": self.name,
                "request_id": request_id,
                "model": request.model,
                "count": len(images),
            },
        )

    async def _poll_for_result(
        self,
        client: httpx.AsyncClient,
        model: str,
        request_id: str,
        api_key: str,
        request: ProviderGenerationRequest,
    ) -> list[ProviderImage]:
        """Poll the FAL queue until the request is COMPLETED, then fetch and return images."""
        status_url = f"{self.QUEUE_URL}/{model}/requests/{request_id}/status"
        result_url = f"{self.QUEUE_URL}/{model}/requests/{request_id}"
        headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(self.MAX_POLL_ATTEMPTS):
            await asyncio.sleep(self.POLL_INTERVAL)

            response = await client.get(status_url, headers=headers)

            if response.status_code >= 500:
                if attempt < self.MAX_POLL_ATTEMPTS - 1:
                    continue
                raise ProviderServiceUnavailableError(
                    f"FAL polling failed ({response.status_code})."
                )

            if response.status_code >= 400:
                message = self._extract_error_message(response)
                raise ProviderError(
                    f"FAL polling failed ({response.status_code}): {message}"
                )

            try:
                status_body = response.json()
            except Exception as exc:
                raise ProviderError("FAL polling returned non-JSON.") from exc

            status = (status_body.get("status") or "").upper()

            if status == "COMPLETED":
                result_response = await client.get(result_url, headers=headers)
                if result_response.status_code >= 400:
                    message = self._extract_error_message(result_response)
                    raise ProviderError(
                        f"FAL result fetch failed ({result_response.status_code}): {message}"
                    )
                try:
                    result_body = result_response.json()
                except Exception as exc:
                    raise ProviderError(
                        "FAL result returned non-JSON."
                    ) from exc
                return await self._extract_images(result_body, request, client)

            elif status == "FAILED":
                detail = status_body.get("error") or status_body.get("detail") or "Unknown error"
                self._logger.error(
                    "FAL generation failed: %s, status_body=%s", detail, status_body
                )
                raise ProviderError(f"FAL generation failed: {detail}")

            elif status in ("IN_QUEUE", "IN_PROGRESS"):
                continue

            else:
                if attempt < self.MAX_POLL_ATTEMPTS - 1:
                    continue
                raise ProviderError(
                    f"FAL polling timed out after {self.MAX_POLL_ATTEMPTS} attempts. "
                    f"Last status: {status}"
                )

        raise ProviderError(
            f"FAL polling timed out after {self.MAX_POLL_ATTEMPTS} attempts."
        )

    async def _extract_images(
        self,
        result: dict[str, Any],
        request: ProviderGenerationRequest,
        client: httpx.AsyncClient,
    ) -> list[ProviderImage]:
        """Download image URLs from the FAL result and return a list of ``ProviderImage`` objects."""
        images_data = result.get("images") or []
        if not images_data:
            raise ProviderError("FAL result does not contain any images.")

        images: list[ProviderImage] = []
        for idx, item in enumerate(images_data, start=1):
            if not isinstance(item, dict):
                raise ProviderError(
                    f"FAL image item at index {idx} is not a dict: {type(item)}"
                )

            image_url = item.get("url")
            if not image_url:
                raise ProviderError(
                    f"FAL image item at index {idx} has no 'url' field."
                )

            try:
                img_response = await client.get(image_url)
                img_response.raise_for_status()
                image_bytes = img_response.content
            except Exception as exc:
                raise ProviderError(
                    f"Failed to fetch FAL image from URL at index {idx}: {exc}"
                ) from exc

            fallback_width = item.get("width") or request.width or 1024
            fallback_height = item.get("height") or request.height or 1024
            width, height = self._probe_dimensions(
                image_bytes, int(fallback_width), int(fallback_height)
            )

            content_type = item.get("content_type") or ""
            mime = self._mime_from_content_type(
                content_type, self._normalize_output_format(request.output_format)
            )

            images.append(
                ProviderImage(
                    data=image_bytes,
                    mime=mime,
                    width=width,
                    height=height,
                    meta={"provider": self.name, "index": idx},
                )
            )

        return images

    def _build_payload(self, request: ProviderGenerationRequest) -> dict[str, Any]:
        """Build the JSON payload for the FAL generation request."""
        payload: dict[str, Any] = {
            "prompt": request.prompt,
        }

        # Preserve explicit dimensions for models that still expect `image_size`.
        if request.width is not None and request.height is not None:
            try:
                payload["image_size"] = {
                    "width": int(request.width),
                    "height": int(request.height),
                }
            except (TypeError, ValueError):
                pass

        fal_aspect_ratio = None
        fal_resolution = None
        fal_image_size = None
        if isinstance(request.params, dict):
            fal_aspect_ratio = (
                str(request.params.get("fal_aspect_ratio") or "").strip() or None
            )
            fal_resolution = (
                str(request.params.get("fal_resolution") or "").strip().upper() or None
            )
            fal_image_size = (request.params.get("fal_image_size") or "").strip() or None

        if not fal_aspect_ratio and fal_image_size:
            fal_aspect_ratio = _LEGACY_FAL_IMAGE_SIZE_TO_ASPECT_RATIO.get(fal_image_size)

        if fal_aspect_ratio:
            payload["aspect_ratio"] = fal_aspect_ratio
        if fal_resolution:
            payload["resolution"] = fal_resolution

        if request.n_images and request.n_images > 1:
            payload["num_images"] = request.n_images

        if request.seed is not None:
            payload["seed"] = request.seed

        output_format = self._normalize_output_format(request.output_format)
        if output_format:
            payload["output_format"] = output_format

        if isinstance(request.params, dict):
            for key, value in request.params.items():
                if (
                    key not in payload
                    and key not in {"fal_aspect_ratio", "fal_resolution", "fal_image_size"}
                    and value is not None
                ):
                    payload[key] = value

        return payload

    def _normalize_output_format(self, value: str | None) -> str:
        """Normalize an output-format string to one of ``jpeg``, ``png``, or ``webp``."""
        raw = (value or "jpeg").strip().lower().lstrip(".")
        if raw in {"jpg", "jpeg"}:
            return "jpeg"
        if raw in {"png", "webp"}:
            return raw
        return "jpeg"

    def _mime_from_content_type(self, content_type: str, fallback_format: str) -> str:
        """Return a MIME type string derived from the FAL content_type field or fallback format."""
        ct = (content_type or "").lower()
        if "jpeg" in ct or "jpg" in ct:
            return "image/jpeg"
        if "png" in ct:
            return "image/png"
        if "webp" in ct:
            return "image/webp"
        if fallback_format == "jpeg":
            return "image/jpeg"
        if fallback_format == "webp":
            return "image/webp"
        return "image/png"

    def _probe_dimensions(
        self, image_bytes: bytes, fallback_width: int, fallback_height: int
    ) -> tuple[int, int]:
        """Probe image bytes for dimensions, falling back to the given values on failure."""
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                width, height = image.size
                if width > 0 and height > 0:
                    return int(width), int(height)
        except (UnidentifiedImageError, OSError):
            pass
        return fallback_width, fallback_height

    def _extract_error_message(self, response: httpx.Response) -> str:
        """Extract a human-readable error message from an httpx response."""
        try:
            data = response.json()
        except Exception:
            text = response.text.strip()
            return text[:400] if text else "Unknown error"

        detail = data.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if isinstance(detail, list) and detail:
            return str(detail[0])[:400]

        error_obj = data.get("error")
        if isinstance(error_obj, dict):
            message = error_obj.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        if isinstance(error_obj, str) and error_obj.strip():
            return error_obj.strip()

        message = data.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

        return str(data)[:400]
