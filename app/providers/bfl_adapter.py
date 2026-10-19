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
    display_name = "Black Forest Labs"
    homepage_url = "https://api.bfl.ai"
    BASE_URL = "https://api.bfl.ai/v1"
    MAX_POLL_ATTEMPTS = 60
    POLL_INTERVAL = 2.0  # seconds
    _logger = logging.getLogger(__name__)
    _internal_param_keys = {
        "description",
        "resolution",
        "default_resolution",
        "aspect_ratio",
        "default_aspect_ratio",
        "bfl_aspect_ratio",
        "bfl_resolution",
        "negative_prompt",
        "system_prompt",
        "base_prompt",
        "fal_aspect_ratio",
        "fal_resolution",
        "fal_image_size",
        "openrouter_aspect_ratio",
        "openrouter_image_size",
        "google_aspect_ratio",
        "google_resolution",
        "image_config",
        "category_ids",
        "categories",
        "selected_style_ids",
        "selected_style_names",
        "upscale_provider",
        "upscale_model",
        "upscale_topaz_model_id",
        "upscaling_active",
        "chat_session_id",
        "chat_session_title",
        "conversation",
        "mode",
        "expand",
        "source_asset_id",
        "continuation_prompt",
        "width",
        "height",
        "seed",
        "input_images",
        "is_style_generation",
        "style_id",
        "overrides",
    }

    FLUX3_ALLOWED_ASPECT_RATIOS: tuple[str, ...] = (
        "21:9",
        "2:1",
        "16:9",
        "3:2",
        "7:5",
        "4:3",
        "5:4",
        "1:1",
        "4:5",
        "3:4",
        "5:7",
        "2:3",
        "9:16",
        "1:2",
        "9:21",
    )

    FLUX3_ALLOWED_RESOLUTIONS: tuple[str, ...] = (
        "768sq",
        "1k",
        "1.5k",
        "2k",
        "4k",
    )

    def _resolve_model_name(self, model: str) -> str:
        """Resolve a model identifier or alias to the expected BFL endpoint path."""
        cleaned = (model or "").strip()
        lower = cleaned.lower()
        if "/" in lower:
            lower = lower.split("/")[-1]
        if lower in {"flux-3", "flux3", "flux-3-image", "flux3-image"}:
            return "flux-3-image"
        return cleaned

    def _is_flux3_image(self, model: str) -> bool:
        """Check whether the model targets the FLUX 3 image generation endpoint."""
        return self._resolve_model_name(model) == "flux-3-image"

    async def list_models(self, settings: Settings) -> list[str]:
        """List available BFL models by querying the models endpoint."""
        api_key = settings.bfl_api_key
        if not api_key:
            raise ProviderConfigError("BFL adapter requires BFL_API_KEY in .env.")

        url = f"{self.BASE_URL}/models"
        headers = {"x-key": api_key}
        timeout = httpx.Timeout(
            settings.llm_models_timeout_seconds,
            connect=settings.llm_models_connect_timeout_seconds,
        )

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
        """Submit an image generation task to BFL and poll for results."""
        # Use api_key from request (custom) or fall back to settings
        api_key = request.api_key or settings.bfl_api_key
        if not api_key:
            raise ProviderConfigError(
                "BFL adapter requires BFL_API_KEY in .env or a custom API key."
            )

        # Submit the generation request
        model_name = self._resolve_model_name(request.model)
        submit_url = f"{self.BASE_URL}/{model_name}"
        headers = {
            "x-key": api_key,
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = self._build_payload(request)
        self._log_request("POST", submit_url, headers, payload)

        timeout = httpx.Timeout(
            settings.llm_generate_timeout_seconds,
            connect=settings.llm_generate_connect_timeout_seconds,
        )
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
                client, polling_url, request_id, request, settings
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
        settings: Settings | None = None,
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
                return self._extract_images_from_result(result, request, settings)

            elif status in {"pending", "reasoning", "generating"}:
                # Still processing, continue polling
                continue

            elif status in {
                "failed",
                "error",
                "request moderated",
                "content moderated",
                "task not found",
            }:
                error_msg = (
                    result.get("error")
                    or result.get("details")
                    or result.get("message")
                    or f"Task ended with status: {result.get('status')}"
                )
                self._logger.error(f"BFL generation failed: {error_msg}, result={result}")
                raise ProviderError(f"BFL generation failed: {error_msg}")

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
        self,
        result: dict[str, Any],
        request: ProviderGenerationRequest,
        settings: Settings | None = None,
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
                    download_timeout = (
                        settings.provider_bfl_download_timeout_seconds
                        if settings
                        else 120.0
                    )
                    connect_timeout = (
                        settings.provider_bfl_download_connect_timeout_seconds
                        if settings
                        else 10.0
                    )
                    timeout = httpx.Timeout(
                        download_timeout,
                        connect=connect_timeout,
                    )
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
        detected_format = ""
        try:
            with Image.open(BytesIO(image_bytes)) as img:
                img.verify()
                detected_format = (img.format or "").lower()
        except Exception as exc:
            raise ProviderError(f"BFL returned invalid image data: {exc}")

        # Get image dimensions
        fallback_width = request.width or 1024
        fallback_height = request.height or 1024
        width, height = self._probe_dimensions(
            image_bytes, fallback_width, fallback_height
        )

        if detected_format in {"jpeg", "jpg"}:
            mime = "image/jpeg"
        elif detected_format == "webp":
            mime = "image/webp"
        elif detected_format == "png":
            mime = "image/png"
        else:
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

    def _resolve_flux3_aspect_ratio(self, request: ProviderGenerationRequest) -> str:
        """Return a valid aspect ratio string for FLUX 3 Image."""
        if isinstance(request.params, dict):
            raw = (
                request.params.get("aspect_ratio")
                or request.params.get("bfl_aspect_ratio")
            )
            if isinstance(raw, str):
                cleaned = raw.strip().lower()
                if cleaned in self.FLUX3_ALLOWED_ASPECT_RATIOS or cleaned == "auto":
                    return cleaned

        if request.width and request.height and request.width > 0 and request.height > 0:
            target = float(request.width) / float(request.height)
            best_ratio = "1:1"
            best_diff = float("inf")
            for ratio in self.FLUX3_ALLOWED_ASPECT_RATIOS:
                w_str, h_str = ratio.split(":")
                val = float(w_str) / float(h_str)
                diff = abs(val - target)
                if diff < best_diff:
                    best_diff = diff
                    best_ratio = ratio
            return best_ratio

        if request.input_images:
            return "auto"

        return "1:1"

    def _resolve_flux3_resolution(self, request: ProviderGenerationRequest) -> str:
        """Return a valid resolution tier for FLUX 3 Image ('768sq', '1k', '1.5k', '2k', '4k')."""
        raw = ""
        if isinstance(request.params, dict):
            raw = str(
                request.params.get("resolution")
                or request.params.get("bfl_resolution")
                or ""
            ).strip().lower()

        if raw in {"768sq", "768", "768px"}:
            return "768sq"
        if raw in {"1k", "1.0k"}:
            return "1k"
        if raw in {"1.5k"}:
            return "1.5k"
        if raw in {"2k", "2.0k"}:
            return "2k"
        if raw in {"4k", "4.0k"}:
            return "4k"

        if request.width and request.height and request.width > 0 and request.height > 0:
            pixels = request.width * request.height
            if pixels >= 3500000:
                return "4k"
            if pixels >= 2500000:
                return "2k"
            if pixels >= 1800000:
                return "1.5k"
            if pixels <= 600000:
                return "768sq"

        return "1k"

    def _build_flux3_payload(self, request: ProviderGenerationRequest) -> dict[str, Any]:
        """Build request payload conforming strictly to the FLUX 3 Image schema."""
        payload: dict[str, Any] = {
            "prompt": request.prompt,
        }

        aspect_ratio = self._resolve_flux3_aspect_ratio(request)
        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio

        resolution = self._resolve_flux3_resolution(request)
        if resolution:
            payload["resolution"] = resolution

        if request.input_images:
            images = [
                base64.b64encode(img.data).decode("ascii")
                for img in request.input_images[:10]
            ]
            if images:
                payload["images"] = images
        elif isinstance(request.params, dict) and "images" in request.params:
            param_images = request.params["images"]
            if isinstance(param_images, list):
                payload["images"] = param_images[:10]
            elif isinstance(param_images, str):
                payload["images"] = [param_images]

        if isinstance(request.params, dict):
            if "safety_tolerance" in request.params:
                try:
                    st = int(request.params["safety_tolerance"])
                    if 0 <= st <= 4:
                        payload["safety_tolerance"] = st
                except (ValueError, TypeError):
                    pass

            if "grounding" in request.params:
                val = request.params["grounding"]
                if isinstance(val, bool):
                    payload["grounding"] = val
                elif isinstance(val, str):
                    payload["grounding"] = val.lower() in {"true", "1", "yes"}

            if "version" in request.params:
                ver = str(request.params["version"]).strip()
                if ver:
                    payload["version"] = ver

        return payload

    def _build_payload(self, request: ProviderGenerationRequest) -> dict[str, Any]:
        """Build request payload for BFL API."""
        if self._is_flux3_image(request.model):
            return self._build_flux3_payload(request)

        payload: dict[str, Any] = {
            "prompt": request.prompt,
        }

        # Handle BFL input images (Base64-encoded reference images)
        if request.input_images:
            for idx, img in enumerate(request.input_images):
                key = "input_image" if idx == 0 else f"input_image_{idx+1}"
                b64_value = base64.b64encode(img.data).decode("ascii")
                payload[key] = b64_value

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
                if (
                    key not in payload
                    and key not in self._internal_param_keys
                    and value is not None
                ):
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
        """Extract a readable error message from a BFL API response."""
        try:
            data = response.json()
        except Exception:
            text = response.text.strip()
            return text[:400] if text else "Unknown error"

        if isinstance(data, dict):
            # Check FastAPI validation details
            detail = data.get("detail")
            if isinstance(detail, list):
                errors = []
                for item in detail:
                    if isinstance(item, dict):
                        loc = " -> ".join(str(x) for x in item.get("loc", []))
                        msg = item.get("msg", "")
                        errors.append(f"{loc}: {msg}" if loc else msg)
                    else:
                        errors.append(str(item))
                if errors:
                    return "; ".join(errors)
            elif isinstance(detail, str) and detail.strip():
                return detail.strip()

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
