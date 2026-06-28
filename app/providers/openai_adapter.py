from __future__ import annotations

import base64
import logging
from io import BytesIO
from typing import Any

import httpx
from PIL import Image

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


class OpenAIAdapter(ProviderAdapter):
    """Provider adapter for the OpenAI image-generation API (DALL-E and gpt-image-* models)."""

    name = "openai"
    display_name = "OpenAI"
    homepage_url = "https://platform.openai.com/api-keys"
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        if not settings.openai_api_key:
            raise ProviderConfigError("OpenAI adapter requires OPENAI_API_KEY in .env.")

        url = settings.openai_base_url.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        timeout = httpx.Timeout(
            settings.llm_models_timeout_seconds,
            connect=settings.llm_models_connect_timeout_seconds,
        )
        self._log_request("GET", url, headers)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)

        if response.status_code >= 400:
            message = self._extract_error_message(response)
            raise ProviderError(f"OpenAI models request failed ({response.status_code}): {message}")

        try:
            body = response.json()
        except Exception as exc:
            raise ProviderError("OpenAI returned a non-JSON models response.") from exc

        model_ids: list[str] = []
        for item in body.get("data") or []:
            if isinstance(item, dict):
                model_id = item.get("id")
                if isinstance(model_id, str) and model_id.strip():
                    model_ids.append(model_id.strip())

        image_like = [item for item in model_ids if "image" in item or item.startswith("dall-e")]
        return image_like or model_ids

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        if not settings.openai_api_key:
            raise ProviderConfigError("OpenAI adapter requires OPENAI_API_KEY in .env.")

        if request.input_images:
            response = await self._generate_with_input_images(request, settings)
        else:
            response = await self._generate_text_only(request, settings)

        if response.status_code == 429:
            raise ProviderRateLimitError("OpenAI rate limit reached (429).")
        if response.status_code == 503:
            raise ProviderServiceUnavailableError("OpenAI service unavailable (503).")
        if response.status_code >= 500:
            raise ProviderServiceUnavailableError(f"OpenAI upstream error ({response.status_code}).")
        if response.status_code >= 400:
            message = self._extract_error_message(response)
            raise ProviderError(f"OpenAI request failed ({response.status_code}): {message}")

        body = response.json()
        data_list = body.get("data") or []
        if not data_list:
            raise ProviderError("OpenAI returned no image data.")

        width, height = self._resolve_dimensions(request)
        mime = self._mime_from_format(self._normalize_output_format(request.output_format))
        images: list[ProviderImage] = []
        for idx, item in enumerate(data_list, start=1):
            b64_value = item.get("b64_json")
            if not b64_value:
                raise ProviderError("OpenAI response did not contain b64_json image data.")
            try:
                image_bytes = base64.b64decode(b64_value)
            except Exception as exc:
                raise ProviderError(f"Failed to decode OpenAI image payload at index {idx}.") from exc

            images.append(
                ProviderImage(
                    data=image_bytes,
                    mime=mime,
                    width=width,
                    height=height,
                    meta={"provider": self.name, "index": idx, "revised_prompt": item.get("revised_prompt")},
                )
            )

        return ProviderGenerationResult(
            images=images,
            raw_meta={
                "provider": self.name,
                "created": body.get("created"),
                "model": request.model,
                "count": len(images),
            },
        )

    def _build_payload(self, request: ProviderGenerationRequest, output_format: str) -> dict[str, Any]:
        model_name = (request.model or "").strip().lower()
        is_dalle = model_name.startswith("dall-e")
        payload: dict[str, Any] = {
            "model": request.model,
            "prompt": request.prompt,
            "n": max(1, int(request.n_images)),
            "size": self._size_string(request),
        }
        if is_dalle:
            payload["response_format"] = "b64_json"
        else:
            payload["output_format"] = output_format

        # Keep adapter forward-compatible with extra provider-specific knobs.
        if isinstance(request.params, dict):
            for key, value in request.params.items():
                if key not in payload and value is not None:
                    payload[key] = value

        return payload

    async def _generate_text_only(
        self, request: ProviderGenerationRequest, settings: Settings
    ) -> httpx.Response:
        """Send a text-to-image request to the OpenAI generations endpoint."""
        url = settings.openai_base_url.rstrip("/") + "/images/generations"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        output_format = self._normalize_output_format(request.output_format)
        payload = self._build_payload(request, output_format)
        self._log_request("POST", url, headers, payload)

        timeout = httpx.Timeout(
            settings.provider_openai_generate_timeout_seconds,
            connect=settings.provider_openai_generate_connect_timeout_seconds,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, headers=headers, json=payload)

    async def _generate_with_input_images(
        self, request: ProviderGenerationRequest, settings: Settings
    ) -> httpx.Response:
        """Send an image-edit/variation request to the OpenAI API.

        OpenAI's ``/v1/images/generations`` endpoint does not accept input images,
        so any request that carries ``input_images`` must be routed through
        ``/v1/images/edits`` (or ``/v1/images/variations`` for DALL-E 2 without a
        prompt). This applies to both DALL-E 2 and the ``gpt-image-*`` family;
        DALL-E 3 does not support input images at all and is rejected explicitly.
        """
        model_name = (request.model or "").strip().lower()
        has_prompt = bool(request.prompt and request.prompt.strip())

        if model_name.startswith("dall-e-3"):
            raise ProviderError(
                "DALL-E 3 does not support input images. Use a DALL-E 2 or gpt-image-* model for image-to-image."
            )

        is_dalle2 = model_name.startswith("dall-e-2")
        if is_dalle2 and not has_prompt:
            url = settings.openai_base_url.rstrip("/") + "/images/variations"
        else:
            url = settings.openai_base_url.rstrip("/") + "/images/edits"

        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
        }

        is_gpt_image = model_name.startswith("gpt-image")
        first_image_bytes = self._ensure_png(request.input_images[0].data)
        reference_field = "image[]" if is_gpt_image else "image"
        files: list[tuple[str, tuple[str, BytesIO, str]]] = [
            (reference_field, ("input.png", BytesIO(first_image_bytes), "image/png"))
        ]

        if len(request.input_images) > 1 and has_prompt:
            mask_bytes = self._ensure_png(request.input_images[1].data)
            files.append(("mask", ("mask.png", BytesIO(mask_bytes), "image/png")))

        data: dict[str, str] = {
            "model": request.model,
            "n": str(max(1, int(request.n_images))),
            "size": self._size_string(request),
        }
        if is_dalle2:
            data["response_format"] = "b64_json"
        else:
            data["output_format"] = self._normalize_output_format(request.output_format)
        if has_prompt:
            data["prompt"] = request.prompt

        if isinstance(request.params, dict):
            for key, value in request.params.items():
                if key in data or value is None:
                    continue
                data[key] = str(value)

        self._log_request("POST", url, headers, {"data": data, "files": [name for name, _ in files]})

        timeout = httpx.Timeout(
            settings.provider_openai_generate_timeout_seconds,
            connect=settings.provider_openai_generate_connect_timeout_seconds,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, headers=headers, files=files, data=data)

    @staticmethod
    def _ensure_png(image_bytes: bytes) -> bytes:
        """Return *image_bytes* re-encoded as PNG, falling back to the input on failure."""
        try:
            with Image.open(BytesIO(image_bytes)) as pil_img:
                buffer = BytesIO()
                pil_img.save(buffer, format="PNG")
                return buffer.getvalue()
        except Exception:
            return image_bytes

    def _size_string(self, request: ProviderGenerationRequest) -> str:
        if request.width and request.height:
            return f"{int(request.width)}x{int(request.height)}"
        return "1024x1024"

    def _resolve_dimensions(self, request: ProviderGenerationRequest) -> tuple[int, int]:
        if request.width and request.height:
            return int(request.width), int(request.height)
        size = self._size_string(request)
        if "x" not in size:
            return 1024, 1024
        left, right = size.split("x", 1)
        try:
            return int(left), int(right)
        except ValueError:
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

        error_obj = data.get("error")
        if isinstance(error_obj, dict):
            message = error_obj.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        text = str(data)
        return text[:400]
