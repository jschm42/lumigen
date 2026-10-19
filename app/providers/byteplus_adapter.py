"""BytePlus ModelArk adapter for ByteDance Seedream image models."""
from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.providers import http_common
from app.providers.base import (
    ProviderAdapter,
    ProviderError,
    ProviderGenerationRequest,
    ProviderGenerationResult,
)

_KNOWN_MODELS = [
    "seedream-5-0-260128",
    "dola-seedream-5-0-pro-260628",
    "seedream-4-5-251128",
    "seedream-4-0-250828",
]
_RATIOS = ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "21:9", "9:21"]
# Resolution keyword -> edge length of the equivalent square image.
_RESOLUTION_EDGE = {"1K": 1024, "2K": 2048, "3K": 3072, "4K": 4096}
_MAX_REFERENCE_IMAGES = 10
_MAX_IMAGES = 15
_PASSTHROUGH = {"guidance_scale", "watermark"}


class BytePlusAdapter(ProviderAdapter):
    """Adapter for ``POST /api/v3/images/generations`` of BytePlus ModelArk (Seedream).

    ``size`` is sent as a resolution keyword (``2K``) or, when an aspect ratio is
    chosen, as ``WIDTHxHEIGHT`` at that resolution. Several images use sequential
    generation; reference images are sent as base64 data URIs.
    """

    name = "byteplus"
    display_name = "BytePlus ModelArk (Seedream)"
    homepage_url = "https://console.byteplus.com/ark/region:ark+ap-southeast-1/apiKey"
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        """Return the known Seedream model IDs (account-specific ``ep-...`` IDs also work)."""
        _ = settings
        return list(_KNOWN_MODELS)

    def _resolution(self, request: ProviderGenerationRequest) -> str:
        raw = ""
        if isinstance(request.params, dict):
            raw = str(request.params.get("resolution") or "").strip().upper()
        return raw if raw in _RESOLUTION_EDGE else "2K"

    def _size(self, request: ProviderGenerationRequest) -> str:
        if request.width and request.height:
            return f"{int(request.width)}x{int(request.height)}"
        resolution = self._resolution(request)
        ratio = http_common.resolve_aspect_ratio(request, _RATIOS, default=None)
        if not ratio:
            return resolution
        edge = _RESOLUTION_EDGE[resolution]
        width, height = http_common.dimensions_for_ratio(ratio, megapixels=(edge * edge) / (1024 * 1024))
        return f"{width}x{height}"

    def _build_payload(self, request: ProviderGenerationRequest) -> dict[str, Any]:
        count = max(1, min(_MAX_IMAGES, int(request.n_images or 1)))
        payload: dict[str, Any] = {
            "model": request.model,
            "prompt": request.prompt,
            "size": self._size(request),
            "response_format": "b64_json",
            "watermark": False,
            "sequential_image_generation": "auto" if count > 1 else "disabled",
        }
        if count > 1:
            payload["sequential_image_generation_options"] = {"max_images": count}
        if request.seed is not None:
            payload["seed"] = int(request.seed)
        if request.input_images:
            refs = [http_common.to_data_uri(img) for img in request.input_images[:_MAX_REFERENCE_IMAGES]]
            payload["image"] = refs[0] if len(refs) == 1 else refs
        payload.update(http_common.passthrough_params(request, _PASSTHROUGH))
        return payload

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        """Generate Seedream images and decode them from base64 (or download URLs)."""
        api_key = http_common.require_api_key(request, settings, "byteplus_api_key", "BytePlus ModelArk")
        url = settings.byteplus_base_url.rstrip("/") + "/images/generations"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = self._build_payload(request)
        self._log_request("POST", url, headers, payload)

        async with http_common.make_client(settings) as client:
            response = await client.post(url, headers=headers, json=payload)
            http_common.raise_for_status(response, "BytePlus ModelArk")
            body = http_common.json_body(response, "BytePlus ModelArk")
            images = []
            errors: list[str] = []
            for idx, item in enumerate(body.get("data") or [], start=1):
                if not isinstance(item, dict):
                    continue
                if item.get("error"):
                    error = item["error"]
                    errors.append(str(error.get("message") if isinstance(error, dict) else error))
                    continue
                if item.get("b64_json"):
                    images.append(http_common.image_from_base64(item["b64_json"], provider=self.name, index=idx))
                elif item.get("url"):
                    images.append(await http_common.download_image(client, item["url"], provider=self.name, index=idx))

        if not images:
            detail = f": {errors[0]}" if errors else ""
            raise ProviderError(f"BytePlus ModelArk returned no images{detail}")
        return ProviderGenerationResult(
            images=images,
            raw_meta={
                "provider": self.name,
                "model": body.get("model") or request.model,
                "usage": body.get("usage"),
                "count": len(images),
                "partial_errors": errors or None,
            },
        )
