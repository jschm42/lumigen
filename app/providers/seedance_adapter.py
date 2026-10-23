from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import httpx

from app.config import Settings
from app.providers.base import (
    ProviderAdapter,
    ProviderConfigError,
    ProviderError,
    ProviderGenerationRequest,
    ProviderGenerationResult,
    ProviderImage,
    ProviderRateLimitError,
    ProviderServiceUnavailableError,
)

_KNOWN_MODELS = [
    "dreamina-seedance-2-5-260628",
    "seedance-2-0-260128",
    "seedance-2-0-fast-260128",
    "seedance-2-0-mini-260615",
    "seedance-1-5-pro-251215",
    "seedance-1-0-pro-fast-251015",
    "seedance-1-0-pro-250528",
]

_RATIOS = {"16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"}
_RESOLUTIONS = {"480p", "720p", "1080p"}

# Resolution & Aspect Ratio -> (width, height)
_DIMENSIONS_MAP: dict[tuple[str, str], tuple[int, int]] = {
    ("720p", "16:9"): (1280, 720),
    ("720p", "9:16"): (720, 1280),
    ("720p", "1:1"): (720, 720),
    ("720p", "4:3"): (960, 720),
    ("720p", "3:4"): (720, 960),
    ("720p", "21:9"): (1680, 720),
    ("1080p", "16:9"): (1920, 1080),
    ("1080p", "9:16"): (1080, 1920),
    ("1080p", "1:1"): (1080, 1080),
    ("1080p", "4:3"): (1440, 1080),
    ("1080p", "3:4"): (1080, 1440),
    ("1080p", "21:9"): (2520, 1080),
    ("480p", "16:9"): (854, 480),
    ("480p", "9:16"): (480, 854),
    ("480p", "1:1"): (480, 480),
    ("480p", "4:3"): (640, 480),
    ("480p", "3:4"): (480, 640),
}


class SeedanceAdapter(ProviderAdapter):
    """Adapter for ByteDance Seedance Video Generation API on BytePlus ModelArk.

    Endpoint: POST /contents/generations/tasks
    Query:    GET  /contents/generations/tasks/{id}
    """

    name = "seedance"
    display_name = "ByteDance Seedance (BytePlus)"
    homepage_url = "https://www.byteplus.com/en/product/seedance"
    MAX_POLL_ATTEMPTS = 120
    POLL_INTERVAL = 3.0  # seconds
    _logger = logging.getLogger(__name__)

    async def list_models(self, settings: Settings) -> list[str]:
        """Return the known Seedance video model IDs."""
        _ = settings
        return list(_KNOWN_MODELS)

    def _resolve_ratio(self, request: ProviderGenerationRequest) -> str:
        """Map aspect ratio selection to Seedance ratio format."""
        ratio = (request.aspect_ratio or "").strip()
        if not ratio and isinstance(request.params, dict):
            ratio = str(request.params.get("ratio") or request.params.get("aspect_ratio") or "").strip()
        if ratio in _RATIOS:
            return ratio
        if request.width and request.height:
            w, h = request.width, request.height
            if w > h * 1.5:
                return "16:9"
            if h > w * 1.5:
                return "9:16"
            if w > h:
                return "4:3"
            if h > w:
                return "3:4"
            return "1:1"
        return "16:9"

    def _resolve_resolution(self, request: ProviderGenerationRequest) -> str:
        res = ""
        if isinstance(request.params, dict):
            res = str(request.params.get("resolution") or "").strip().lower()
        if res in _RESOLUTIONS:
            return res
        return "720p"

    def _build_payload(self, request: ProviderGenerationRequest) -> dict[str, Any]:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": request.prompt}
        ]
        if request.input_images:
            img = request.input_images[0]
            b64 = base64.b64encode(img.data).decode("ascii")
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img.mime};base64,{b64}"
                }
            })

        ratio = self._resolve_ratio(request)
        resolution = self._resolve_resolution(request)

        duration = 5
        if isinstance(request.params, dict) and "duration" in request.params:
            try:
                duration = int(request.params["duration"])
            except (ValueError, TypeError):
                duration = 5

        generate_audio = False
        if isinstance(request.params, dict) and "generate_audio" in request.params:
            generate_audio = bool(request.params["generate_audio"])

        watermark = False
        if isinstance(request.params, dict) and "watermark" in request.params:
            watermark = bool(request.params["watermark"])

        payload: dict[str, Any] = {
            "model": request.model,
            "content": content,
            "ratio": ratio,
            "resolution": resolution,
            "duration": duration,
            "generate_audio": generate_audio,
            "watermark": watermark,
        }
        if request.seed is not None:
            payload["seed"] = request.seed

        return payload

    async def generate(
        self, request: ProviderGenerationRequest, settings: Settings
    ) -> ProviderGenerationResult:
        api_key = (
            request.api_key
            or getattr(settings, "seedance_api_key", None)
            or settings.byteplus_api_key
        )
        if not api_key:
            raise ProviderConfigError(
                "Seedance adapter requires SEEDANCE_API_KEY or BYTEPLUS_API_KEY in .env or custom API key."
            )

        base_url = (
            getattr(settings, "seedance_base_url", None)
            or settings.byteplus_base_url
        ).rstrip("/")
        tasks_url = f"{base_url}/contents/generations/tasks"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_payload(request)
        self._log_request("POST", tasks_url, headers, payload)

        timeout = httpx.Timeout(
            getattr(settings, "provider_seedance_generate_timeout_seconds", 300.0),
            connect=getattr(settings, "provider_seedance_generate_connect_timeout_seconds", 15.0),
        )

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(tasks_url, headers=headers, json=payload)
            if response.status_code == 429:
                raise ProviderRateLimitError("Seedance rate limit reached (429).")
            if response.status_code == 503:
                raise ProviderServiceUnavailableError("Seedance service unavailable (503).")
            if response.status_code >= 500:
                raise ProviderServiceUnavailableError(f"Seedance upstream error ({response.status_code}).")
            if response.status_code >= 400:
                msg = self._extract_error_message(response)
                raise ProviderError(f"Seedance request failed ({response.status_code}): {msg}")

            try:
                submit_result = response.json()
            except Exception as exc:
                raise ProviderError("Seedance returned a non-JSON response.") from exc

            task_id = submit_result.get("id")
            if not task_id:
                raise ProviderError(f"Seedance did not return a task id: {submit_result}")

            images = await self._poll_for_result(
                client=client,
                base_url=base_url,
                task_id=task_id,
                headers=headers,
                request=request,
            )

        return ProviderGenerationResult(
            images=images,
            raw_meta={
                "provider": self.name,
                "task_id": task_id,
                "model": request.model,
                "count": len(images),
                "media_type": "video",
            },
        )

    async def _poll_for_result(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        task_id: str,
        headers: dict[str, str],
        request: ProviderGenerationRequest,
    ) -> list[ProviderImage]:
        status_url = f"{base_url}/contents/generations/tasks/{task_id}"

        for attempt in range(self.MAX_POLL_ATTEMPTS):
            await asyncio.sleep(self.POLL_INTERVAL)
            response = await client.get(status_url, headers=headers)

            if response.status_code >= 500:
                if attempt < self.MAX_POLL_ATTEMPTS - 1:
                    continue
                raise ProviderServiceUnavailableError(f"Seedance polling failed ({response.status_code}).")
            if response.status_code >= 400:
                msg = self._extract_error_message(response)
                raise ProviderError(f"Seedance polling failed ({response.status_code}): {msg}")

            try:
                status_body = response.json()
            except Exception as exc:
                raise ProviderError("Seedance polling returned non-JSON.") from exc

            status = (status_body.get("status") or "").lower()

            if status in ("succeeded", "completed"):
                return await self._extract_video(status_body, request, client)

            if status == "failed":
                err = status_body.get("error") or {}
                msg = err.get("message") if isinstance(err, dict) else str(err)
                raise ProviderError(f"Seedance generation failed: {msg or 'Unknown error'}")

            if status == "cancelled":
                raise ProviderError("Seedance generation task was cancelled.")

            if status in ("queued", "running", "processing", "pending"):
                continue

            if attempt >= self.MAX_POLL_ATTEMPTS - 1:
                raise ProviderError(f"Seedance polling timed out. Last status: {status}")

        raise ProviderError(f"Seedance polling timed out after {self.MAX_POLL_ATTEMPTS} attempts.")

    async def _extract_video(
        self,
        result: dict[str, Any],
        request: ProviderGenerationRequest,
        client: httpx.AsyncClient,
    ) -> list[ProviderImage]:
        content = result.get("content") or {}
        video_url = ""
        if isinstance(content, dict):
            video_url = content.get("video_url") or ""
        elif isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                video_url = first.get("video_url") or ""

        if not video_url:
            raise ProviderError(f"Seedance result content has no video_url: {result}")

        try:
            resp = await client.get(video_url)
            resp.raise_for_status()
            video_bytes = resp.content
        except Exception as exc:
            raise ProviderError(f"Failed to download Seedance video from {video_url}: {exc}") from exc

        ratio = self._resolve_ratio(request)
        resolution = self._resolve_resolution(request)
        width, height = _DIMENSIONS_MAP.get((resolution, ratio), (1280, 720))

        return [
            ProviderImage(
                data=video_bytes,
                mime="video/mp4",
                width=width,
                height=height,
                meta={
                    "provider": self.name,
                    "model": request.model,
                    "media_type": "video",
                    "video_url": video_url,
                    "resolution": resolution,
                    "ratio": ratio,
                },
            )
        ]

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            body = response.json()
            if isinstance(body, dict):
                error_obj = body.get("error")
                if isinstance(error_obj, dict) and "message" in error_obj:
                    return str(error_obj["message"])
                if isinstance(error_obj, str):
                    return error_obj
                if "message" in body:
                    return str(body["message"])
            return response.text[:200]
        except Exception:
            return response.text[:200]
