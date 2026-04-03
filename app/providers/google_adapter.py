from __future__ import annotations

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


class GoogleAdapter(ProviderAdapter):
    """Provider adapter for the Google Gemini image-generation API."""
    name = "google"
    display_name = "Google AI"
    homepage_url = "https://aistudio.google.com/app/apikey"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        if not settings.google_api_key:
            raise ProviderConfigError("Google adapter requires GOOGLE_API_KEY in .env.")

        url = f"{self._base_url(settings)}/models"
        headers = {"Content-Type": "application/json"}
        params = {"key": settings.google_api_key}
        timeout = httpx.Timeout(30.0, connect=10.0)
        self._log_request("GET", url, headers)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers, params=params)

        if response.status_code >= 400:
            message = self._extract_error_message(response)
            raise ProviderError(f"Google models request failed ({response.status_code}): {message}")

        try:
            body = response.json()
        except Exception as exc:
            raise ProviderError("Google returned a non-JSON models response.") from exc

        models: list[str] = []
        for item in body.get("models") or []:
            if not isinstance(item, dict):
                continue
            model_name = item.get("name")
            if not isinstance(model_name, str) or not model_name.strip():
                continue
            methods = item.get("supportedGenerationMethods") or []
            method_values = {str(value).strip() for value in methods if str(value).strip()}
            if "generateContent" not in method_values and "predict" not in method_values:
                continue
            models.append(self._normalize_model_name(model_name))

        return models or [
            "gemini-2.0-flash-preview-image-generation",
            "imagen-3.0-generate-002",
        ]

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        if not settings.google_api_key:
            raise ProviderConfigError("Google adapter requires GOOGLE_API_KEY in .env.")

        model_name = self._normalize_model_name(request.model)
        use_predict = "imagen" in model_name.lower()
        action = "predict" if use_predict else "generateContent"
        url = f"{self._base_url(settings)}/models/{model_name}:{action}"
        headers = {"Content-Type": "application/json"}
        params = {"key": settings.google_api_key}
        payload = self._build_payload(request, use_predict=use_predict)
        self._log_request("POST", url, headers, payload)

        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, params=params, json=payload)

        if response.status_code == 429:
            raise ProviderRateLimitError("Google rate limit reached (429).")
        if response.status_code == 503:
            raise ProviderServiceUnavailableError("Google service unavailable (503).")
        if response.status_code >= 500:
            raise ProviderServiceUnavailableError(f"Google upstream error ({response.status_code}).")
        if response.status_code >= 400:
            message = self._extract_error_message(response)
            raise ProviderError(f"Google request failed ({response.status_code}): {message}")

        try:
            body = response.json()
        except Exception as exc:
            raise ProviderError("Google returned a non-JSON generation response.") from exc

        images = self._extract_images(body, request)

        return ProviderGenerationResult(
            images=images,
            raw_meta={
                "provider": self.name,
                "model": model_name,
                "count": len(images),
                "response_id": body.get("responseId"),
            },
        )

    def _base_url(self, settings: Settings) -> str:
        return settings.google_base_url.rstrip("/") if settings.google_base_url else self.BASE_URL

    def _normalize_model_name(self, value: str) -> str:
        raw = (value or "").strip()
        if raw.startswith("models/"):
            return raw.split("/", 1)[1]
        return raw

    def _build_payload(self, request: ProviderGenerationRequest, use_predict: bool) -> dict[str, Any]:
        if use_predict:
            return self._build_predict_payload(request)
        return self._build_generate_content_payload(request)

    def _build_generate_content_payload(self, request: ProviderGenerationRequest) -> dict[str, Any]:
        parts: list[dict[str, Any]] = [{"text": request.prompt}]
        for input_image in request.input_images:
            if not input_image.data or not input_image.mime:
                continue
            parts.append(
                {
                    "inlineData": {
                        "mimeType": input_image.mime,
                        "data": base64.b64encode(input_image.data).decode("ascii"),
                    }
                }
            )

        generation_config: dict[str, Any] = {
            "responseModalities": ["TEXT", "IMAGE"],
            "candidateCount": max(1, int(request.n_images)),
        }
        if request.seed is not None:
            generation_config["seed"] = int(request.seed)

        if isinstance(request.params, dict):
            image_config = self._normalize_image_config(request.params.get("image_config"))
            if image_config:
                generation_config["imageConfig"] = image_config

        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation_config,
        }

        if isinstance(request.params, dict):
            for key, value in request.params.items():
                if key != "image_config" and key not in payload and value is not None:
                    payload[key] = value

        return payload

    def _build_predict_payload(self, request: ProviderGenerationRequest) -> dict[str, Any]:
        output_format = self._normalize_output_format(request.output_format)
        parameters: dict[str, Any] = {
            "sampleCount": max(1, int(request.n_images)),
            "outputOptions": {"mimeType": self._mime_from_format(output_format)},
        }
        if request.seed is not None:
            parameters["seed"] = int(request.seed)

        if isinstance(request.params, dict):
            image_config = self._normalize_image_config(request.params.get("image_config"))
            if image_config:
                parameters["imageConfig"] = image_config

        if isinstance(request.params, dict):
            for key, value in request.params.items():
                if key != "image_config" and key not in parameters and value is not None:
                    parameters[key] = value

        return {
            "instances": [{"prompt": request.prompt}],
            "parameters": parameters,
        }

    def _normalize_image_config(self, value: Any) -> dict[str, Any]:
        """Return Google imageConfig payload with canonical camelCase keys."""
        if not isinstance(value, dict):
            return {}

        normalized: dict[str, Any] = {}
        key_map = {
            "aspect_ratio": "aspectRatio",
            "image_size": "imageSize",
            "aspectRatio": "aspectRatio",
            "imageSize": "imageSize",
        }
        for key, raw in value.items():
            if raw is None:
                continue
            target_key = key_map.get(str(key), str(key))
            normalized[target_key] = raw
        return normalized

    def _extract_images(
        self,
        body: dict[str, Any],
        request: ProviderGenerationRequest,
    ) -> list[ProviderImage]:
        blobs = self._collect_image_blobs(body)
        if not blobs:
            raise ProviderError("Google returned no generated image data.")

        fallback_width = int(request.width) if request.width else 1024
        fallback_height = int(request.height) if request.height else 1024
        default_mime = self._mime_from_format(self._normalize_output_format(request.output_format))
        images: list[ProviderImage] = []
        for index, blob in enumerate(blobs, start=1):
            try:
                image_bytes = base64.b64decode(blob["data"])
            except Exception as exc:
                raise ProviderError(f"Failed to decode Google image payload at index {index}.") from exc

            width, height = self._probe_dimensions(image_bytes, fallback_width, fallback_height)
            images.append(
                ProviderImage(
                    data=image_bytes,
                    mime=str(blob.get("mime") or default_mime),
                    width=width,
                    height=height,
                    meta={"provider": self.name, "index": index},
                )
            )
        return images

    def _collect_image_blobs(self, body: dict[str, Any]) -> list[dict[str, str]]:
        blobs: list[dict[str, str]] = []

        candidates = body.get("candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                content = candidate.get("content")
                if not isinstance(content, dict):
                    continue
                parts = content.get("parts")
                if not isinstance(parts, list):
                    continue
                for part in parts:
                    if not isinstance(part, dict):
                        continue
                    inline_data = part.get("inlineData") or part.get("inline_data")
                    if not isinstance(inline_data, dict):
                        continue
                    data = inline_data.get("data")
                    if not isinstance(data, str) or not data.strip():
                        continue
                    mime = inline_data.get("mimeType") or inline_data.get("mime_type")
                    blobs.append({"data": data, "mime": str(mime or "image/png")})

        predictions = body.get("predictions")
        if isinstance(predictions, list):
            for prediction in predictions:
                if isinstance(prediction, str) and prediction.strip():
                    blobs.append({"data": prediction, "mime": "image/png"})
                    continue
                if not isinstance(prediction, dict):
                    continue

                direct_data = prediction.get("bytesBase64Encoded") or prediction.get("bytes_base64_encoded")
                if isinstance(direct_data, str) and direct_data.strip():
                    mime = prediction.get("mimeType") or prediction.get("mime_type")
                    blobs.append({"data": direct_data, "mime": str(mime or "image/png")})
                    continue

                image_obj = prediction.get("image")
                if isinstance(image_obj, dict):
                    image_data = image_obj.get("bytesBase64Encoded") or image_obj.get("bytes_base64_encoded")
                    if isinstance(image_data, str) and image_data.strip():
                        mime = image_obj.get("mimeType") or image_obj.get("mime_type")
                        blobs.append({"data": image_data, "mime": str(mime or "image/png")})

        return blobs

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

    def _probe_dimensions(
        self,
        image_bytes: bytes,
        fallback_width: int,
        fallback_height: int,
    ) -> tuple[int, int]:
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                return int(image.width), int(image.height)
        except (UnidentifiedImageError, OSError, ValueError):
            return int(fallback_width), int(fallback_height)

    def _extract_error_message(self, response: httpx.Response) -> str:
        def _collect_strings(value: Any) -> list[str]:
            if isinstance(value, str):
                text = value.strip()
                return [text] if text else []
            if isinstance(value, list):
                items: list[str] = []
                for entry in value:
                    items.extend(_collect_strings(entry))
                return items
            if isinstance(value, dict):
                items = []
                preferred_keys = (
                    "message",
                    "description",
                    "details",
                    "status",
                    "reason",
                    "field",
                )
                for key in preferred_keys:
                    if key in value:
                        items.extend(_collect_strings(value.get(key)))
                for key, entry in value.items():
                    if key in preferred_keys:
                        continue
                    items.extend(_collect_strings(entry))
                return items
            return []

        try:
            data = response.json()
        except ValueError:
            text = response.text.strip()
            return text[:400] if text else "Unknown error"

        error_obj = data.get("error") if isinstance(data, dict) else data
        messages = _collect_strings(error_obj)
        if messages:
            return " | ".join(messages)[:400]

        fallback = _collect_strings(data)
        if fallback:
            return " | ".join(fallback)[:400]

        text = response.text.strip()
        if text:
            return text[:400]
        text = str(data)
        return text[:400] if text else "Unknown error"
