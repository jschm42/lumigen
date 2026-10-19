"""Ideogram 3.0 image generation adapter."""
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

# Model identifier -> Ideogram rendering speed.
_MODELS = {
    "ideogram-v3-turbo": "TURBO",
    "ideogram-v3": "DEFAULT",
    "ideogram-v3-quality": "QUALITY",
}
_ASPECT_RATIOS = [
    "1x3", "3x1", "1x2", "2x1", "9x16", "16x9", "10x16", "16x10",
    "2x3", "3x2", "3x4", "4x3", "4x5", "5x4", "1x1",
]
_MAX_IMAGES = 8
_PASSTHROUGH = {"style_type", "magic_prompt", "style_preset"}


class IdeogramAdapter(ProviderAdapter):
    """Adapter for ``POST /v1/ideogram-v3/generate`` (multipart, ``Api-Key`` header).

    Reference images are sent as style references. Result URLs expire, so images are
    downloaded immediately.
    """

    name = "ideogram"
    display_name = "Ideogram"
    homepage_url = "https://developer.ideogram.ai"
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        """Return the Ideogram 3.0 model identifiers (one per rendering speed)."""
        _ = settings
        return list(_MODELS)

    def _build_fields(self, request: ProviderGenerationRequest) -> dict[str, str]:
        speed = _MODELS.get((request.model or "").strip().lower())
        if speed is None:
            raise ProviderError(f"Unknown Ideogram model '{request.model}'. Use one of: {', '.join(_MODELS)}.")
        fields: dict[str, Any] = {
            "prompt": request.prompt,
            "rendering_speed": speed,
            "aspect_ratio": http_common.resolve_aspect_ratio(request, _ASPECT_RATIOS, default="1x1", separator="x"),
            "num_images": max(1, min(_MAX_IMAGES, int(request.n_images or 1))),
        }
        if request.seed is not None:
            fields["seed"] = int(request.seed)
        if request.negative_prompt:
            fields["negative_prompt"] = request.negative_prompt
        fields.update(http_common.passthrough_params(request, _PASSTHROUGH))
        return {key: str(value) for key, value in fields.items()}

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        """Generate images and download them from the returned (temporary) URLs."""
        api_key = http_common.require_api_key(request, settings, "ideogram_api_key", "Ideogram")
        url = settings.ideogram_base_url.rstrip("/") + "/v1/ideogram-v3/generate"
        headers = {"Api-Key": api_key}
        fields = self._build_fields(request)
        self._log_request("POST", url, headers, fields)

        files: list[tuple[str, Any]] = [(key, (None, value)) for key, value in fields.items()]
        for idx, image in enumerate(request.input_images[:3]):
            files.append(("style_reference_images", (f"reference-{idx}", image.data, image.mime)))

        async with http_common.make_client(settings) as client:
            response = await client.post(url, headers=headers, files=files)
            http_common.raise_for_status(response, "Ideogram")
            body = http_common.json_body(response, "Ideogram")
            images = []
            skipped_unsafe = 0
            for idx, item in enumerate(body.get("data") or [], start=1):
                if not isinstance(item, dict):
                    continue
                if item.get("is_image_safe") is False or not item.get("url"):
                    skipped_unsafe += 1
                    continue
                images.append(
                    await http_common.download_image(
                        client, item["url"], provider=self.name, index=idx, meta={"seed": item.get("seed")}
                    )
                )

        if not images:
            if skipped_unsafe:
                raise ProviderError("Ideogram flagged all generated images as unsafe.")
            raise ProviderError("Ideogram returned no images.")
        return ProviderGenerationResult(
            images=images,
            raw_meta={"provider": self.name, "model": request.model, "count": len(images), "skipped_unsafe": skipped_unsafe},
        )
