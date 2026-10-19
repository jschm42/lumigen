"""xAI Grok Imagine image generation adapter."""
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

_KNOWN_MODELS = ["grok-imagine-image-2.0"]
_ASPECT_RATIOS = [
    "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "2:1", "1:2",
    "19.5:9", "9:19.5", "20:9", "9:20", "21:9", "5:2",
]
_MAX_IMAGES = 10
_PASSTHROUGH = {"quality"}


class XAIAdapter(ProviderAdapter):
    """Adapter for xAI's OpenAI-compatible ``/v1/images/generations`` and ``/v1/images/edits``."""

    name = "xai"
    display_name = "xAI (Grok Imagine)"
    homepage_url = "https://console.x.ai"
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        """Return the known Grok Imagine image models."""
        _ = settings
        return list(_KNOWN_MODELS)

    def _build_payload(self, request: ProviderGenerationRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model,
            "prompt": request.prompt,
            "n": max(1, min(_MAX_IMAGES, int(request.n_images or 1))),
            "response_format": "b64_json",
        }
        if request.input_images:
            # Edits follow the input image's aspect ratio.
            payload["image"] = {"url": http_common.to_data_uri(request.input_images[0]), "type": "image_url"}
        else:
            ratio = http_common.resolve_aspect_ratio(request, _ASPECT_RATIOS, default=None)
            if ratio:
                payload["aspect_ratio"] = ratio
        resolution = ""
        if isinstance(request.params, dict):
            resolution = str(request.params.get("resolution") or "").strip().lower()
        if resolution in ("1k", "2k"):
            payload["resolution"] = resolution
        payload.update(http_common.passthrough_params(request, _PASSTHROUGH))
        return payload

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        """Generate (or edit, with an input image) images via the xAI API."""
        api_key = http_common.require_api_key(request, settings, "xai_api_key", "xAI")
        endpoint = "/v1/images/edits" if request.input_images else "/v1/images/generations"
        url = settings.xai_base_url.rstrip("/") + endpoint
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = self._build_payload(request)
        self._log_request("POST", url, headers, payload)

        async with http_common.make_client(settings) as client:
            response = await client.post(url, headers=headers, json=payload)
            http_common.raise_for_status(response, "xAI")
            body = http_common.json_body(response, "xAI")
            images = []
            for idx, item in enumerate(body.get("data") or [], start=1):
                if not isinstance(item, dict):
                    continue
                meta = {"revised_prompt": item.get("revised_prompt")} if item.get("revised_prompt") else None
                if item.get("b64_json"):
                    images.append(http_common.image_from_base64(item["b64_json"], provider=self.name, index=idx, meta=meta))
                elif item.get("url"):
                    images.append(await http_common.download_image(client, item["url"], provider=self.name, index=idx, meta=meta))

        if not images:
            raise ProviderError("xAI returned no images.")
        return ProviderGenerationResult(
            images=images,
            raw_meta={"provider": self.name, "model": request.model, "usage": body.get("usage"), "count": len(images)},
        )
