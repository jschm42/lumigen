from __future__ import annotations

import base64
import logging
import re
from io import BytesIO
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
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        if not settings.openrouter_api_key:
            raise ProviderConfigError(
                "OpenRouter adapter requires OPENROUTER_API_KEY in .env."
            )

        url = settings.openrouter_base_url.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
        timeout = httpx.Timeout(30.0, connect=10.0)
        self._log_request("GET", url, headers)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)

        if response.status_code >= 400:
            message = self._extract_error_message(response)
            raise ProviderError(
                f"OpenRouter models request failed ({response.status_code}): {message}"
            )

        try:
            body = response.json()
        except Exception as exc:
            raise ProviderError(
                "OpenRouter returned a non-JSON models response."
            ) from exc

        models: list[str] = []
        for item in body.get("data") or []:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id") or item.get("name")
            if isinstance(model_id, str) and model_id.strip():
                models.append(model_id.strip())
        return models

    async def generate(
        self, request: ProviderGenerationRequest, settings: Settings
    ) -> ProviderGenerationResult:
        if not settings.openrouter_api_key:
            raise ProviderConfigError(
                "OpenRouter adapter requires OPENROUTER_API_KEY in .env."
            )

        url = settings.openrouter_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "X-Title": settings.app_name,
        }
        payload = self._build_payload(request)
        self._log_request("POST", url, headers, payload)

        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            if self._should_retry_with_image_only(response, payload):
                retry_payload = dict(payload)
                retry_payload["modalities"] = ["image"]
                response = await client.post(url, headers=headers, json=retry_payload)
                payload = retry_payload
            if self._should_retry_without_explicit_dimensions(response, payload):
                retry_payload = dict(payload)
                retry_payload.pop("width", None)
                retry_payload.pop("height", None)
                retry_payload.pop("size", None)
                response = await client.post(url, headers=headers, json=retry_payload)
                payload = retry_payload

            if response.status_code == 429:
                raise ProviderRateLimitError("OpenRouter rate limit reached (429).")
            if response.status_code == 503:
                raise ProviderServiceUnavailableError(
                    "OpenRouter service unavailable (503)."
                )
            if response.status_code >= 500:
                raise ProviderServiceUnavailableError(
                    f"OpenRouter upstream error ({response.status_code})."
                )
            if response.status_code >= 400:
                message = self._extract_error_message(response)
                raise ProviderError(
                    f"OpenRouter request failed ({response.status_code}): {message}"
                )

            try:
                body = response.json()
            except Exception as exc:
                raise ProviderError("OpenRouter returned a non-JSON response.") from exc

            normalized_output_format = self._normalize_output_format(
                request.output_format
            )
            image_refs = self._extract_image_refs(
                body, output_format=normalized_output_format
            )
            if not image_refs and self._should_retry_empty_success_with_image_only(
                payload
            ):
                retry_payload = dict(payload)
                retry_payload["modalities"] = ["image"]
                response = await client.post(url, headers=headers, json=retry_payload)

                if response.status_code == 429:
                    raise ProviderRateLimitError("OpenRouter rate limit reached (429).")
                if response.status_code == 503:
                    raise ProviderServiceUnavailableError(
                        "OpenRouter service unavailable (503)."
                    )
                if response.status_code >= 500:
                    raise ProviderServiceUnavailableError(
                        f"OpenRouter upstream error ({response.status_code})."
                    )
                if response.status_code >= 400:
                    message = self._extract_error_message(response)
                    raise ProviderError(
                        f"OpenRouter request failed ({response.status_code}): {message}"
                    )

                try:
                    body = response.json()
                except Exception as exc:
                    raise ProviderError(
                        "OpenRouter returned a non-JSON response."
                    ) from exc

                payload = retry_payload
                image_refs = self._extract_image_refs(
                    body, output_format=normalized_output_format
                )

            if not image_refs:
                summary = self._summarize_empty_image_response(body)
                raise ProviderError(
                    f"OpenRouter returned no generated image data. {summary}"
                )

            fallback_width, fallback_height = self._resolve_dimensions(request)
            images: list[ProviderImage] = []
            for idx, image_ref in enumerate(image_refs, start=1):
                image_bytes, mime = await self._read_image_payload(
                    client, image_ref, idx
                )
                width, height = self._probe_dimensions(
                    image_bytes, fallback_width, fallback_height
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

        return ProviderGenerationResult(
            images=images,
            raw_meta={
                "provider": self.name,
                "id": body.get("id"),
                "created": body.get("created"),
                "model": body.get("model") or request.model,
                "modalities": payload.get("modalities"),
                "usage": body.get("usage"),
                "count": len(images),
            },
        )

    def _build_payload(self, request: ProviderGenerationRequest) -> dict[str, Any]:
        content: Any = request.prompt
        if request.input_images:
            parts: list[dict[str, Any]] = [{"type": "text", "text": request.prompt}]
            for image in request.input_images:
                data_url = self._to_input_data_url(image.data, image.mime)
                if not data_url:
                    continue
                parts.append({"type": "image_url", "image_url": {"url": data_url}})
            content = parts

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [{"role": "user", "content": content}],
            "modalities": ["image", "text"],
            "stream": False,
            "n": max(1, int(request.n_images)),
        }

        image_config = (
            request.params.get("image_config")
            if isinstance(request.params, dict)
            else None
        )
        has_image_config_dimensions = (
            isinstance(image_config, dict)
            and (
                str(image_config.get("aspect_ratio") or "").strip() != ""
                or str(image_config.get("image_size") or "").strip() != ""
            )
        )
        explicit_dimensions = self._explicit_dimensions(request)
        if explicit_dimensions and not has_image_config_dimensions:
            width, height = explicit_dimensions
            # OpenRouter models are most consistent with a single `size` value.
            # Sending both `width`/`height` and `size` can lead to ambiguous handling.
            payload["size"] = f"{width}x{height}"

        if request.seed is not None:
            payload["seed"] = int(request.seed)

        output_format = self._normalize_output_format(request.output_format)
        if output_format:
            payload["output_format"] = output_format

        if isinstance(request.params, dict):
            for key, value in request.params.items():
                if key not in payload and value is not None:
                    payload[key] = value

        return payload

    def _to_input_data_url(self, data: bytes, mime: str) -> str:
        if not data or not mime:
            return ""
        b64_value = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64_value}"

    def _extract_image_refs(
        self, body: dict[str, Any], output_format: str
    ) -> list[str]:
        refs: list[str] = []
        choices = body.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message")
                if not isinstance(message, dict):
                    continue

                refs.extend(
                    self._extract_image_refs_from_message_images(
                        message.get("images"), output_format
                    )
                )
                refs.extend(
                    self._extract_image_refs_from_message_content(
                        message.get("content"), output_format
                    )
                )

        refs.extend(
            self._extract_image_refs_from_message_images(
                body.get("images"), output_format
            )
        )
        refs.extend(self._extract_image_refs_from_data(body.get("data"), output_format))
        refs.extend(
            self._extract_image_refs_from_output(body.get("output"), output_format)
        )
        return self._unique_refs(refs)

    def _extract_image_refs_from_message_images(
        self, value: Any, output_format: str
    ) -> list[str]:
        refs: list[str] = []
        if not isinstance(value, list):
            return refs

        for image_obj in value:
            ref = self._extract_single_image_ref(image_obj, output_format)
            if ref:
                refs.append(ref)
        return refs

    def _extract_image_refs_from_message_content(
        self, value: Any, output_format: str
    ) -> list[str]:
        refs: list[str] = []
        if isinstance(value, str):
            refs.extend(self._extract_refs_from_text(value))
            return refs

        if not isinstance(value, list):
            return refs

        for part in value:
            if isinstance(part, str):
                refs.extend(self._extract_refs_from_text(part))
                continue
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type") or "").strip().lower()
            if part_type in {"image_url", "image", "input_image", "output_image"}:
                ref = self._extract_single_image_ref(part, output_format)
                if ref:
                    refs.append(ref)
                continue
            text_value = part.get("text")
            if isinstance(text_value, str):
                refs.extend(self._extract_refs_from_text(text_value))
                continue
            if part_type:
                continue
            ref = self._extract_single_image_ref(part, output_format)
            if ref:
                refs.append(ref)
        return refs

    def _extract_image_refs_from_data(
        self, value: Any, output_format: str
    ) -> list[str]:
        refs: list[str] = []
        if not isinstance(value, list):
            return refs
        for item in value:
            ref = self._extract_single_image_ref(item, output_format)
            if ref:
                refs.append(ref)
        return refs

    def _extract_image_refs_from_output(
        self, value: Any, output_format: str
    ) -> list[str]:
        refs: list[str] = []
        if not isinstance(value, list):
            return refs

        for item in value:
            if isinstance(item, str):
                refs.extend(self._extract_refs_from_text(item))
                continue
            if not isinstance(item, dict):
                continue

            ref = self._extract_single_image_ref(item, output_format)
            if ref:
                refs.append(ref)

            content = item.get("content")
            refs.extend(
                self._extract_image_refs_from_message_content(content, output_format)
            )
        return refs

    def _extract_single_image_ref(
        self, image_obj: Any, output_format: str
    ) -> Optional[str]:
        if isinstance(image_obj, str):
            return self._normalize_ref_string(image_obj, output_format)

        if not isinstance(image_obj, dict):
            return None

        nested = image_obj.get("image_url")
        if isinstance(nested, dict):
            value = nested.get("url") or nested.get("uri") or nested.get("image_url")
            if isinstance(value, str) and value.strip():
                return self._normalize_ref_string(value.strip(), output_format)

        if isinstance(nested, str) and nested.strip():
            return self._normalize_ref_string(nested.strip(), output_format)

        direct = image_obj.get("url") or image_obj.get("uri") or image_obj.get("href")
        if isinstance(direct, str) and direct.strip():
            return self._normalize_ref_string(direct.strip(), output_format)

        text = image_obj.get("text")
        if isinstance(text, str) and text.strip():
            refs = self._extract_refs_from_text(text)
            if refs:
                return refs[0]

        b64 = (
            image_obj.get("b64_json")
            or image_obj.get("b64")
            or image_obj.get("base64")
            or image_obj.get("image_base64")
        )
        if isinstance(b64, str) and self._looks_like_base64_payload(b64):
            return self._to_data_url(b64, output_format)

        return None

    def _normalize_ref_string(self, value: str, output_format: str) -> Optional[str]:
        raw = value.strip()
        if not raw:
            return None
        if raw.startswith("data:"):
            return raw
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        if self._looks_like_base64_payload(raw):
            return self._to_data_url(raw, output_format)
        return None

    def _extract_refs_from_text(self, value: str) -> list[str]:
        refs: list[str] = []
        if not value:
            return refs

        for match in re.findall(
            r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+", value
        ):
            if isinstance(match, str) and match.strip():
                refs.append(match.strip())

        for match in re.findall(r"!\[[^\]]*\]\((https?://[^)]+)\)", value):
            if isinstance(match, str) and match.strip():
                refs.append(match.strip())

        for match in re.findall(r"https?://[^\s)\]>\"]+", value):
            if isinstance(match, str) and match.strip():
                refs.append(match.strip())

        return self._unique_refs(refs)

    def _unique_refs(self, refs: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for ref in refs:
            normalized = ref.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _looks_like_base64_payload(self, value: str) -> bool:
        payload = re.sub(r"\s+", "", value.strip())
        if len(payload) < 128:
            return False
        return re.fullmatch(r"[A-Za-z0-9+/=]+", payload) is not None

    def _to_data_url(self, payload: str, output_format: str) -> str:
        encoded = re.sub(r"\s+", "", payload.strip())
        return f"data:{self._mime_from_output_format(output_format)};base64,{encoded}"

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
            content_type = (
                str(response.headers.get("content-type") or "")
                .split(";", 1)[0]
                .strip()
                .lower()
            )
            mime = content_type or self._mime_from_output_format("png")
            if not response.content:
                raise ProviderError(
                    f"OpenRouter image URL payload was empty at index {idx}."
                )
            return response.content, mime

        raise ProviderError(
            f"OpenRouter image reference at index {idx} had unsupported format."
        )

    def _decode_data_url(self, image_ref: str, idx: int) -> tuple[bytes, str]:
        match = re.match(
            r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$",
            image_ref,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            raise ProviderError(
                f"OpenRouter image payload at index {idx} was not a valid base64 data URL."
            )

        mime = match.group("mime").strip().lower() or self._mime_from_output_format(
            "png"
        )
        data = match.group("data").strip()

        try:
            image_bytes = base64.b64decode(data)
        except Exception as exc:
            raise ProviderError(
                f"Failed to decode OpenRouter image payload at index {idx}."
            ) from exc

        if not image_bytes:
            raise ProviderError(
                f"Decoded OpenRouter image payload was empty at index {idx}."
            )

        return image_bytes, mime

    def _explicit_dimensions(
        self, request: ProviderGenerationRequest
    ) -> Optional[tuple[int, int]]:
        if request.width is None or request.height is None:
            return None
        try:
            width = int(request.width)
            height = int(request.height)
        except (TypeError, ValueError):
            return None
        if width <= 0 or height <= 0:
            return None
        return width, height

    def _resolve_dimensions(
        self, request: ProviderGenerationRequest
    ) -> tuple[int, int]:
        if request.width and request.height:
            width = int(request.width)
            height = int(request.height)
            if width > 0 and height > 0:
                return width, height

        return 1024, 1024

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

    def _should_retry_with_image_only(
        self, response: httpx.Response, payload: dict[str, Any]
    ) -> bool:
        if response.status_code not in {400, 404}:
            return False

        requested_modalities = payload.get("modalities")
        if not isinstance(requested_modalities, list):
            return False

        normalized_modalities = {
            str(modality).strip().lower()
            for modality in requested_modalities
            if isinstance(modality, str) and modality.strip()
        }
        if normalized_modalities != {"image", "text"}:
            return False

        message = self._extract_error_message(response).lower()
        return (
            "no endpoints found that support the requested output modalities" in message
        )

    def _should_retry_without_explicit_dimensions(
        self, response: httpx.Response, payload: dict[str, Any]
    ) -> bool:
        if response.status_code != 400:
            return False
        has_explicit_dimensions = any(
            key in payload for key in ("width", "height", "size")
        )
        if not has_explicit_dimensions:
            return False
        message = self._extract_error_message(response).lower()
        keywords = (
            "unknown",
            "unsupported",
            "invalid",
            "not allowed",
            "not supported",
            "unexpected",
            "unrecognized",
        )
        touches_dimensions = any(
            token in message for token in ("width", "height", "size")
        )
        is_param_validation = any(token in message for token in keywords)
        return touches_dimensions and is_param_validation

    def _should_retry_empty_success_with_image_only(
        self, payload: dict[str, Any]
    ) -> bool:
        requested_modalities = payload.get("modalities")
        if not isinstance(requested_modalities, list):
            return True

        normalized_modalities = {
            str(modality).strip().lower()
            for modality in requested_modalities
            if isinstance(modality, str) and modality.strip()
        }
        return normalized_modalities != {"image"}

    def _summarize_empty_image_response(self, body: dict[str, Any]) -> str:
        summary: list[str] = [f"top_keys={sorted(body.keys())}"]

        choices = body.get("choices")
        if isinstance(choices, list):
            summary.append(f"choices={len(choices)}")
            if choices and isinstance(choices[0], dict):
                choice = choices[0]
                finish_reason = choice.get("finish_reason") or choice.get(
                    "native_finish_reason"
                )
                if finish_reason:
                    summary.append(f"finish_reason={finish_reason}")

                message = choice.get("message")
                if isinstance(message, dict):
                    summary.append(f"message_keys={sorted(message.keys())}")
                    images = message.get("images")
                    if isinstance(images, list):
                        summary.append(f"message_images={len(images)}")
                    content = message.get("content")
                    if isinstance(content, list):
                        summary.append(f"content_parts={len(content)}")
                    elif isinstance(content, str):
                        content_excerpt = content.strip().replace("\n", " ")
                        if content_excerpt:
                            summary.append(f"content_excerpt={content_excerpt[:160]}")
        elif choices is not None:
            summary.append(f"choices_type={type(choices).__name__}")

        top_images = body.get("images")
        if isinstance(top_images, list):
            summary.append(f"top_images={len(top_images)}")
        top_data = body.get("data")
        if isinstance(top_data, list):
            summary.append(f"top_data={len(top_data)}")
        top_output = body.get("output")
        if isinstance(top_output, list):
            summary.append(f"top_output={len(top_output)}")

        return "; ".join(summary)[:1000]

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
