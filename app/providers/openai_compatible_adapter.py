from __future__ import annotations

import logging
from io import BytesIO
from typing import Any
from urllib.parse import urljoin

import httpx
from PIL import Image

from app.config import Settings
from app.providers.base import (
    EndpointConfig,
    ProviderAdapter,
    ProviderConfigError,
    ProviderError,
    ProviderGenerationRequest,
    ProviderGenerationResult,
    ProviderImage,
)
from app.providers.http_common import (
    download_image,
    image_from_base64,
    json_body,
    raise_for_status,
)

_LABEL = "OpenAI-compatible endpoint"


class OpenAICompatibleAdapter(ProviderAdapter):
    """Adapter for any server that implements the OpenAI Images API.

    Works with self-hosted or third-party gateways such as LocalAI, LiteLLM,
    vLLM-based servers or hosted OpenAI-compatible providers. The base URL and
    optional API key come from the model's custom endpoint (``request.endpoint``).

    Compared to the official OpenAI adapter it is deliberately lenient: it asks
    for ``b64_json`` but also accepts ``url`` responses, does not send OpenAI-only
    fields such as ``output_format``, and reads the real image size/MIME type from
    the returned bytes.

    Model-level ``provider_options``:

    - ``response_format``: ``"b64_json"`` (default), ``"url"`` or ``""`` to omit the field.
    - ``extra_params``: dict merged into the JSON payload (e.g. ``{"quality": "high"}``).
    """

    name = "openai_compatible"
    display_name = "OpenAI-compatible API"
    homepage_url = "https://platform.openai.com/docs/api-reference/images"
    _logger = logging.getLogger(__name__)

    #: Request params that are forwarded to the API when present on the profile/request.
    _allowed_param_keys = {"quality", "style", "user", "background", "moderation"}

    async def list_endpoint_models(self, endpoint: EndpointConfig, settings: Settings) -> list[str]:
        """Return all model IDs reported by ``GET {base_url}/models``."""
        url = f"{endpoint.root_url}/models"
        headers = self._headers(endpoint)
        self._log_request("GET", url, headers)
        async with self._client(settings, generate=False) as client:
            try:
                response = await client.get(url, headers=headers)
            except httpx.HTTPError as exc:
                raise ProviderError(f"{_LABEL} is not reachable at {endpoint.root_url}: {exc}") from exc
        raise_for_status(response, _LABEL)
        body = json_body(response, _LABEL)
        items = body.get("data") if isinstance(body, dict) else body
        model_ids: list[str] = []
        for item in items or []:
            model_id = item.get("id") if isinstance(item, dict) else item
            if isinstance(model_id, str) and model_id.strip():
                model_ids.append(model_id.strip())
        return model_ids

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        """Generate images via ``/images/generations`` (or ``/images/edits`` with input images)."""
        endpoint = self._require_endpoint(request)
        options = endpoint.options or {}

        async with self._client(settings, generate=True) as client:
            try:
                if request.input_images:
                    response = await self._post_edit(client, request, endpoint, options)
                else:
                    response = await self._post_generation(client, request, endpoint, options)
            except httpx.HTTPError as exc:
                raise ProviderError(f"{_LABEL} request to {endpoint.root_url} failed: {exc}") from exc

            raise_for_status(response, _LABEL)
            body = json_body(response, _LABEL)
            data_list = body.get("data") if isinstance(body, dict) else None
            if not data_list:
                raise ProviderError(f"{_LABEL} returned no image data.")

            images: list[ProviderImage] = []
            for index, item in enumerate(data_list, start=1):
                images.append(await self._image_from_item(client, item, endpoint, index))

        return ProviderGenerationResult(
            images=images,
            raw_meta={
                "provider": self.name,
                "endpoint": endpoint.name,
                "created": body.get("created"),
                "model": request.model,
                "usage": body.get("usage"),
                "count": len(images),
            },
        )

    # -- request building -------------------------------------------------

    def build_payload(self, request: ProviderGenerationRequest, options: dict[str, Any]) -> dict[str, Any]:
        """Return the JSON payload for ``/images/generations``."""
        payload: dict[str, Any] = {
            "model": request.model,
            "prompt": request.prompt,
            "n": max(1, int(request.n_images or 1)),
            "size": self._size_string(request),
        }
        response_format = self._response_format(options)
        if response_format:
            payload["response_format"] = response_format
        if isinstance(request.params, dict):
            for key, value in request.params.items():
                if key in self._allowed_param_keys and value is not None and key not in payload:
                    payload[key] = value
        extra = options.get("extra_params")
        if isinstance(extra, dict):
            payload.update(extra)
        return payload

    async def _post_generation(
        self,
        client: httpx.AsyncClient,
        request: ProviderGenerationRequest,
        endpoint: EndpointConfig,
        options: dict[str, Any],
    ) -> httpx.Response:
        url = f"{endpoint.root_url}/images/generations"
        headers = {**self._headers(endpoint), "Content-Type": "application/json"}
        payload = self.build_payload(request, options)
        self._log_request("POST", url, headers, payload)
        return await client.post(url, headers=headers, json=payload)

    async def _post_edit(
        self,
        client: httpx.AsyncClient,
        request: ProviderGenerationRequest,
        endpoint: EndpointConfig,
        options: dict[str, Any],
    ) -> httpx.Response:
        url = f"{endpoint.root_url}/images/edits"
        headers = self._headers(endpoint)
        payload = self.build_payload(request, options)
        data = {key: str(value) for key, value in payload.items() if not isinstance(value, (dict, list))}
        files = [("image", ("input.png", BytesIO(self._ensure_png(request.input_images[0].data)), "image/png"))]
        if len(request.input_images) > 1:
            files.append(("mask", ("mask.png", BytesIO(self._ensure_png(request.input_images[1].data)), "image/png")))
        self._log_request("POST", url, headers, {"data": data, "files": [name for name, _ in files]})
        return await client.post(url, headers=headers, data=data, files=files)

    async def _image_from_item(
        self, client: httpx.AsyncClient, item: Any, endpoint: EndpointConfig, index: int
    ) -> ProviderImage:
        if not isinstance(item, dict):
            raise ProviderError(f"{_LABEL} returned an unexpected image entry.")
        meta = {"revised_prompt": item.get("revised_prompt"), "endpoint": endpoint.name}
        b64_value = item.get("b64_json")
        if isinstance(b64_value, str) and b64_value:
            return image_from_base64(b64_value, provider=self.name, index=index, meta=meta)
        url = item.get("url")
        if isinstance(url, str) and url:
            if url.startswith("data:"):
                return image_from_base64(url, provider=self.name, index=index, meta=meta)
            # Relative URLs (common for local servers) resolve against the endpoint.
            absolute = urljoin(f"{endpoint.root_url}/", url)
            return await download_image(
                client, absolute, provider=self.name, index=index, headers=self._headers(endpoint), meta=meta
            )
        raise ProviderError(f"{_LABEL} response contained neither b64_json nor url.")

    # -- helpers -------------------------------------------------------------

    def _require_endpoint(self, request: ProviderGenerationRequest) -> EndpointConfig:
        endpoint = request.endpoint
        if endpoint is None or not endpoint.root_url:
            raise ProviderConfigError(f"{_LABEL} models need a custom endpoint with a base URL (Admin -> Endpoints).")
        return endpoint

    @staticmethod
    def _headers(endpoint: EndpointConfig) -> dict[str, str]:
        key = (endpoint.api_key or "").strip()
        return {"Authorization": f"Bearer {key}"} if key else {}

    @staticmethod
    def _response_format(options: dict[str, Any]) -> str | None:
        if "response_format" not in options:
            return "b64_json"
        value = str(options.get("response_format") or "").strip()
        return value or None

    @staticmethod
    def _client(settings: Settings, *, generate: bool) -> httpx.AsyncClient:
        read_timeout = (
            settings.provider_openai_compatible_generate_timeout_seconds
            if generate
            else settings.llm_models_timeout_seconds
        )
        timeout = httpx.Timeout(read_timeout, connect=settings.llm_models_connect_timeout_seconds)
        return httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    @staticmethod
    def _size_string(request: ProviderGenerationRequest) -> str:
        if request.width and request.height:
            return f"{int(request.width)}x{int(request.height)}"
        return "1024x1024"

    @staticmethod
    def _ensure_png(image_bytes: bytes) -> bytes:
        """Return *image_bytes* re-encoded as PNG, falling back to the input on failure."""
        try:
            with Image.open(BytesIO(image_bytes)) as pil_img:
                buffer = BytesIO()
                pil_img.save(buffer, format="PNG")
                return buffer.getvalue()
        except Exception:
            return image_bytes
