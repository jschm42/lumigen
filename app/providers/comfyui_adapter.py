from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from typing import Any

import httpx

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
from app.providers.comfyui_workflow import (
    DEFAULT_WORKFLOW,
    WorkflowError,
    fill_workflow,
    parse_workflow,
    used_placeholders,
)
from app.providers.http_common import error_message, image_from_bytes, json_body, raise_for_status

_LABEL = "ComfyUI"
_MAX_SEED = 2**32 - 1


class ComfyUIAdapter(ProviderAdapter):
    """Adapter for a ComfyUI server (``/prompt`` queue + ``/history`` polling + ``/view`` download).

    The workflow comes from the model's ``provider_options["workflow"]`` (an API-format
    graph with placeholders, see :mod:`app.providers.comfyui_workflow`); without one the
    built-in text-to-image graph is used and the model identifier is the checkpoint name.
    """

    name = "comfyui"
    display_name = "ComfyUI"
    homepage_url = "https://github.com/comfyanonymous/ComfyUI"
    _logger = logging.getLogger(__name__)

    async def list_endpoint_models(self, endpoint: EndpointConfig, settings: Settings) -> list[str]:
        """Return the checkpoint files the server can load (``CheckpointLoaderSimple`` options)."""
        url = f"{endpoint.root_url}/object_info/CheckpointLoaderSimple"
        async with self._client(settings) as client:
            response = await self._send(client, "GET", url, endpoint)
        raise_for_status(response, _LABEL)
        body = json_body(response, _LABEL)
        try:
            spec = body["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"]
        except (KeyError, TypeError) as exc:
            raise ProviderError(f"{_LABEL} did not report any checkpoints.") from exc
        return [str(name) for name in self._combo_options(spec)]

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        """Queue the filled workflow, wait for completion and download all output images."""
        endpoint = request.endpoint
        if endpoint is None or not endpoint.root_url:
            raise ProviderConfigError("ComfyUI models need a custom endpoint with a base URL (Admin -> Endpoints).")

        workflow = self._workflow_for(endpoint)
        seed = int(request.seed) if request.seed is not None else random.randint(0, _MAX_SEED)

        async with self._client(settings) as client:
            input_image_name = ""
            if request.input_images and "input_image" in used_placeholders(workflow):
                input_image_name = await self._upload_image(client, endpoint, request.input_images[0].data)

            values = {
                "prompt": request.prompt or "",
                "negative_prompt": request.negative_prompt or "",
                "seed": seed,
                "width": self._dimension(request.width),
                "height": self._dimension(request.height),
                "batch_size": max(1, int(request.n_images or 1)),
                "model": request.model,
                "input_image": input_image_name,
            }
            graph = fill_workflow(workflow, values)
            prompt_id = await self._queue_prompt(client, endpoint, graph)
            outputs = await self._wait_for_outputs(client, endpoint, prompt_id, settings)
            images = await self._download_outputs(client, endpoint, outputs, seed)

        if not images:
            raise ProviderError(f"{_LABEL} finished without producing images (does the workflow end in SaveImage?).")
        return ProviderGenerationResult(
            images=images,
            raw_meta={
                "provider": self.name,
                "endpoint": endpoint.name,
                "prompt_id": prompt_id,
                "model": request.model,
                "seed": seed,
                "custom_workflow": bool((endpoint.options or {}).get("workflow")),
                "count": len(images),
            },
        )

    # -- workflow ------------------------------------------------------------

    @staticmethod
    def _workflow_for(endpoint: EndpointConfig) -> dict[str, Any]:
        custom = (endpoint.options or {}).get("workflow")
        if not custom:
            return DEFAULT_WORKFLOW
        try:
            return parse_workflow(custom)
        except WorkflowError as exc:
            raise ProviderConfigError(f"Invalid ComfyUI workflow: {exc}") from exc

    @staticmethod
    def _dimension(value: int | None) -> int:
        """Return *value* rounded to a multiple of 8 (latent size requirement), default 1024."""
        size = int(value or 1024)
        return max(64, (size // 8) * 8)

    # -- HTTP steps ----------------------------------------------------------

    async def _queue_prompt(self, client: httpx.AsyncClient, endpoint: EndpointConfig, graph: dict[str, Any]) -> str:
        url = f"{endpoint.root_url}/prompt"
        payload = {"prompt": graph, "client_id": f"lumigen-{uuid.uuid4().hex}"}
        self._log_request("POST", url, self._headers(endpoint), payload)
        response = await self._send(client, "POST", url, endpoint, json=payload)
        if response.status_code == 400:
            raise ProviderError(f"{_LABEL} rejected the workflow: {self._node_errors(response)}")
        raise_for_status(response, _LABEL)
        prompt_id = json_body(response, _LABEL).get("prompt_id")
        if not prompt_id:
            raise ProviderError(f"{_LABEL} did not return a prompt_id.")
        return str(prompt_id)

    async def _wait_for_outputs(
        self, client: httpx.AsyncClient, endpoint: EndpointConfig, prompt_id: str, settings: Settings
    ) -> dict[str, Any]:
        url = f"{endpoint.root_url}/history/{prompt_id}"
        deadline = time.monotonic() + settings.provider_comfyui_generate_timeout_seconds
        while True:
            response = await self._send(client, "GET", url, endpoint)
            raise_for_status(response, _LABEL)
            entry = (json_body(response, _LABEL) or {}).get(prompt_id)
            if entry:
                status = entry.get("status") or {}
                if status.get("status_str") == "error":
                    raise ProviderError(f"{_LABEL} execution failed: {self._execution_error(status)}")
                if status.get("completed", True):
                    return entry.get("outputs") or {}
            if time.monotonic() >= deadline:
                raise ProviderError(
                    f"{_LABEL} did not finish within {int(settings.provider_comfyui_generate_timeout_seconds)}s."
                )
            await asyncio.sleep(settings.provider_comfyui_poll_interval_seconds)

    async def _download_outputs(
        self, client: httpx.AsyncClient, endpoint: EndpointConfig, outputs: dict[str, Any], seed: int
    ) -> list[ProviderImage]:
        files: list[dict[str, Any]] = []
        for node_output in outputs.values():
            for item in (node_output or {}).get("images") or []:
                if isinstance(item, dict) and item.get("filename"):
                    files.append(item)
        # Prefer final outputs (SaveImage) over temporary previews when both exist.
        saved = [item for item in files if item.get("type") == "output"]
        selected = saved or files

        images: list[ProviderImage] = []
        for index, item in enumerate(selected, start=1):
            params = {
                "filename": item["filename"],
                "subfolder": item.get("subfolder", ""),
                "type": item.get("type", "output"),
            }
            response = await self._send(client, "GET", f"{endpoint.root_url}/view", endpoint, params=params)
            raise_for_status(response, f"{_LABEL} image download")
            images.append(
                image_from_bytes(
                    response.content,
                    provider=self.name,
                    index=index,
                    meta={"endpoint": endpoint.name, "filename": item["filename"], "seed": seed},
                )
            )
        return images

    async def _upload_image(self, client: httpx.AsyncClient, endpoint: EndpointConfig, data: bytes) -> str:
        url = f"{endpoint.root_url}/upload/image"
        files = {"image": (f"lumigen-{uuid.uuid4().hex}.png", data, "image/png")}
        response = await self._send(client, "POST", url, endpoint, files=files, data={"overwrite": "true"})
        raise_for_status(response, f"{_LABEL} image upload")
        body = json_body(response, _LABEL)
        name = str(body.get("name") or "")
        subfolder = str(body.get("subfolder") or "")
        if not name:
            raise ProviderError(f"{_LABEL} image upload returned no file name.")
        return f"{subfolder}/{name}" if subfolder else name

    # -- helpers -------------------------------------------------------------

    async def _send(
        self, client: httpx.AsyncClient, method: str, url: str, endpoint: EndpointConfig, **kwargs: Any
    ) -> httpx.Response:
        try:
            return await client.request(method, url, headers=self._headers(endpoint), **kwargs)
        except httpx.HTTPError as exc:
            raise ProviderError(f"{_LABEL} is not reachable at {endpoint.root_url}: {exc}") from exc

    @staticmethod
    def _headers(endpoint: EndpointConfig) -> dict[str, str]:
        key = (endpoint.api_key or "").strip()
        return {"Authorization": f"Bearer {key}"} if key else {}

    @staticmethod
    def _client(settings: Settings) -> httpx.AsyncClient:
        timeout = httpx.Timeout(
            settings.provider_comfyui_request_timeout_seconds,
            connect=settings.llm_models_connect_timeout_seconds,
        )
        return httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    @staticmethod
    def _combo_options(spec: Any) -> list[Any]:
        """Return COMBO options for both the legacy ``[[...], {...}]`` and the ``["COMBO", {"options": [...]}]`` shape."""
        if isinstance(spec, list) and spec:
            first = spec[0]
            if isinstance(first, list):
                return first
            if len(spec) > 1 and isinstance(spec[1], dict):
                return list(spec[1].get("options") or [])
        return []

    @staticmethod
    def _node_errors(response: httpx.Response) -> str:
        try:
            body = response.json()
        except Exception:
            return error_message(response)
        messages: list[str] = []
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict) and error.get("message"):
            messages.append(str(error["message"]))
        node_errors = body.get("node_errors") if isinstance(body, dict) else None
        if isinstance(node_errors, dict):
            for node_id, info in node_errors.items():
                for err in (info or {}).get("errors") or []:
                    detail = err.get("details") or err.get("message")
                    messages.append(f"node {node_id} ({info.get('class_type', '?')}): {detail}")
        return "; ".join(messages)[:500] or error_message(response)

    @staticmethod
    def _execution_error(status: dict[str, Any]) -> str:
        for message in status.get("messages") or []:
            if isinstance(message, list) and len(message) == 2 and message[0] == "execution_error":
                data = message[1] or {}
                return str(data.get("exception_message") or data.get("node_type") or "unknown error").strip()[:500]
        return "unknown error"
