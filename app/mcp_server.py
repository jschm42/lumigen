"""MCP endpoint that lets external apps (for example TaleWeaver) generate images.

The endpoint speaks the MCP streamable HTTP transport at ``/mcp`` in stateless
JSON mode, so every call is a plain ``POST`` with a JSON-RPC body. It is
disabled until ``MCP_API_TOKEN`` is set; clients authenticate with
``Authorization: Bearer <token>``. The session login of the web UI does not
apply here.
"""
from __future__ import annotations

import hmac
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, ImageContent, TextContent
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.config import get_settings
from app.db import engine as db_engine
from app.services.external_generation_service import (
    ExternalGenerationError,
    ExternalGenerationService,
    ExternalImageRequest,
)

MCP_PATH = "/mcp"
ImageVariant = Literal["full", "thumbnail", "none"]

SERVER_INSTRUCTIONS = (
    "Lumigen generates images. Call list_models, list_profiles and list_categories "
    "to discover valid values, then call generate_image. Models, profiles and "
    "categories can be given by ID or name. Unknown category names are created. "
    "generate_image waits for the result by default; with wait=false it returns "
    "a job_id that you poll with get_generation."
)


def build_mcp_server(external_service: ExternalGenerationService) -> MCPServer:
    """Create the MCP server and register Lumigen's image tools on it."""
    settings = get_settings()
    server = MCPServer(
        name="lumigen",
        title="Lumigen",
        instructions=SERVER_INSTRUCTIONS,
        version=settings.app_version,
    )

    @server.tool(description="List the image models configured in Lumigen.")
    def list_models() -> dict[str, Any]:
        with db_engine.SessionLocal() as session:
            return {"models": external_service.list_models(session)}

    @server.tool(description="List the generation profiles (presets for model, size and categories).")
    def list_profiles() -> dict[str, Any]:
        with db_engine.SessionLocal() as session:
            return {"profiles": external_service.list_profiles(session)}

    @server.tool(description="List the gallery categories that generated images can be filed under.")
    def list_categories() -> dict[str, Any]:
        with db_engine.SessionLocal() as session:
            return {"categories": external_service.list_categories(session)}

    @server.tool(
        description=(
            "Generate images from a prompt. 'model' and 'profile' accept an ID or a name; "
            "'model' overrides the profile's model. 'categories' takes IDs or names and "
            "creates unknown names. With wait=true (default) the call returns when the "
            "images are done or timeout_seconds passed; 'include_images' controls whether "
            "the images are returned inline as full size, thumbnail or not at all."
        )
    )
    async def generate_image(
        prompt: str,
        model: str | int | None = None,
        profile: str | int | None = None,
        categories: list[str | int] | None = None,
        negative_prompt: str | None = None,
        aspect_ratio: str | None = None,
        resolution: str | None = None,
        n_images: int | None = None,
        seed: int | None = None,
        session_title: str | None = None,
        wait: bool = True,
        timeout_seconds: int | None = None,
        include_images: ImageVariant = "full",
    ) -> CallToolResult:
        request = ExternalImageRequest(
            prompt=prompt,
            model=model,
            profile=profile,
            categories=list(categories or []),
            negative_prompt=negative_prompt,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            n_images=n_images,
            seed=seed,
            session_title=session_title,
        )
        try:
            with db_engine.SessionLocal() as session:
                generation = external_service.create_job(session, request)
                generation_id = generation.id
        except ExternalGenerationError as exc:
            raise ToolError(str(exc)) from exc

        external_service.start_job(generation_id)
        if not wait:
            return _job_result(external_service, generation_id, "none")

        max_wait = get_settings().mcp_max_wait_seconds
        timeout = max_wait if timeout_seconds is None else max(1, min(timeout_seconds, max_wait))
        await external_service.wait_for_job(generation_id, timeout)
        return _job_result(external_service, generation_id, include_images)

    @server.tool(description="Return status, error and image IDs of a generation job.")
    def get_generation(job_id: int, include_images: ImageVariant = "none") -> CallToolResult:
        return _job_result(external_service, job_id, include_images)

    @server.tool(description="Return one generated image by its asset_id, as full size or thumbnail.")
    def get_image(asset_id: int, thumbnail: bool = False) -> CallToolResult:
        try:
            data, mime = external_service.read_asset_base64(asset_id, thumbnail=thumbnail)
        except ExternalGenerationError as exc:
            raise ToolError(str(exc)) from exc
        return CallToolResult(content=[ImageContent(type="image", data=data, mime_type=mime)])

    return server


def _job_result(
    external_service: ExternalGenerationService, generation_id: int, include_images: ImageVariant
) -> CallToolResult:
    """Build the tool result for a job: JSON summary plus optional inline images."""
    generation = external_service.load_job(generation_id)
    if generation is None:
        raise ToolError(f"Unknown job '{generation_id}'.")
    summary = external_service.describe_job(generation)
    content: list[TextContent | ImageContent] = [
        TextContent(type="text", text=json.dumps(summary, ensure_ascii=False))
    ]
    if include_images != "none" and generation.status == "succeeded":
        for image in summary["images"]:
            try:
                data, mime = external_service.read_asset_base64(
                    image["asset_id"], thumbnail=include_images == "thumbnail"
                )
            except ExternalGenerationError:
                continue
            content.append(ImageContent(type="image", data=data, mime_type=mime))
    return CallToolResult(
        content=content,
        structured_content=summary,
        is_error=generation.status in {"failed", "cancelled"},
    )


class McpEndpoint:
    """ASGI app for ``/mcp``: checks the bearer token, then hands over to the MCP SDK.

    The SDK session manager can only run once, so ``lifespan`` creates a fresh
    one for every application start.
    """

    def __init__(self, server: MCPServer) -> None:
        self.server = server
        self._manager: Any = None

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        """Run the MCP session manager for the lifetime of the FastAPI app."""
        # The bearer token already blocks DNS rebinding (browsers cannot add it),
        # and the SDK's host check would reject LAN and Docker hostnames.
        self.server.streamable_http_app(
            streamable_http_path=MCP_PATH,
            stateless_http=True,
            json_response=True,
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        )
        manager = self.server.session_manager
        async with manager.run():
            self._manager = manager
            try:
                yield
            finally:
                self._manager = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Authenticate the request and forward it to the MCP transport."""
        if scope["type"] != "http":
            return
        token = (get_settings().mcp_api_token or "").strip()
        if not token:
            response = JSONResponse({"detail": "MCP endpoint is disabled"}, status_code=404)
            await response(scope, receive, send)
            return
        if not _bearer_matches(Headers(scope=scope).get("authorization", ""), token):
            response = JSONResponse(
                {"detail": "Invalid or missing bearer token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return
        if self._manager is None:
            response = JSONResponse({"detail": "MCP endpoint is not ready"}, status_code=503)
            await response(scope, receive, send)
            return
        await self._manager.handle_request(scope, receive, send)


def _bearer_matches(header_value: str, expected: str) -> bool:
    """Return whether *header_value* is ``Bearer <expected>`` (constant-time compare)."""
    scheme, _, provided = header_value.partition(" ")
    if scheme.lower() != "bearer":
        return False
    return hmac.compare_digest(provided.strip().encode("utf-8"), expected.encode("utf-8"))
