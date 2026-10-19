"""Shared helpers for the HTTP-based image provider adapters."""
from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

import httpx
from PIL import Image

from app.config import Settings
from app.providers.base import (
    ProviderConfigError,
    ProviderError,
    ProviderGenerationRequest,
    ProviderImage,
    ProviderInputImage,
    ProviderRateLimitError,
    ProviderServiceUnavailableError,
)

_PIL_FORMAT_TO_MIME = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}


def make_client(settings: Settings) -> httpx.AsyncClient:
    """Return an ``httpx.AsyncClient`` with the generic provider timeouts (patched in tests)."""
    timeout = httpx.Timeout(
        settings.provider_http_generate_timeout_seconds,
        connect=settings.provider_http_connect_timeout_seconds,
    )
    return httpx.AsyncClient(timeout=timeout, follow_redirects=True)


def require_api_key(request: ProviderGenerationRequest, settings: Settings, attr: str, label: str) -> str:
    """Return the request's custom key or the configured settings key, else raise."""
    key = (request.api_key or getattr(settings, attr, None) or "").strip()
    if not key:
        raise ProviderConfigError(f"{label} requires an API key (Admin -> API Keys or {attr.upper()} in .env).")
    return key


def error_message(response: httpx.Response) -> str:
    """Extract a short human-readable error message from a provider response."""
    try:
        body = response.json()
    except Exception:
        return (response.text or "").strip()[:300] or response.reason_phrase
    if isinstance(body, dict):
        for key in ("detail", "message", "error", "errors", "name"):
            value = body.get(key)
            if isinstance(value, dict):
                value = value.get("message") or value.get("detail") or value
            if isinstance(value, list) and value:
                value = value[0]
            if value:
                return str(value)[:300]
    return str(body)[:300]


def raise_for_status(response: httpx.Response, label: str) -> None:
    """Map HTTP error codes to the provider exception hierarchy used for retries."""
    status = response.status_code
    if status < 400:
        return
    if status == 429:
        raise ProviderRateLimitError(f"{label} rate limit reached (429).")
    if status in (502, 503, 504):
        raise ProviderServiceUnavailableError(f"{label} service unavailable ({status}).")
    if status >= 500:
        raise ProviderServiceUnavailableError(f"{label} upstream error ({status}).")
    raise ProviderError(f"{label} request failed ({status}): {error_message(response)}")


def json_body(response: httpx.Response, label: str) -> Any:
    """Return the decoded JSON body or raise a ``ProviderError``."""
    try:
        return response.json()
    except Exception as exc:
        raise ProviderError(f"{label} returned a non-JSON response.") from exc


def image_from_bytes(
    data: bytes,
    *,
    provider: str,
    index: int,
    fallback_mime: str = "image/png",
    meta: dict[str, Any] | None = None,
) -> ProviderImage:
    """Build a ``ProviderImage`` and read its real dimensions and MIME type with Pillow."""
    if not data:
        raise ProviderError(f"{provider} returned an empty image.")
    width = height = 0
    mime = fallback_mime
    try:
        with Image.open(BytesIO(data)) as img:
            width, height = img.size
            mime = _PIL_FORMAT_TO_MIME.get(str(img.format or "").upper(), fallback_mime)
    except Exception as exc:
        raise ProviderError(f"{provider} returned data that is not a valid image.") from exc
    return ProviderImage(
        data=data,
        mime=mime,
        width=width,
        height=height,
        meta={"provider": provider, "index": index, **(meta or {})},
    )


def image_from_base64(value: str, *, provider: str, index: int, meta: dict[str, Any] | None = None) -> ProviderImage:
    """Decode a (optionally ``data:``-prefixed) base64 image string."""
    raw = value.split(",", 1)[1] if value.startswith("data:") else value
    try:
        data = base64.b64decode(raw)
    except Exception as exc:
        raise ProviderError(f"{provider} returned invalid base64 image data.") from exc
    return image_from_bytes(data, provider=provider, index=index, meta=meta)


async def download_image(
    client: httpx.AsyncClient,
    url: str,
    *,
    provider: str,
    index: int,
    headers: dict[str, str] | None = None,
    meta: dict[str, Any] | None = None,
) -> ProviderImage:
    """Download a generated image from a (usually short-lived) provider URL."""
    response = await client.get(url, headers=headers or {})
    raise_for_status(response, f"{provider} image download")
    content_type = (response.headers.get("content-type") or "image/png").split(";")[0].strip()
    return image_from_bytes(
        response.content,
        provider=provider,
        index=index,
        fallback_mime=content_type if content_type.startswith("image/") else "image/png",
        meta=meta,
    )


def to_data_uri(image: ProviderInputImage) -> str:
    """Return a ``data:`` URI for an input image."""
    return f"data:{image.mime};base64,{base64.b64encode(image.data).decode('ascii')}"


def _ratio_value(ratio: str) -> float | None:
    for separator in (":", "x"):
        if separator in ratio:
            left, _, right = ratio.partition(separator)
            try:
                w, h = float(left), float(right)
            except ValueError:
                return None
            return w / h if w > 0 and h > 0 else None
    return None


def resolve_aspect_ratio(
    request: ProviderGenerationRequest,
    allowed: list[str],
    *,
    default: str | None,
    separator: str = ":",
) -> str | None:
    """Map the requested aspect ratio (or width/height) onto a provider's allowed values.

    ``allowed`` uses the provider's own notation (``16:9`` or ``16x9``). An exact match is
    preferred; otherwise the closest allowed ratio is returned. Returns ``default`` when
    nothing was requested.
    """
    candidates: list[str] = []
    if request.aspect_ratio:
        candidates.append(request.aspect_ratio)
    if isinstance(request.params, dict) and request.params.get("aspect_ratio"):
        candidates.append(str(request.params["aspect_ratio"]))

    target: float | None = None
    for candidate in candidates:
        normalized = candidate.strip().lower().replace(":", separator).replace("x", separator)
        if normalized in allowed:
            return normalized
        if target is None:
            target = _ratio_value(candidate.strip().lower())
    if target is None and request.width and request.height:
        target = request.width / request.height
    if target is None:
        return default

    scored = [(abs((_ratio_value(item) or 0) - target), item) for item in allowed if _ratio_value(item)]
    return min(scored)[1] if scored else default


def dimensions_for_ratio(ratio: str | None, *, megapixels: float = 1.0, multiple: int = 16) -> tuple[int, int]:
    """Return width/height for *ratio* at roughly *megapixels*, rounded to *multiple*."""
    value = _ratio_value(ratio or "1:1") or 1.0
    area = megapixels * 1024 * 1024
    width = (area * value) ** 0.5
    height = width / value

    def _round(v: float) -> int:
        return max(multiple, int(round(v / multiple)) * multiple)

    return _round(width), _round(height)


def passthrough_params(request: ProviderGenerationRequest, allowed: set[str]) -> dict[str, Any]:
    """Return profile ``params_json`` entries whose keys are explicitly allowed."""
    if not isinstance(request.params, dict):
        return {}
    return {key: value for key, value in request.params.items() if key in allowed and value is not None}
