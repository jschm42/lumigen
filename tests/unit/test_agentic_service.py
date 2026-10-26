from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.services.agentic_service import AgenticPlan, AgenticService
from app.services.enhancement_service import EnhancementService


def _json_response(method: str, url: str, status: int, payload: dict[str, Any]) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(status, json=payload, request=request)


@pytest.mark.asyncio
async def test_agentic_plan_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    llm_payload = {
        "set_title": "RPG Inventory Icons",
        "common_style_anchor": "clean vector game icon, dark fantasy, solid black background",
        "negative_prompt": "blurry, photo, watermark",
        "items": [
            {"title": "Health Potion", "prompt_detail": "round flask with glowing red elixir"},
            {"title": "Mana Potion", "prompt_detail": "tall vial with blue bubbling liquid"},
            {"title": "Iron Sword", "prompt_detail": "sharp steel broadsword with leather grip"},
            {"title": "Magic Scroll", "prompt_detail": "ancient parchment tied with gold ribbon"},
        ],
    }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            calls.append({"url": url, "headers": headers or {}, "json": json})
            return _json_response(
                "POST",
                url,
                200,
                {
                    "choices": [
                        {"message": {"content": json_dumps(llm_payload)}}
                    ]
                },
            )

    def json_dumps(data: Any) -> str:
        return json.dumps(data)

    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    secrets = SimpleNamespace(
        get_default_api_key=lambda provider: "test-openai-key",
        decrypt_api_key=lambda tok: tok,
    )
    enhancement = EnhancementService(Settings(), secrets)
    service = AgenticService(Settings(), secrets, enhancement)

    plan = await service.plan_set(
        instruction="design a set of 4 RPG icons",
        min_images=4,
        max_images=6,
        target_model="flux-schnell",
        target_provider="fal",
    )

    assert isinstance(plan, AgenticPlan)
    assert plan.set_title == "RPG Inventory Icons"
    assert len(plan.items) == 4
    assert plan.items[0].title == "Health Potion"
    assert "glowing red elixir" in plan.items[0].prompt_detail
    assert len(calls) == 1
    assert "RPG icons" in calls[0]["json"]["messages"][1]["content"]


@pytest.mark.asyncio
async def test_agentic_plan_fallback_on_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            raise httpx.ConnectError("Network unreachable")

    monkeypatch.setattr("httpx.AsyncClient", FailingAsyncClient)

    secrets = SimpleNamespace(
        get_default_api_key=lambda provider: "key",
        decrypt_api_key=lambda tok: tok,
    )
    enhancement = EnhancementService(Settings(), secrets)
    service = AgenticService(Settings(), secrets, enhancement)

    plan = await service.plan_set(
        instruction="design fantasy icons",
        min_images=4,
        max_images=6,
    )

    assert isinstance(plan, AgenticPlan)
    assert len(plan.items) >= 4
    assert plan.set_title != ""
    assert plan.items[0].title == "Variation 1"
