"""FAL.ai Topaz upscaling service.

Uses the fal-ai/topaz/upscale/image endpoint via the FAL queue API.
"""
from __future__ import annotations

import asyncio
import base64
import logging
from io import BytesIO
from urllib.parse import urlparse

import httpx
from PIL import Image, UnidentifiedImageError

_logger = logging.getLogger(__name__)


class FalUpscaleError(Exception):
    """Raised when the FAL.ai upscale request fails."""


class FalUpscaleService:
    """Async upscaling service backed by the FAL.ai Topaz upscale API."""

    QUEUE_URL = "https://queue.fal.run"
    DEFAULT_MODEL_IDENTIFIER = "fal-ai/topaz/upscale/image"
    MAX_POLL_ATTEMPTS = 90
    POLL_INTERVAL = 2.0

    def is_available(self, api_key: str | None) -> bool:
        """Return ``True`` if a FAL.ai API key is configured."""
        return bool((api_key or "").strip())

    async def upscale_bytes(
        self,
        data: bytes,
        output_format: str,
        api_key: str,
        *,
        model_identifier: str | None = None,
        model_params: dict | None = None,
    ) -> tuple[bytes, int, int, str]:
        """Upscale *data* via FAL.ai Topaz and return ``(image_bytes, width, height, mime)``.

        Submits the image to the FAL queue, polls for completion, fetches the result,
        and returns the upscaled image bytes along with dimensions and MIME type.
        """
        if not api_key:
            raise FalUpscaleError("FAL_API_KEY is not configured")

        fmt = self._normalize_format(output_format)
        mime = self._format_to_mime(fmt)

        # Encode image as data URL for FAL API
        image_data_url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

        headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {"image_url": image_data_url}
        for key, value in (model_params or {}).items():
            if key != "image_url":
                payload[key] = value

        submit_url = self._build_submit_url(model_identifier)

        timeout = httpx.Timeout(60.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Submit the request
            response = await client.post(submit_url, headers=headers, json=payload)

            if response.status_code == 401:
                raise FalUpscaleError("FAL.ai API key is invalid or unauthorized.")
            if response.status_code == 429:
                raise FalUpscaleError("FAL.ai rate limit reached.")
            if response.status_code >= 500:
                raise FalUpscaleError(
                    f"FAL.ai upstream error ({response.status_code})."
                )
            if response.status_code >= 400:
                msg = self._extract_error_message(response)
                raise FalUpscaleError(
                    f"FAL.ai upscale request failed ({response.status_code}): {msg}"
                )

            try:
                submit_result = response.json()
            except Exception as exc:
                raise FalUpscaleError("FAL.ai returned a non-JSON response.") from exc

            request_id = submit_result.get("request_id")
            if not request_id:
                raise FalUpscaleError(
                    f"FAL.ai did not return a request_id. Response: {submit_result}"
                )

            _logger.debug("FAL.ai upscale submitted, request_id=%s", request_id)

            # Poll for completion
            model_path = self._resolve_model_path(model_identifier, submit_url)
            status_url, response_url = self._extract_queue_urls(
                submit_result=submit_result,
                request_id=request_id,
                model_path=model_path,
            )
            result = await self._poll_for_result(
                client,
                headers,
                status_url,
                response_url,
            )

        # Download and return the upscaled image
        images = self._extract_result_images(result)
        if not images:
            raise FalUpscaleError(
                f"FAL.ai upscale returned no images in the result. Keys: {sorted(result.keys())}"
            )

        image_info = images[0]
        image_url = image_info.get("url") or ""
        if not image_url:
            raise FalUpscaleError("FAL.ai upscale result has no image URL.")

        timeout_dl = httpx.Timeout(120.0, connect=30.0)
        async with httpx.AsyncClient(timeout=timeout_dl) as client:
            dl_response = await client.get(image_url)
            if dl_response.status_code >= 400:
                raise FalUpscaleError(
                    f"Failed to download FAL.ai upscaled image ({dl_response.status_code})."
                )
            image_bytes = dl_response.content

        width, height = self._probe_dimensions(image_bytes)
        result_mime = image_info.get("content_type") or image_info.get("mime_type") or mime
        return image_bytes, width, height, result_mime

    async def _poll_for_result(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        status_url: str,
        response_url: str,
    ) -> dict:
        """Poll FAL.ai until the request is complete and return the result payload."""
        for attempt in range(self.MAX_POLL_ATTEMPTS):
            await asyncio.sleep(self.POLL_INTERVAL)

            status_response = await client.get(status_url, headers=headers)

            # Some endpoints may not expose a GET /status route. Fall back to response_url polling.
            if status_response.status_code == 405:
                result_response = await client.get(response_url, headers=headers)
                if result_response.status_code == 200:
                    try:
                        return result_response.json()
                    except Exception as exc:
                        raise FalUpscaleError(
                            "FAL.ai result returned non-JSON."
                        ) from exc
                if result_response.status_code in {202, 204, 425, 429}:
                    continue
                if result_response.status_code >= 500:
                    if attempt < self.MAX_POLL_ATTEMPTS - 1:
                        continue
                    raise FalUpscaleError(
                        f"FAL.ai result polling failed ({result_response.status_code})."
                    )
                msg = self._extract_error_message(result_response)
                raise FalUpscaleError(
                    f"FAL.ai result polling failed ({result_response.status_code}): {msg}"
                )

            if status_response.status_code >= 500:
                if attempt < self.MAX_POLL_ATTEMPTS - 1:
                    continue
                raise FalUpscaleError(
                    f"FAL.ai status polling failed ({status_response.status_code})."
                )
            if status_response.status_code >= 400:
                msg = self._extract_error_message(status_response)
                raise FalUpscaleError(
                    f"FAL.ai status polling failed ({status_response.status_code}): {msg}"
                )

            try:
                status_data = status_response.json()
            except Exception as exc:
                raise FalUpscaleError("FAL.ai status polling returned non-JSON.") from exc

            status = (status_data.get("status") or "").upper()
            _logger.debug("FAL.ai upscale status: %s (attempt %d)", status, attempt + 1)

            if status == "COMPLETED":
                result_response = await client.get(response_url, headers=headers)
                if result_response.status_code >= 400:
                    msg = self._extract_error_message(result_response)
                    raise FalUpscaleError(
                        f"FAL.ai result fetch failed ({result_response.status_code}): {msg}"
                    )
                try:
                    return result_response.json()
                except Exception as exc:
                    raise FalUpscaleError(
                        "FAL.ai result returned non-JSON."
                    ) from exc

            if status in {"FAILED", "CANCELLED"}:
                error_msg = status_data.get("error") or "Unknown error"
                raise FalUpscaleError(f"FAL.ai upscale failed: {error_msg}")

            # IN_QUEUE or IN_PROGRESS: keep polling

        raise FalUpscaleError(
            f"FAL.ai upscale timed out after {self.MAX_POLL_ATTEMPTS} polling attempts."
        )

    def _probe_dimensions(self, image_bytes: bytes) -> tuple[int, int]:
        """Return image dimensions from *image_bytes*, or (0, 0) on failure."""
        try:
            with Image.open(BytesIO(image_bytes)) as img:
                return img.width, img.height
        except (UnidentifiedImageError, OSError):
            return 0, 0

    def _normalize_format(self, output_format: str) -> str:
        fmt = (output_format or "png").lower().lstrip(".")
        if fmt == "jpeg":
            fmt = "jpg"
        if fmt not in {"png", "jpg", "webp"}:
            return "png"
        return fmt

    def _format_to_mime(self, fmt: str) -> str:
        if fmt == "jpg":
            return "image/jpeg"
        return f"image/{fmt}"

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except Exception:
            text = response.text.strip()
            return text[:400] if text else "Unknown error"
        detail = data.get("detail") or data.get("message") or data.get("error")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()[:400]
        return str(data)[:400]

    def _extract_result_images(self, result: dict) -> list[dict]:
        """Return a normalized list of image objects from possible FAL result shapes."""
        candidates: list[dict] = [result]
        data_payload = result.get("data")
        if isinstance(data_payload, dict):
            candidates.append(data_payload)
        output_payload = result.get("output")
        if isinstance(output_payload, dict):
            candidates.append(output_payload)

        for payload in candidates:
            images = payload.get("images")
            if isinstance(images, list):
                normalized = [item for item in images if isinstance(item, dict)]
                if normalized:
                    return normalized

            image = payload.get("image")
            if isinstance(image, dict):
                return [image]

            image_url = payload.get("image_url")
            if isinstance(image_url, str) and image_url.strip():
                return [
                    {
                        "url": image_url.strip(),
                        "content_type": payload.get("content_type"),
                    }
                ]

        return []

    def _extract_queue_urls(
        self,
        *,
        submit_result: dict,
        request_id: str,
        model_path: str,
    ) -> tuple[str, str]:
        """Return normalized status/response URLs from submit response with safe fallback."""
        raw_status_url = str(submit_result.get("status_url") or "").strip()
        raw_response_url = str(
            submit_result.get("response_url")
            or submit_result.get("result_url")
            or ""
        ).strip()

        status_url = raw_status_url or f"{self.QUEUE_URL}/{model_path}/requests/{request_id}/status"
        response_url = raw_response_url or f"{self.QUEUE_URL}/{model_path}/requests/{request_id}"
        return status_url, response_url

    def _build_submit_url(self, model_identifier: str | None) -> str:
        """Return the queue submit URL for the configured FAL model identifier."""
        identifier = (model_identifier or self.DEFAULT_MODEL_IDENTIFIER).strip()
        if not identifier:
            identifier = self.DEFAULT_MODEL_IDENTIFIER
        if identifier.startswith("https://") or identifier.startswith("http://"):
            return identifier
        return f"{self.QUEUE_URL}/{identifier.lstrip('/')}"

    def _resolve_model_path(self, model_identifier: str | None, submit_url: str) -> str:
        """Resolve queue model path used for polling/result endpoints."""
        identifier = (model_identifier or "").strip()
        if identifier and not (identifier.startswith("https://") or identifier.startswith("http://")):
            return identifier.lstrip("/")

        parsed = urlparse(identifier) if identifier else None
        if parsed and parsed.netloc.lower().endswith("queue.fal.run") and parsed.path.strip("/"):
            return parsed.path.strip("/")

        submit_parsed = urlparse(submit_url)
        if submit_parsed.netloc.lower().endswith("queue.fal.run") and submit_parsed.path.strip("/"):
            return submit_parsed.path.strip("/")

        return self.DEFAULT_MODEL_IDENTIFIER
