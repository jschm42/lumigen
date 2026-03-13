from __future__ import annotations

import asyncio
import base64
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


class BFLAdapter(ProviderAdapter):
    """Provider adapter for the Black Forest Labs (BFL) image-generation API."""
    name = "bfl"
    BASE_URL = "https://api.bfl.ai/v1"
    MAX_POLL_ATTEMPTS = 60
    POLL_INTERVAL = 2.0  # seconds
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        api_key = settings.bfl_api_key
        if not api_key:
            raise ProviderConfigError("BFL adapter requires BFL_API_KEY in .env.")

        url = f"{self.BASE_URL}/models"
        headers = {"x-key": api_key}
        timeout = httpx.Timeout(30.0, connect=10.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)

        if response.status_code >= 400:
            message = self._extract_error_message(response)
            raise ProviderError(
                f"BFL models request failed ({response.status_code}): {message}"
            )

        try:
            body = response.json()
        except Exception as exc:
            raise ProviderError(
                "BFL returned a non-JSON models response."
            ) from exc

        models: list[str] = []
        data = body.get("data") or body.get("models") or []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    model_id = item.get("id") or item.get("name")
                    if isinstance(model_id, str) and model_id.strip():
                        models.append(model_id.strip())
        return models

    async def generate(
        self, request: ProviderGenerationRequest, settings: Settings
    ) -> ProviderGenerationResult:
        # Use api_key from request (custom) or fall back to settings
        api_key = request.api_key or settings.bfl_api_key
        if not api_key:
            raise ProviderConfigError(
                "BFL adapter requires BFL_API_KEY in .env or a custom API key."
            )

        # Submit the generation request
        submit_url = f"{self.BASE_URL}/{request.model}"
        headers = {
            "x-key": api_key,
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = self._build_payload(request)
        self._log_request("POST", submit_url, headers, payload)

        timeout = httpx.Timeout(60.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(submit_url, headers=headers, json=payload)

            if response.status_code == 429:
                raise ProviderRateLimitError("BFL rate limit reached (429).")
            if response.status_code == 503:
                raise ProviderServiceUnavailableError(
                    "BFL service unavailable (503)."
                )
            if response.status_code >= 500:
                raise ProviderServiceUnavailableError(
                    f"BFL upstream error ({response.status_code})."
                )
            if response.status_code >= 400:
                message = self._extract_error_message(response)
                raise ProviderError(
                    f"BFL request failed ({response.status_code}): {message}"
                )

            try:
                submit_result = response.json()
            except Exception as exc:
                raise ProviderError("BFL returned a non-JSON response.") from exc

            # Get the request ID and polling URL
            request_id = submit_result.get("id")
            polling_url = submit_result.get("polling_url")

            if not request_id:
                raise ProviderError(
                    f"BFL did not return a request ID. Response: {submit_result}"
                )

            # Poll for the result
            images = await self._poll_for_result(
                client, polling_url, request_id, request
            )

        return ProviderGenerationResult(
            images=images,
            raw_meta={
                "provider": self.name,
                "id": request_id,
                "model": request.model,
                "count": len(images),
            },
        )

    async def _poll_for_result(
        self,
        client: httpx.AsyncClient,
        polling_url: str,
        request_id: str,
        request: ProviderGenerationRequest,
    ) -> list[ProviderImage]:
        """Poll the BFL API for the generation result."""
        headers = {"accept": "application/json"}

        for attempt in range(self.MAX_POLL_ATTEMPTS):
            await asyncio.sleep(self.POLL_INTERVAL)

            response = await client.get(polling_url, headers=headers)

            if response.status_code >= 500:
                if attempt < self.MAX_POLL_ATTEMPTS - 1:
                    continue
                raise ProviderServiceUnavailableError(
                    f"BFL polling failed ({response.status_code})."
                )

            if response.status_code >= 400:
                message = self._extract_error_message(response)
                raise ProviderError(
                    f"BFL polling failed ({response.status_code}): {message}"
                )

            try:
                result = response.json()
            except Exception as exc:
                raise ProviderError("BFL polling returned non-JSON.") from exc

            status = result.get("status", "").lower()

            if status == "ready":
                # Extract the image
                return self._extract_images_from_result(result, request)

            elif status == "failed":
                error_msg = result.get("error", "Unknown error")
                self._logger.error(f"BFL generation failed: {error_msg}, result={result}")
                raise ProviderError(f"BFL generation failed: {error_msg}")

            elif status == "pending":
                # Still processing, continue polling
                continue

            else:
                # Unknown status, continue polling
                if attempt < self.MAX_POLL_ATTEMPTS - 1:
                    continue
                raise ProviderError(
                    f"BFL polling timed out after {self.MAX_POLL_ATTEMPTS} attempts. "
                    f"Last status: {status}"
                )

        raise ProviderError(
            f"BFL polling timed out after {self.MAX_POLL_ATTEMPTS} attempts."
        )

    def _extract_images_from_result(
        self, result: dict[str, Any], request: ProviderGenerationRequest
    ) -> list[ProviderImage]:
        """Extract images from the BFL result."""
        images: list[ProviderImage] = []

        # BFL returns the result in 'result' -> 'sample'
        result_data = result.get("result", {})
        sample = result_data.get("sample")

        if not sample:
            # Try alternative path
            sample = result.get("sample")

        if not sample:
            raise ProviderError("BFL result does not contain 'sample' image.")

        # Debug: Write to file for troubleshooting
        debug_info = {
            "sample_type": type(sample).__name__,
            "sample_length": len(sample) if isinstance(sample, str) else "N/A",
            "sample_first_50": repr(sample[:50]) if isinstance(sample, str) else str(sample),
            "result_keys": list(result.keys()),
        }
        self._write_debug_log("bfl_sample", debug_info)

        # Log sample info at INFO level for debugging
        self._logger.info(
            f"BFL sample: type={type(sample).__name__}, "
            f"length={len(sample) if isinstance(sample, str) else 'N/A'}, "
            f"first_50={repr(sample[:50]) if isinstance(sample, str) else sample}"
        )

        # Debug log the raw response
        self._logger.debug(
            f"BFL full result keys: {result.keys()}"
        )

        # sample can be a base64 string or URL
        if isinstance(sample, str):
            # Check if it's a URL (HTTPS or HTTP)
            if sample.startswith("http://") or sample.startswith("https://"):
                # It's a URL - fetch the image
                try:
                    timeout = httpx.Timeout(60.0, connect=30.0)
                    with httpx.Client(timeout=timeout) as client:
                        response = client.get(sample)
                        response.raise_for_status()
                        image_bytes = response.content
                except Exception as exc:
                    raise ProviderError(
                        f"Failed to fetch BFL image from URL: {exc}"
                    ) from exc
            else:
                # It's base64 - decode it
                try:
                    image_bytes = base64.b64decode(sample)
                except Exception as exc:
                    raise ProviderError(
                        f"Failed to decode BFL image: {exc}"
                    ) from exc
        else:
            raise ProviderError(
                f"BFL sample is not a string: {type(sample)}"
            )

        # Debug log decoded bytes
        self._logger.debug(
            f"BFL decoded: length={len(image_bytes)}, "
            f"first_bytes={image_bytes[:20].hex()}, "
            f"is_ascii_printable={all(32 <= b < 127 for b in image_bytes[:100])}"
        )

        # Validate image data is actually valid
        try:
            with Image.open(BytesIO(image_bytes)) as img:
                img.verify()
        except Exception as exc:
            raise ProviderError(f"BFL returned invalid image data: {exc}")

        # Get image dimensions
        fallback_width = request.width or 1024
        fallback_height = request.height or 1024
        width, height = self._probe_dimensions(
            image_bytes, fallback_width, fallback_height
        )

        mime = self._mime_from_output_format(
            self._normalize_output_format(request.output_format)
        )

        images.append(
            ProviderImage(
                data=image_bytes,
                mime=mime,
                width=width,
                height=height,
                meta={"provider": self.name, "index": 1},
            )
        )

        return images

    def _build_payload(self, request: ProviderGenerationRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "prompt": request.prompt,
        }

        # Handle image dimensions
        if request.width and request.height:
            payload["width"] = request.width
            payload["height"] = request.height

        # Number of images
        if request.n_images and request.n_images > 1:
            payload["num_images"] = request.n_images

        # Seed
        if request.seed is not None:
            payload["seed"] = request.seed

        # Output format
        output_format = self._normalize_output_format(request.output_format)
        if output_format and output_format != "png":
            payload["output_format"] = output_format

        # Additional params
        if isinstance(request.params, dict):
            for key, value in request.params.items():
                if key not in payload and value is not None:
                    payload[key] = value

        return payload

    def _normalize_output_format(self, value: str | None) -> str:
        raw = (value or "png").strip().lower().lstrip(".")
        if raw in {"jpg", "jpeg"}:
            return "jpeg"
        if raw in {"png", "webp"}:
            return raw
        return "png"

    def _mime_from_output_format(self, output_format: str) -> str:
        if output_format == "jpeg":
            return "image/jpeg"
        if output_format == "webp":
            return "image/webp"
        return "image/png"

    def _probe_dimensions(
        self, image_bytes: bytes, fallback_width: int, fallback_height: int
    ) -> tuple[int, int]:
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                width, height = image.size
                if width > 0 and height > 0:
                    return int(width), int(height)
        except (UnidentifiedImageError, OSError):
            pass
        return fallback_width, fallback_height

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except Exception:
            text = response.text.strip()
            return text[:400] if text else "Unknown error"

        error_obj = data.get("error")
        if isinstance(error_obj, dict):
            message = error_obj.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()

        message = data.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

        text = str(data)
        return text[:400]

    def _write_debug_log(self, prefix: str, data: Any) -> None:
        """Write debug info to a file for troubleshooting."""
        import json
        from pathlib import Path

        debug_dir = Path("data/debug")
        debug_dir.mkdir(exist_ok=True, parents=True)

        # Find next sequence number
        existing = list(debug_dir.glob(f"{prefix}_*.json"))
        seq = len(existing) + 1

        filepath = debug_dir / f"{prefix}_{seq:04d}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
