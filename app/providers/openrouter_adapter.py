from __future__ import annotations

import base64
import re
from io import BytesIO
from math import gcd
from typing import Any, Optional

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


class OpenRouterAdapter(ProviderAdapter):
    name = "openrouter"

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        if not settings.openrouter_api_key:
            raise ProviderConfigError("OpenRouter adapter requires OPENROUTER_API_KEY in .env.")

        url = settings.openrouter_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "X-Title": settings.app_name,
        }
        payload = self._build_payload(request)

        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 429:
                raise ProviderRateLimitError("OpenRouter rate limit reached (429).")
            if response.status_code == 503:
                raise ProviderServiceUnavailableError("OpenRouter service unavailable (503).")
            if response.status_code >= 500:
                raise ProviderServiceUnavailableError(f"OpenRouter upstream error ({response.status_code}).")
            if response.status_code >= 400:
                message = self._extract_error_message(response)
                raise ProviderError(f"OpenRouter request failed ({response.status_code}): {message}")

            try:
                body = response.json()
            except Exception as exc:
                raise ProviderError("OpenRouter returned a non-JSON response.") from exc

            image_refs = self._extract_image_refs(body)
            if not image_refs:
                raise ProviderError("OpenRouter returned no generated image data.")

            fallback_width, fallback_height = self._resolve_dimensions(request)
            images: list[ProviderImage] = []
            for idx, image_ref in enumerate(image_refs, start=1):
                image_bytes, mime = await self._read_image_payload(client, image_ref, idx)
                width, height = self._probe_dimensions(image_bytes, fallback_width, fallback_height)
                images.append(
                    ProviderImage(
                        data=image_bytes,
                        mime=mime,
                        width=width,
                        height=height,
                        meta={"provider": self.name, "index": idx},
                    )
                )

        return ProviderGenerationResult(
            images=images,
            raw_meta={
                "provider": self.name,
                "id": body.get("id"),
                "created": body.get("created"),
                "model": body.get("model") or request.model,
                "usage": body.get("usage"),
                "count": len(images),
            },
        )

    def _build_payload(self, request: ProviderGenerationRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "modalities": ["image", "text"],
            "stream": False,
            "n": max(1, int(request.n_images)),
        }

        aspect_ratio = self._resolve_aspect_ratio(request)
        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio

        if request.seed is not None:
            payload["seed"] = int(request.seed)

        if request.negative_prompt:
            payload["negative_prompt"] = str(request.negative_prompt).strip()

        output_format = self._normalize_output_format(request.output_format)
        if output_format:
            payload["output_format"] = output_format

        if isinstance(request.params, dict):
            for key, value in request.params.items():
                if key not in payload and value is not None:
                    payload[key] = value

        return payload

    def _extract_image_refs(self, body: dict[str, Any]) -> list[str]:
        refs: list[str] = []
        choices = body.get("choices")
        if not isinstance(choices, list):
            return refs

        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if not isinstance(message, dict):
                continue

            refs.extend(self._extract_image_refs_from_message_images(message.get("images")))
            refs.extend(self._extract_image_refs_from_message_content(message.get("content")))

        return refs

    def _extract_image_refs_from_message_images(self, value: Any) -> list[str]:
        refs: list[str] = []
        if not isinstance(value, list):
            return refs

        for image_obj in value:
            ref = self._extract_single_image_ref(image_obj)
            if ref:
                refs.append(ref)
        return refs

    def _extract_image_refs_from_message_content(self, value: Any) -> list[str]:
        refs: list[str] = []
        if not isinstance(value, list):
            return refs

        for part in value:
            if not isinstance(part, dict):
                continue
            if part.get("type") != "image_url":
                continue
            ref = self._extract_single_image_ref(part)
            if ref:
                refs.append(ref)
        return refs

    def _extract_single_image_ref(self, image_obj: Any) -> Optional[str]:
        if not isinstance(image_obj, dict):
            return None

        nested = image_obj.get("image_url")
        if isinstance(nested, dict):
            value = nested.get("url") or nested.get("uri")
            if isinstance(value, str) and value.strip():
                return value.strip()

        if isinstance(nested, str) and nested.strip():
            return nested.strip()

        direct = image_obj.get("url") or image_obj.get("uri")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()

        return None

    async def _read_image_payload(
        self,
        client: httpx.AsyncClient,
        image_ref: str,
        idx: int,
    ) -> tuple[bytes, str]:
        if image_ref.startswith("data:"):
            return self._decode_data_url(image_ref, idx)

        if image_ref.startswith("http://") or image_ref.startswith("https://"):
            response = await client.get(image_ref)
            if response.status_code >= 400:
                raise ProviderError(
                    f"OpenRouter image URL fetch failed at index {idx} with status {response.status_code}."
                )
            content_type = str(response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
            mime = content_type or self._mime_from_output_format("png")
            if not response.content:
                raise ProviderError(f"OpenRouter image URL payload was empty at index {idx}.")
            return response.content, mime

        raise ProviderError(f"OpenRouter image reference at index {idx} had unsupported format.")

    def _decode_data_url(self, image_ref: str, idx: int) -> tuple[bytes, str]:
        match = re.match(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", image_ref, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            raise ProviderError(f"OpenRouter image payload at index {idx} was not a valid base64 data URL.")

        mime = match.group("mime").strip().lower() or self._mime_from_output_format("png")
        data = match.group("data").strip()

        try:
            image_bytes = base64.b64decode(data)
        except Exception as exc:
            raise ProviderError(f"Failed to decode OpenRouter image payload at index {idx}.") from exc

        if not image_bytes:
            raise ProviderError(f"Decoded OpenRouter image payload was empty at index {idx}.")

        return image_bytes, mime

    def _resolve_aspect_ratio(self, request: ProviderGenerationRequest) -> Optional[str]:
        if request.aspect_ratio:
            ratio = str(request.aspect_ratio).strip()
            if self._is_ratio(ratio):
                return ratio

        if request.width and request.height:
            width = int(request.width)
            height = int(request.height)
            if width > 0 and height > 0:
                divisor = gcd(width, height)
                return f"{width // divisor}:{height // divisor}"

        return None

    def _resolve_dimensions(self, request: ProviderGenerationRequest) -> tuple[int, int]:
        if request.width and request.height:
            width = int(request.width)
            height = int(request.height)
            if width > 0 and height > 0:
                return width, height

        ratio = self._resolve_aspect_ratio(request)
        if ratio and ":" in ratio:
            left_raw, right_raw = ratio.split(":", 1)
            try:
                left = int(left_raw)
                right = int(right_raw)
            except ValueError:
                return 1024, 1024
            if left > 0 and right > 0:
                if left >= right:
                    return 1024, max(1, round(1024 * right / left))
                return max(1, round(1024 * left / right)), 1024

        return 1024, 1024

    def _probe_dimensions(self, image_bytes: bytes, fallback_width: int, fallback_height: int) -> tuple[int, int]:
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                width, height = image.size
                if width > 0 and height > 0:
                    return int(width), int(height)
        except (UnidentifiedImageError, OSError):
            pass
        return fallback_width, fallback_height

    def _normalize_output_format(self, value: Optional[str]) -> str:
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

    def _is_ratio(self, value: str) -> bool:
        parts = value.split(":")
        if len(parts) != 2:
            return False
        left, right = parts
        if not left.isdigit() or not right.isdigit():
            return False
        return int(left) > 0 and int(right) > 0

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
