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


@pytest.mark.asyncio
async def test_agentic_plan_optional_min_max(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    llm_payload = {
        "set_title": "Sci-Fi Badges",
        "common_style_anchor": "cyberpunk badge, neon glow",
        "negative_prompt": "blurry",
        "items": [
            {"title": "Badge 1", "prompt_detail": "detail 1"},
            {"title": "Badge 2", "prompt_detail": "detail 2"},
            {"title": "Badge 3", "prompt_detail": "detail 3"},
        ],
    }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, **kwargs):  # type: ignore[no-untyped-def]
            calls.append({"url": url, "headers": headers or {}, "json": kwargs.get("json")})
            return _json_response(
                "POST",
                url,
                200,
                {
                    "choices": [
                        {"message": {"content": json.dumps(llm_payload)}}
                    ]
                },
            )

    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    secrets = SimpleNamespace(
        get_default_api_key=lambda provider: "test-openai-key",
        decrypt_api_key=lambda tok: tok,
    )
    enhancement = EnhancementService(Settings(), secrets)
    service = AgenticService(Settings(), secrets, enhancement)

    # Calling with min_images=None, max_images=None
    plan = await service.plan_set(
        instruction="design cool sci-fi badges",
        min_images=None,
        max_images=None,
    )

    assert isinstance(plan, AgenticPlan)
    assert plan.set_title == "Sci-Fi Badges"
    assert len(plan.items) == 3
    # Verify the prompt sent to LLM contains "ideal count" instruction
    prompt_sent = calls[0]["json"]["messages"][1]["content"]
    assert "Decide on an ideal number" in prompt_sent



def _animation_service(monkeypatch: pytest.MonkeyPatch, content: str | None) -> tuple[AgenticService, list]:
    """Return an AgenticService whose LLM answers with *content* (None = network error)."""
    calls: list = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, headers=None, json=None):  # type: ignore[no-untyped-def]
            calls.append(json)
            if content is None:
                raise httpx.ConnectError("Network unreachable")
            return _json_response("POST", url, 200, {"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)
    secrets = SimpleNamespace(get_default_api_key=lambda provider: "key", decrypt_api_key=lambda tok: tok)
    return AgenticService(Settings(), secrets, EnhancementService(Settings(), secrets)), calls


@pytest.mark.asyncio
async def test_plan_animation_parses_frames_and_applies_user_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "title": "Knight swing",
        "subject_anchor": "pixel knight",
        "scene_anchor": "flat blue background",
        "style_anchor": "16-bit pixel art",
        "negative_prompt": "blurry",
        "loop": "once",
        "frames": [
            {"title": "Idle", "pose": "sword lowered", "duration_ms": 5},
            {"title": "Wind-up", "pose": "sword raised"},
            {"title": "Empty", "pose": ""},
            "sword swung forward",
        ],
    }
    service, calls = _animation_service(monkeypatch, "```json\n" + json.dumps(payload) + "\n```")

    plan = await service.plan_animation("knight swings a sword", loop="pingpong", default_frame_ms=90)

    assert [f.title for f in plan.frames] == ["Idle", "Wind-up", "Frame 4"]
    assert plan.frames[0].duration_ms == 20  # clamped
    assert plan.loop == "pingpong"  # user choice wins
    assert plan.key_color is None
    assert "sprite sheet" in plan.negative_prompt
    assert "ping-pong" in calls[0]["messages"][0]["content"]
    assert plan.frame_prompt(0).startswith("pixel knight, sword lowered")
    second = plan.frame_prompt(1)
    assert second.startswith("Frame 2 of 3 of an animation.")
    assert "NEW POSE: sword raised" in second
    assert "only for the character's identity" in second
    assert "IMPORTANT" not in second
    assert "IMPORTANT" in plan.frame_prompt(1, emphasize_change=True)
    assert plan.to_dict()["kind"] == "animation"


@pytest.mark.asyncio
async def test_plan_animation_pads_and_caps_frame_count(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"title": "Blink", "frames": [{"pose": f"step {i}"} for i in range(30)]}
    service, _ = _animation_service(monkeypatch, json.dumps(payload))
    plan = await service.plan_animation("blinking eye", max_frames=40, frame_limit=10)
    assert len(plan.frames) == 10

    short = {"title": "Blink", "frames": [{"pose": "open"}]}
    service, _ = _animation_service(monkeypatch, json.dumps(short))
    plan = await service.plan_animation("blinking eye", min_frames=4)
    assert len(plan.frames) == 4
    assert plan.frames[-1].pose == "open"


@pytest.mark.asyncio
async def test_plan_animation_transparent_enforces_key_colour(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"title": "Frog", "scene_anchor": "white background", "key_color": "#123456",
               "frames": [{"pose": "a"}, {"pose": "b"}]}
    service, calls = _animation_service(monkeypatch, json.dumps(payload))
    plan = await service.plan_animation("green frog hopping", transparent=True)
    assert plan.key_color == "#00FF00"
    assert "#00FF00" in plan.scene_anchor
    assert "TRANSPARENT BACKGROUND" in calls[0]["messages"][0]["content"]

    payload["key_color"] = "#ff00ff"
    service, _ = _animation_service(monkeypatch, json.dumps(payload))
    plan = await service.plan_animation("green frog hopping", transparent=True)
    assert plan.key_color == "#FF00FF"
    assert "magenta" in plan.scene_anchor


@pytest.mark.asyncio
async def test_plan_animation_falls_back_without_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _ = _animation_service(monkeypatch, None)
    plan = await service.plan_animation("a candle flickering", min_frames=5, loop="loop")
    assert len(plan.frames) == 5
    assert plan.subject_anchor == "a candle flickering"
    assert plan.loop == "loop"

    service, _ = _animation_service(monkeypatch, "not json")
    plan = await service.plan_animation("a candle flickering")
    assert len(plan.frames) >= 2


def test_animation_plan_roundtrip_and_keyframe_edit_prompt() -> None:
    from app.services.agentic_service import AgenticAnimationPlan, AgenticFramePlan

    plan = AgenticAnimationPlan(
        title="Walk",
        subject_anchor="ranger",
        scene_anchor="flat green background",
        style_anchor="pixel art",
        negative_prompt="blurry",
        loop="pingpong",
        default_frame_ms=90,
        key_color="#00FF00",
        frames=[AgenticFramePlan("Contact", "left leg forward", 120), AgenticFramePlan("Pass", "legs together")],
    )
    restored = AgenticAnimationPlan.from_dict(plan.to_dict())
    assert restored == plan
    # The keyframe is a text-to-image prompt, but regenerating it from another frame needs the edit prompt.
    assert plan.frame_prompt(0).startswith("ranger, left leg forward")
    assert plan.frame_prompt(0, as_edit=True).startswith("Frame 1 of 2 of an animation.")


@pytest.mark.asyncio
async def test_plan_animation_extracts_json_wrapped_in_think_or_prose(monkeypatch: pytest.MonkeyPatch) -> None:
    wrapped = (
        "<think>Let me plan 2 distinct poses.</think>\n"
        "Here is the animation plan:\n"
        '{"title": "Spin", "subject_anchor": "gold coin", "frames": [{"title": "Front", "pose": "front face"}, '
        '{"title": "Edge", "pose": "thin side edge"}]}\n'
        "Hope this helps!"
    )
    service, calls = _animation_service(monkeypatch, wrapped)
    plan = await service.plan_animation("spinning coin", loop="loop")
    assert plan.title == "Spin"
    assert [f.title for f in plan.frames] == ["Front", "Edge"]
    assert "Do NOT repeat frame 1" in calls[0]["messages"][0]["content"]
