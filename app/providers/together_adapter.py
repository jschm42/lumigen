"""Together AI image generation adapter (FLUX and other hosted models)."""
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
    "black-forest-labs/FLUX.2-dev",
    "black-forest-labs/FLUX.1.1-pro",
    "black-forest-labs/FLUX.1-schnell",
    "black-forest-labs/FLUX.1-schnell-Free",
]
_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9", "9:21"]
_PASSTHROUGH = {"steps", "guidance_scale", "disable_safety_checker", "image_loras"}
_MAX_IMAGES = 4


class TogetherAdapter(ProviderAdapter):
    """Adapter for ``POST /v1/images/generations`` of the Together AI API."""

    name = "together"
    display_name = "Together AI"
    homepage_url = "https://api.together.ai/settings/api-keys"
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        """Return a curated list of popular Together AI image models."""
        _ = settings
        return list(_KNOWN_MODELS)

    def _build_payload(self, request: ProviderGenerationRequest) -> dict[str, Any]:
        if request.width and request.height:
            width, height = int(request.width), int(request.height)
        else:
            ratio = http_common.resolve_aspect_ratio(request, _RATIOS, default="1:1")
            width, height = http_common.dimensions_for_ratio(ratio)
        output_format = (request.output_format or "png").lower()
        payload: dict[str, Any] = {
            "model": request.model,
            "prompt": request.prompt,
            "width": width,
            "height": height,
            "n": max(1, min(_MAX_IMAGES, int(request.n_images or 1))),
            "response_format": "base64",
            "output_format": "jpeg" if output_format in ("jpg", "jpeg") else "png",
        }
        if request.seed is not None:
            payload["seed"] = int(request.seed)
        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt
        if request.input_images:
            payload["image_url"] = http_common.to_data_uri(request.input_images[0])
        payload.update(http_common.passthrough_params(request, _PASSTHROUGH))
        return payload

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        """Generate images and return them decoded from base64."""
        api_key = http_common.require_api_key(request, settings, "together_api_key", "Together AI")
        url = settings.together_base_url.rstrip("/") + "/v1/images/generations"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = self._build_payload(request)
        self._log_request("POST", url, headers, payload)

        async with http_common.make_client(settings) as client:
            response = await client.post(url, headers=headers, json=payload)
            http_common.raise_for_status(response, "Together AI")
            body = http_common.json_body(response, "Together AI")
            images = []
            for idx, item in enumerate(body.get("data") or [], start=1):
                if not isinstance(item, dict):
                    continue
                if item.get("b64_json"):
                    images.append(http_common.image_from_base64(item["b64_json"], provider=self.name, index=idx))
                elif item.get("url"):
                    images.append(await http_common.download_image(client, item["url"], provider=self.name, index=idx))

        if not images:
            raise ProviderError("Together AI returned no images.")
        return ProviderGenerationResult(
            images=images,
            raw_meta={"provider": self.name, "id": body.get("id"), "model": body.get("model") or request.model, "count": len(images)},
        )
