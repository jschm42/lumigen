"""Replicate prediction adapter for hosted image models."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.config import Settings
from app.providers import http_common
from app.providers.base import (
    ProviderAdapter,
    ProviderError,
    ProviderGenerationRequest,
    ProviderGenerationResult,
    ProviderImage,
    ProviderServiceUnavailableError,
)

_KNOWN_MODELS = [
    "black-forest-labs/flux-1.1-pro",
    "black-forest-labs/flux-schnell",
    "google/imagen-4",
    "ideogram-ai/ideogram-v3-turbo",
    "recraft-ai/recraft-v3",
    "stability-ai/stable-diffusion-3.5-large",
]
_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9", "9:21", "4:5", "5:4"]
_TERMINAL = {"succeeded", "failed", "canceled"}
_POLL_INTERVAL_SECONDS = 1.5
# Keys that are internal to Lumigen and never forwarded as model inputs.
_INTERNAL_KEYS = {
    "aspect_ratio", "resolution", "negative_prompt", "width", "height", "seed",
    "image_config", "category_ids", "categories", "description", "default_aspect_ratio",
    "default_resolution", "system_prompt", "base_prompt",
}


class ReplicateAdapter(ProviderAdapter):
    """Adapter for Replicate predictions.

    Model identifiers are ``owner/name`` for official models or ``owner/name:version``
    for community models. Model-specific inputs can be set via the profile's
    ``params_json`` and are forwarded as-is. Only ``prompt`` plus explicitly chosen
    aspect ratio / seed / negative prompt are sent by default, because accepted inputs
    differ per model.
    """

    name = "replicate"
    display_name = "Replicate"
    homepage_url = "https://replicate.com/account/api-tokens"
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        """Return a curated list of popular official image models on Replicate."""
        _ = settings
        return list(_KNOWN_MODELS)

    def _build_input(self, request: ProviderGenerationRequest) -> dict[str, Any]:
        model_input: dict[str, Any] = {"prompt": request.prompt}
        ratio = http_common.resolve_aspect_ratio(request, _RATIOS, default=None)
        if ratio:
            model_input["aspect_ratio"] = ratio
        if request.seed is not None:
            model_input["seed"] = int(request.seed)
        if request.negative_prompt:
            model_input["negative_prompt"] = request.negative_prompt
        if request.n_images and int(request.n_images) > 1:
            model_input["num_outputs"] = int(request.n_images)
        if request.input_images:
            model_input["image"] = http_common.to_data_uri(request.input_images[0])
        if isinstance(request.params, dict):
            for key, value in request.params.items():
                if key not in _INTERNAL_KEYS and value is not None:
                    model_input[key] = value
        return model_input

    def _create_url_and_body(self, settings: Settings, model: str, model_input: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        base = settings.replicate_base_url.rstrip("/") + "/v1"
        identifier = (model or "").strip()
        if ":" in identifier:
            _, version = identifier.split(":", 1)
            return f"{base}/predictions", {"version": version, "input": model_input}
        if identifier.count("/") != 1:
            raise ProviderError("Replicate model must be 'owner/name' or 'owner/name:version'.")
        return f"{base}/models/{identifier}/predictions", {"input": model_input}

    @staticmethod
    def _output_urls(output: Any) -> list[str]:
        if isinstance(output, str):
            return [output]
        if isinstance(output, list):
            return [item for item in output if isinstance(item, str)]
        if isinstance(output, dict):
            return [value for value in output.values() if isinstance(value, str) and value.startswith("http")]
        return []

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        """Create a prediction, wait for it (sync mode, then polling) and download the outputs."""
        api_key = http_common.require_api_key(request, settings, "replicate_api_key", "Replicate")
        url, body = self._create_url_and_body(settings, request.model, self._build_input(request))
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Prefer": "wait=60",
        }
        self._log_request("POST", url, headers, body)
        deadline = time.monotonic() + float(settings.provider_http_generate_timeout_seconds)

        async with http_common.make_client(settings) as client:
            response = await client.post(url, headers=headers, json=body)
            http_common.raise_for_status(response, "Replicate")
            prediction = http_common.json_body(response, "Replicate")

            poll_url = (prediction.get("urls") or {}).get("get")
            while prediction.get("status") not in _TERMINAL:
                if not poll_url:
                    raise ProviderError("Replicate returned no polling URL.")
                if time.monotonic() > deadline:
                    raise ProviderServiceUnavailableError("Replicate prediction timed out.")
                await asyncio.sleep(_POLL_INTERVAL_SECONDS)
                poll = await client.get(poll_url, headers={"Authorization": f"Bearer {api_key}"})
                http_common.raise_for_status(poll, "Replicate")
                prediction = http_common.json_body(poll, "Replicate")

            status = prediction.get("status")
            if status != "succeeded":
                reason = prediction.get("error") or status
                raise ProviderError(f"Replicate prediction {status}: {reason}")

            images: list[ProviderImage] = []
            for idx, image_url in enumerate(self._output_urls(prediction.get("output")), start=1):
                images.append(
                    await http_common.download_image(
                        client, image_url, provider=self.name, index=idx,
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                )

        if not images:
            raise ProviderError("Replicate prediction returned no images.")
        return ProviderGenerationResult(
            images=images,
            raw_meta={
                "provider": self.name,
                "id": prediction.get("id"),
                "model": request.model,
                "metrics": prediction.get("metrics"),
                "count": len(images),
            },
        )
