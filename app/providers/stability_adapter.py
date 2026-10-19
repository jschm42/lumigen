"""Stability AI (Stable Image Ultra / Core / SD 3.5) provider adapter."""
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
    ProviderImage,
)

_SD3_MODELS = ("sd3.5-large", "sd3.5-large-turbo", "sd3.5-medium", "sd3.5-flash")
_KNOWN_MODELS = ["ultra", "core", *_SD3_MODELS]
_ASPECT_RATIOS = ["16:9", "1:1", "21:9", "2:3", "3:2", "4:5", "5:4", "9:16", "9:21"]
_OUTPUT_FORMATS = {"png", "jpeg", "webp"}
_MAX_IMAGES = 4
_PASSTHROUGH = {"style_preset", "strength", "cfg_scale"}


class StabilityAdapter(ProviderAdapter):
    """Adapter for the Stability AI v2beta Stable Image generate endpoints.

    Model identifiers: ``ultra``, ``core`` or an SD 3.5 model such as ``sd3.5-large``.
    The API returns one image per request, so ``n_images`` results in several calls.
    """

    name = "stability"
    display_name = "Stability AI"
    homepage_url = "https://platform.stability.ai/account/keys"
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        """Return the supported Stable Image model identifiers."""
        _ = settings
        return list(_KNOWN_MODELS)

    def _endpoint(self, settings: Settings, model: str) -> tuple[str, dict[str, str]]:
        normalized = (model or "core").strip().lower()
        base = settings.stability_base_url.rstrip("/") + "/v2beta/stable-image/generate/"
        if normalized in ("ultra", "core"):
            return base + normalized, {}
        if normalized.startswith("sd3"):
            return base + "sd3", {"model": normalized}
        raise ProviderError(f"Unknown Stability AI model '{model}'. Use one of: {', '.join(_KNOWN_MODELS)}.")

    def _build_fields(self, request: ProviderGenerationRequest, extra: dict[str, str]) -> dict[str, Any]:
        output_format = (request.output_format or "png").lower().replace("jpg", "jpeg")
        fields: dict[str, Any] = {
            "prompt": request.prompt,
            "output_format": output_format if output_format in _OUTPUT_FORMATS else "png",
            **extra,
        }
        if request.negative_prompt:
            fields["negative_prompt"] = request.negative_prompt
        if request.seed is not None:
            fields["seed"] = str(request.seed)
        if request.input_images:
            fields["mode"] = "image-to-image" if "model" in extra else None
            fields.setdefault("strength", "0.7")
        else:
            fields["aspect_ratio"] = http_common.resolve_aspect_ratio(request, _ASPECT_RATIOS, default="1:1")
        for key, value in http_common.passthrough_params(request, _PASSTHROUGH).items():
            fields[key] = str(value)
        return {key: value for key, value in fields.items() if value is not None}

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        """Generate ``n_images`` images (one API call each) and return them."""
        api_key = http_common.require_api_key(request, settings, "stability_api_key", "Stability AI")
        url, extra = self._endpoint(settings, request.model)
        if request.input_images and url.endswith("/core"):
            raise ProviderError("Stability AI 'core' does not accept reference images; use 'ultra' or an SD 3.5 model.")
        fields = self._build_fields(request, extra)
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        count = max(1, min(_MAX_IMAGES, int(request.n_images or 1)))
        self._log_request("POST", url, headers, fields)

        images: list[ProviderImage] = []
        seeds: list[Any] = []
        async with http_common.make_client(settings) as client:
            for idx in range(1, count + 1):
                call_fields = dict(fields)
                if request.seed is not None and count > 1:
                    # A fixed seed would return the same image for every call.
                    call_fields["seed"] = str(int(request.seed) + idx - 1)
                files: dict[str, Any] = {key: (None, str(value)) for key, value in call_fields.items()}
                if request.input_images:
                    first = request.input_images[0]
                    files["image"] = ("input", first.data, first.mime)
                response = await client.post(url, headers=headers, files=files)
                http_common.raise_for_status(response, "Stability AI")
                body = http_common.json_body(response, "Stability AI")
                if str(body.get("finish_reason") or "").upper() == "CONTENT_FILTERED":
                    raise ProviderError("Stability AI filtered the image (content moderation).")
                encoded = body.get("image")
                if not isinstance(encoded, str) or not encoded:
                    raise ProviderError("Stability AI returned no image data.")
                images.append(
                    http_common.image_from_base64(encoded, provider=self.name, index=idx, meta={"seed": body.get("seed")})
                )
                seeds.append(body.get("seed"))

        return ProviderGenerationResult(
            images=images,
            raw_meta={"provider": self.name, "model": request.model, "seeds": seeds, "count": len(images)},
        )
