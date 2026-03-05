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
    name = "openai"
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        if not settings.openai_api_key:
            raise ProviderConfigError("OpenAI adapter requires OPENAI_API_KEY in .env.")

        url = settings.openai_base_url.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        timeout = httpx.Timeout(30.0, connect=10.0)
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

        url = settings.openai_base_url.rstrip("/") + "/images/generations"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        output_format = self._normalize_output_format(request.output_format)
        payload = self._build_payload(request, output_format)
        self._log_request("POST", url, headers, payload)

        timeout = httpx.Timeout(60.0, connect=10.0)
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
