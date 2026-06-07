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


class OpenAIAdapter(ProviderAdapter):
    """Provider adapter for the OpenAI image-generation API (DALL-E models)."""

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

        model_name = (request.model or "").strip().lower()
        is_dalle = model_name.startswith("dall-e")

        # If it's a DALL-E model and we have input images, we use OpenAI's official edits/variations endpoints
        if request.input_images and is_dalle:
            from io import BytesIO
            from PIL import Image

            # Determine if it's an edit or variation
            has_prompt = bool(request.prompt and request.prompt.strip())
            if has_prompt:
                url = settings.openai_base_url.rstrip("/") + "/images/edits"
            else:
                url = settings.openai_base_url.rstrip("/") + "/images/variations"

            headers = {
                "Authorization": f"Bearer {settings.openai_api_key}",
            }

            # OpenAI requires PNG format for edits/variations
            first_image = request.input_images[0]
            try:
                with Image.open(BytesIO(first_image.data)) as pil_img:
                    png_io = BytesIO()
                    pil_img.save(png_io, format="PNG")
                    image_bytes = png_io.getvalue()
            except Exception:
                image_bytes = first_image.data

            files = {
                "image": ("input.png", BytesIO(image_bytes), "image/png")
            }

            if len(request.input_images) > 1 and has_prompt:
                second_image = request.input_images[1]
                try:
                    with Image.open(BytesIO(second_image.data)) as pil_mask:
                        mask_io = BytesIO()
                        pil_mask.save(mask_io, format="PNG")
                        mask_bytes = mask_io.getvalue()
                except Exception:
                    mask_bytes = second_image.data
                files["mask"] = ("mask.png", BytesIO(mask_bytes), "image/png")

            # DALL-E 3 does not support edits/variations, so we must use dall-e-2
            data = {
                "model": "dall-e-2",
                "n": str(max(1, int(request.n_images))),
                "size": self._size_string(request),
                "response_format": "b64_json",
            }
            if has_prompt:
                data["prompt"] = request.prompt

            self._log_request("POST", url, headers, {"data": data, "files": list(files.keys())})

            timeout = httpx.Timeout(
                settings.provider_openai_generate_timeout_seconds,
                connect=settings.provider_openai_generate_connect_timeout_seconds,
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, files=files, data=data)

        else:
            # Standard generation endpoint (text-to-image or custom JSON image-to-image)
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
                response = await client.post(url, headers=headers, json=payload)

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
        mime = self._mime_from_format(output_format)
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

        # Keep adapter compatible with custom/proxy endpoints that accept input images
        # ONLY if we are not using official DALL-E models, to avoid 400 errors.
        if request.input_images and not is_dalle:
            is_gpt_image = model_name.startswith("gpt-image")
            input_images_payload = [
                f"data:{img.mime};base64,{base64.b64encode(img.data).decode('ascii')}"
                for img in request.input_images
            ]
            payload["input_images"] = input_images_payload

            # For generic custom endpoints, add fallback parameters for maximum compatibility
            if not is_gpt_image:
                first_image = request.input_images[0]
                b64_value = base64.b64encode(first_image.data).decode("ascii")
                data_url = f"data:{first_image.mime};base64,{b64_value}"
                payload["image"] = b64_value
                payload["image_url"] = data_url
                payload["input_image"] = b64_value
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
