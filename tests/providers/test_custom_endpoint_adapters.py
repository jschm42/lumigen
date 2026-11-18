"""Tests for the endpoint-based adapters: OpenAI-compatible APIs and ComfyUI."""
from __future__ import annotations

import base64
import json
from collections.abc import Callable
from io import BytesIO
from typing import Any

import httpx
import pytest
from PIL import Image

from app.config import Settings
from app.providers import comfyui_adapter as comfy_module
from app.providers import openai_compatible_adapter as oai_module
from app.providers.base import (
    EndpointConfig,
    ProviderConfigError,
    ProviderError,
    ProviderGenerationRequest,
    ProviderInputImage,
)
from app.providers.comfyui_adapter import ComfyUIAdapter
from app.providers.comfyui_workflow import (
    DEFAULT_WORKFLOW,
    WorkflowError,
    fill_workflow,
    parse_workflow,
)
from app.providers.openai_compatible_adapter import OpenAICompatibleAdapter


def _png(width: int = 16, height: int = 8) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(10, 120, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


def _settings() -> Settings:
    return Settings(provider_comfyui_poll_interval_seconds=0, provider_comfyui_generate_timeout_seconds=5)


def _request(endpoint: EndpointConfig | None, **overrides: Any) -> ProviderGenerationRequest:
    fields: dict[str, Any] = {
        "prompt": "a lighthouse",
        "width": 1000,
        "height": 600,
        "n_images": 1,
        "seed": 42,
        "output_format": "png",
        "model": "sdxl.safetensors",
        "endpoint": endpoint,
    }
    fields.update(overrides)
    return ProviderGenerationRequest(**fields)


class FakeClient:
    """Minimal async httpx client stand-in that routes calls to a handler."""

    calls: list[dict[str, Any]]

    def __init__(self, handler: Callable[[str, str, dict[str, Any]], httpx.Response]) -> None:
        self._handler = handler
        self.calls = []

    def __call__(self, *args: Any, **kwargs: Any) -> FakeClient:
        return self

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"method": method, "url": url, **kwargs})
        response = self._handler(method, url, kwargs)
        response.request = httpx.Request(method, url)
        return response

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)


def _install(monkeypatch: pytest.MonkeyPatch, module: Any, handler: Callable) -> FakeClient:
    client = FakeClient(handler)
    monkeypatch.setattr(module.httpx, "AsyncClient", client)
    return client


# --- OpenAI-compatible ------------------------------------------------------

OAI_ENDPOINT = EndpointConfig(id=1, name="LocalAI", kind="openai_compatible", base_url="http://localai:8080/v1/")


def test_openai_compatible_payload_defaults_and_options() -> None:
    adapter = OpenAICompatibleAdapter()
    request = _request(OAI_ENDPOINT, params={"quality": "high", "description": "internal"})

    payload = adapter.build_payload(request, {})
    assert payload == {
        "model": "sdxl.safetensors",
        "prompt": "a lighthouse",
        "n": 1,
        "size": "1000x600",
        "response_format": "b64_json",
        "quality": "high",
    }
    assert "output_format" not in payload

    custom = adapter.build_payload(request, {"response_format": "", "extra_params": {"steps": 8}})
    assert "response_format" not in custom
    assert custom["steps"] == 8


@pytest.mark.asyncio
async def test_openai_compatible_generate_decodes_b64_and_relative_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    png = _png(32, 24)

    def handler(method: str, url: str, kwargs: dict[str, Any]) -> httpx.Response:
        if url.endswith("/images/generations"):
            return httpx.Response(
                200,
                json={"data": [{"b64_json": base64.b64encode(png).decode()}, {"url": "/generated/b.png"}]},
            )
        if url == "http://localai:8080/generated/b.png":
            return httpx.Response(200, content=png, headers={"content-type": "image/png"})
        return httpx.Response(404, json={"error": "unexpected " + url})

    client = _install(monkeypatch, oai_module, handler)
    endpoint = EndpointConfig(id=1, name="LocalAI", kind="openai_compatible", base_url="http://localai:8080/v1")

    result = await OpenAICompatibleAdapter().generate(_request(endpoint, n_images=2), _settings())

    assert [(img.width, img.height, img.mime) for img in result.images] == [(32, 24, "image/png")] * 2
    assert result.raw_meta["endpoint"] == "LocalAI"
    post = client.calls[0]
    assert post["url"] == "http://localai:8080/v1/images/generations"
    assert "Authorization" not in post["headers"]  # no key configured -> no auth header


@pytest.mark.asyncio
async def test_openai_compatible_sends_bearer_key_and_maps_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(method: str, url: str, kwargs: dict[str, Any]) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "unknown model"}})

    client = _install(monkeypatch, oai_module, handler)
    endpoint = EndpointConfig(id=2, name="Gateway", kind="openai_compatible", base_url="https://gw/v1", api_key="sk-x")

    with pytest.raises(ProviderError, match="unknown model"):
        await OpenAICompatibleAdapter().generate(_request(endpoint), _settings())
    assert client.calls[0]["headers"]["Authorization"] == "Bearer sk-x"


@pytest.mark.asyncio
async def test_openai_compatible_edit_uses_multipart(monkeypatch: pytest.MonkeyPatch) -> None:
    png = _png()

    def handler(method: str, url: str, kwargs: dict[str, Any]) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png).decode()}]})

    client = _install(monkeypatch, oai_module, handler)
    request = _request(OAI_ENDPOINT, input_images=[ProviderInputImage(data=png, mime="image/png")])

    await OpenAICompatibleAdapter().generate(request, _settings())

    call = client.calls[0]
    assert call["url"].endswith("/images/edits")
    assert call["data"]["prompt"] == "a lighthouse"
    assert call["files"][0][0] == "image"


@pytest.mark.asyncio
async def test_openai_compatible_lists_models_and_requires_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        oai_module,
        lambda method, url, kwargs: httpx.Response(200, json={"data": [{"id": "flux-dev"}, {"id": "sdxl"}]}),
    )
    adapter = OpenAICompatibleAdapter()
    assert await adapter.list_endpoint_models(OAI_ENDPOINT, _settings()) == ["flux-dev", "sdxl"]

    with pytest.raises(ProviderConfigError):
        await adapter.generate(_request(None), _settings())


# --- ComfyUI workflow helpers ----------------------------------------------


def test_fill_workflow_replaces_typed_and_embedded_placeholders() -> None:
    workflow = {
        "1": {"class_type": "KSampler", "inputs": {"seed": "{{seed}}", "note": "seed={{seed}} / {{prompt}}"}},
    }
    filled = fill_workflow(workflow, {"seed": 7, "prompt": "cat"})
    assert filled["1"]["inputs"]["seed"] == 7
    assert filled["1"]["inputs"]["note"] == "seed=7 / cat"
    assert workflow["1"]["inputs"]["seed"] == "{{seed}}"  # original untouched


def test_parse_workflow_accepts_json_and_rejects_invalid_graphs() -> None:
    assert parse_workflow(json.dumps(DEFAULT_WORKFLOW)) == DEFAULT_WORKFLOW

    with pytest.raises(WorkflowError, match="API"):
        parse_workflow({"nodes": [], "links": []})
    with pytest.raises(WorkflowError, match="valid JSON"):
        parse_workflow("{not json")
    with pytest.raises(WorkflowError, match="prompt"):
        parse_workflow({"1": {"class_type": "SaveImage", "inputs": {}}})
    with pytest.raises(WorkflowError, match="Unknown placeholder"):
        parse_workflow({"1": {"class_type": "X", "inputs": {"text": "{{prompt}} {{steps}}"}}})


# --- ComfyUI adapter --------------------------------------------------------

COMFY_ENDPOINT = EndpointConfig(id=5, name="GPU box", kind="comfyui", base_url="http://gpu:8188")


def _comfy_handler(png: bytes, *, history_rounds: int = 1, fail: bool = False) -> Callable:
    state = {"history_calls": 0}

    def handler(method: str, url: str, kwargs: dict[str, Any]) -> httpx.Response:
        if url.endswith("/prompt"):
            return httpx.Response(200, json={"prompt_id": "p1", "number": 1})
        if url.endswith("/history/p1"):
            state["history_calls"] += 1
            if state["history_calls"] <= history_rounds:
                return httpx.Response(200, json={})
            if fail:
                status = {
                    "status_str": "error",
                    "completed": False,
                    "messages": [["execution_error", {"exception_message": "CUDA out of memory"}]],
                }
                return httpx.Response(200, json={"p1": {"status": status, "outputs": {}}})
            outputs = {
                "9": {"images": [{"filename": "lumigen_0001.png", "subfolder": "", "type": "output"}]},
                "12": {"images": [{"filename": "preview.png", "subfolder": "", "type": "temp"}]},
            }
            return httpx.Response(
                200, json={"p1": {"status": {"status_str": "success", "completed": True}, "outputs": outputs}}
            )
        if url.endswith("/view"):
            return httpx.Response(200, content=png, headers={"content-type": "image/png"})
        if url.endswith("/upload/image"):
            return httpx.Response(200, json={"name": "lumigen-in.png", "subfolder": "", "type": "input"})
        return httpx.Response(404, json={"error": "unexpected " + url})

    return handler


@pytest.mark.asyncio
async def test_comfyui_default_workflow_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    png = _png(64, 48)
    client = _install(monkeypatch, comfy_module, _comfy_handler(png, history_rounds=2))

    result = await ComfyUIAdapter().generate(_request(COMFY_ENDPOINT, negative_prompt="blurry"), _settings())

    graph = client.calls[0]["json"]["prompt"]
    assert graph["4"]["inputs"]["ckpt_name"] == "sdxl.safetensors"
    assert graph["3"]["inputs"]["seed"] == 42
    assert graph["5"]["inputs"] == {"width": 1000, "height": 600, "batch_size": 1}
    assert graph["7"]["inputs"]["text"] == "blurry"
    # Only the SaveImage output is downloaded, not the temp preview.
    view_calls = [c for c in client.calls if c["url"].endswith("/view")]
    assert [c["params"]["filename"] for c in view_calls] == ["lumigen_0001.png"]
    assert len(result.images) == 1 and result.images[0].width == 64
    assert result.raw_meta["seed"] == 42 and result.raw_meta["custom_workflow"] is False


@pytest.mark.asyncio
async def test_comfyui_custom_workflow_uploads_input_image(monkeypatch: pytest.MonkeyPatch) -> None:
    png = _png()
    client = _install(monkeypatch, comfy_module, _comfy_handler(png))
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "{{input_image}}"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{prompt}}"}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }
    endpoint = EndpointConfig(id=5, name="GPU box", kind="comfyui", base_url="http://gpu:8188", options={"workflow": workflow})
    request = _request(endpoint, seed=None, input_images=[ProviderInputImage(data=png, mime="image/png")])

    result = await ComfyUIAdapter().generate(request, _settings())

    assert client.calls[0]["url"].endswith("/upload/image")
    graph = next(c for c in client.calls if c["url"].endswith("/prompt"))["json"]["prompt"]
    assert graph["1"]["inputs"]["image"] == "lumigen-in.png"
    assert isinstance(result.raw_meta["seed"], int)  # random seed generated when none given
    assert result.raw_meta["custom_workflow"] is True


@pytest.mark.asyncio
async def test_comfyui_reports_execution_and_validation_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, comfy_module, _comfy_handler(_png(), fail=True))
    with pytest.raises(ProviderError, match="CUDA out of memory"):
        await ComfyUIAdapter().generate(_request(COMFY_ENDPOINT), _settings())

    def rejecting(method: str, url: str, kwargs: dict[str, Any]) -> httpx.Response:
        body = {
            "error": {"message": "Prompt outputs failed validation"},
            "node_errors": {"4": {"class_type": "CheckpointLoaderSimple", "errors": [{"details": "ckpt not found"}]}},
        }
        return httpx.Response(400, json=body)

    _install(monkeypatch, comfy_module, rejecting)
    with pytest.raises(ProviderError, match="ckpt not found"):
        await ComfyUIAdapter().generate(_request(COMFY_ENDPOINT), _settings())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "spec",
    [
        [["a.safetensors", "b.ckpt"], {}],
        ["COMBO", {"options": ["a.safetensors", "b.ckpt"]}],
    ],
)
async def test_comfyui_lists_checkpoints_in_both_formats(monkeypatch: pytest.MonkeyPatch, spec: list) -> None:
    body = {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": spec}}}}
    _install(monkeypatch, comfy_module, lambda method, url, kwargs: httpx.Response(200, json=body))
    models = await ComfyUIAdapter().list_endpoint_models(COMFY_ENDPOINT, _settings())
    assert models == ["a.safetensors", "b.ckpt"]


@pytest.mark.asyncio
async def test_comfyui_unreachable_server_raises_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(method: str, url: str, kwargs: dict[str, Any]) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _install(monkeypatch, comfy_module, handler)
    with pytest.raises(ProviderError, match="not reachable"):
        await ComfyUIAdapter().list_endpoint_models(COMFY_ENDPOINT, _settings())
