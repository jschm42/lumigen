from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings
from app.services.enhancement_service import EnhancementService
from app.services.model_config_service import ModelConfigService

logger = logging.getLogger(__name__)

AGENTIC_SET_PLANNING_PROMPT = """You are an expert AI art director and prompt engineer.
Your task is to take a high-level creative instruction for a set/collection of images and decompose it into a cohesive set of individual, standalone image prompts.

CRITICAL RULES FOR IMAGE GENERATION:
1. EXACTLY ONE SINGLE STANDALONE OBJECT PER IMAGE:
   Each planned item corresponds to ONE separate image.
   NEVER generate a sprite sheet, grid, sheet of icons, collage, montage, multiple items, or collection in a single image.
   If the instruction asks for "RPG icons", "weapons", "character avatars", etc., you MUST break this down into concrete, individual solitary subjects (e.g. Item 1: "Healing Potion", Item 2: "Steel Broadsword", Item 3: "Dragon Shield", Item 4: "Magic Scroll", Item 5: "Mana Crystal").
   Every item's prompt MUST describe EXACTLY ONE solitary centered object isolated on its own.

2. AVOID PLURAL AND COLLECTION KEYWORDS:
   In each item's 'prompt_detail', NEVER use words like "icons", "set", "sheet", "sprite sheet", "collection", "grid", "collage", or "group".
   Instead, explicitly start each item prompt with phrases like:
   "A single isolated [subject], centered, solitary standalone object..."

3. COMMON STYLE ANCHOR:
   Formulate a cohesive 'common_style_anchor' to be appended to every item prompt.
   It MUST enforce visual consistency and solitary framing, for example:
   "single isolated standalone game asset icon, centered solitary subject, dark clean neutral studio background, no grid, no sheet, cohesive art style, masterpiece"

4. NEGATIVE PROMPT:
   Formulate an overarching 'negative_prompt' that strictly forbids grids and collections:
   "sheet, sprite sheet, icon sheet, grid, collage, multiple items, multiple objects, split frame, collection of items, borders with multiple icons, ui frame with multiple icons, blurry, distorted, low quality"

5. TARGET COUNT:
   {count_instruction}
   Do not plan fewer items than requested.

IMPORTANT: You MUST respond ONLY with a valid JSON object matching this structure:
{{
  "set_title": "Short title of the set, e.g. 'Fantasy RPG Inventory Icons'",
  "common_style_anchor": "Styling keywords, e.g. 'single isolated standalone game asset icon, centered solitary object, dark neutral background, no grid, no sheet, sharp digital painting'",
  "negative_prompt": "sheet, sprite sheet, icon sheet, grid, collage, multiple items, multiple objects, collection of icons, blurry, low quality",
  "items": [
    {{
      "title": "Item name, e.g. 'Health Potion'",
      "prompt_detail": "A single isolated round glass flask filled with glowing ruby red elixir, ornate brass stopper, solitary centered object"
    }}
  ]
}}
"""


AGENTIC_ANIMATION_PLANNING_PROMPT = """You are an expert animation director and prompt engineer.
Your task is to turn a high-level instruction into a frame-by-frame plan for a short looping GIF animation.
The frames are generated one after another by an image model that receives the first frame (keyframe) and the
previous frame as reference images, so every frame must show THE SAME subject in THE SAME scene.

CRITICAL RULES:
1. CONSISTENCY: The subject, its proportions, colours and clothing, the background, the camera position, the framing
   and the lighting stay identical in every frame. Describe them ONCE in 'subject_anchor', 'scene_anchor' and
   'style_anchor'. Never introduce new objects, cuts, zooms or camera moves unless explicitly requested.
2. FULL POSE PER FRAME: Each frame's 'pose' describes the COMPLETE body position of that frame in absolute terms
   (both legs, both arms, torso, head, held objects), e.g. "left leg forward with heel touching the ground, right
   leg behind on the toes, left arm swung back, right arm forward, torso upright". Never use relative wording such
   as "moves", "continues", "reverses" or "same as before". Adjacent frames must be clearly, visibly different;
   split the motion into evenly spaced key poses.
3. LOOP: {loop_instruction}
4. FRAME COUNT: {count_instruction}
5. TIMING: 'duration_ms' per frame is optional (default {default_frame_ms} ms). Use longer holds for key poses and
   shorter durations for fast motion. Never go below 20 ms.
6. SINGLE IMAGE: Every frame is ONE full image. NEVER describe sprite sheets, grids, panels, collages or
   multiple copies of the subject.
{background_instruction}

IMPORTANT: You MUST respond ONLY with a valid JSON object matching this structure:
{{
  "title": "Short title, e.g. 'Knight sword swing'",
  "subject_anchor": "pixel-art knight, silver armor, red cape, side view facing right",
  "scene_anchor": "flat dark-blue background, no props, fixed camera, character centered",
  "style_anchor": "16-bit pixel art, limited palette, crisp edges",
  "negative_prompt": "camera movement, zoom, different character, extra limbs, text, watermark, grid, sprite sheet",
  "loop": "loop",
  "default_frame_ms": {default_frame_ms},
  "key_color": "#00FF00",
  "frames": [
    {{"title": "Idle", "pose": "standing upright, feet shoulder-width apart, sword held low in the right hand, left arm relaxed", "duration_ms": 150}},
    {{"title": "Wind-up", "pose": "weight on the back leg, torso twisted right, both hands raising the sword over the right shoulder"}}
  ]
}}
"""

#: Allowed chroma-key colours for transparent animations (green default, magenta for green subjects).
ANIMATION_KEY_COLORS: tuple[str, ...] = ("#00FF00", "#FF00FF")


@dataclass
class AgenticItemPlan:
    """A single planned item within an agentic image set."""

    title: str
    prompt_detail: str


@dataclass
class AgenticPlan:
    """The complete multi-image plan generated by the LLM."""

    set_title: str
    common_style_anchor: str
    negative_prompt: str
    items: list[AgenticItemPlan] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the plan to a JSON-serializable dictionary."""
        return {
            "set_title": self.set_title,
            "common_style_anchor": self.common_style_anchor,
            "negative_prompt": self.negative_prompt,
            "items": [
                {"title": it.title, "prompt_detail": it.prompt_detail}
                for it in self.items
            ],
        }


@dataclass
class AgenticFramePlan:
    """A single planned frame of an agentic animation."""

    title: str
    pose: str
    duration_ms: int | None = None


@dataclass
class AgenticAnimationPlan:
    """The frame-by-frame animation plan generated by the LLM."""

    title: str
    subject_anchor: str
    scene_anchor: str
    style_anchor: str
    negative_prompt: str
    loop: str = "loop"
    default_frame_ms: int = 100
    key_color: str | None = None
    frames: list[AgenticFramePlan] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the plan to a JSON-serializable dictionary."""
        return {
            "kind": "animation",
            "title": self.title,
            "subject_anchor": self.subject_anchor,
            "scene_anchor": self.scene_anchor,
            "style_anchor": self.style_anchor,
            "negative_prompt": self.negative_prompt,
            "loop": self.loop,
            "default_frame_ms": self.default_frame_ms,
            "key_color": self.key_color,
            "frames": [
                {"title": fr.title, "pose": fr.pose, "duration_ms": fr.duration_ms}
                for fr in self.frames
            ],
        }

    def frame_prompt(self, index: int, emphasize_change: bool = False) -> str:
        """Return the generation prompt for frame *index*.

        Frame 0 is a full text-to-image description. Later frames redraw the
        character from the keyframe reference in the planned pose: the pose comes
        first and the reference is restricted to character identity, because
        edit models otherwise copy the reference image unchanged. With
        *emphasize_change* (retry after a static result) the instruction to
        change the pose is repeated more strongly.
        """
        frame = self.frames[index]
        if index == 0:
            return ", ".join(part for part in (self.subject_anchor, frame.pose, self.scene_anchor, self.style_anchor) if part)
        parts = [
            f"Frame {index + 1} of {len(self.frames)} of an animation. Redraw the character from the reference image "
            f"in this NEW POSE: {frame.pose}.",
            "The pose must be clearly and visibly different from the reference image.",
            "Use the reference image only for the character's identity, face, outfit, colours, proportions and art "
            "style, not for the pose.",
        ]
        if emphasize_change:
            parts.append(
                "IMPORTANT: a previous attempt returned the reference pose unchanged. Move the limbs, torso and head "
                "into the described position."
            )
        if self.subject_anchor:
            parts.append(f"Character: {self.subject_anchor}.")
        if self.scene_anchor:
            parts.append(f"Keep the same scene and camera framing: {self.scene_anchor}.")
        if self.style_anchor:
            parts.append(f"Style: {self.style_anchor}.")
        return " ".join(parts)


class AgenticService:
    """Service that orchestrates LLM-driven planning for agentic multi-image sets and animations."""

    def __init__(
        self,
        settings: Settings,
        model_config_service: ModelConfigService,
        enhancement_service: EnhancementService,
    ) -> None:
        """Initialize the agentic service with app settings and helper services."""
        self._settings = settings
        self._secrets = model_config_service
        self._enhancement_service = enhancement_service

    async def plan_set(
        self,
        instruction: str,
        min_images: int | None = None,
        max_images: int | None = None,
        target_model: str = "Unknown",
        target_provider: str = "Unknown",
        llm_model: str | None = None,
    ) -> AgenticPlan:
        """Decompose a high-level instruction into a cohesive multi-image generation plan.

        Calls the configured LLM to generate a structured JSON plan with a unified
        style anchor and individual item prompts. Min and max images are optional.
        """
        min_count = max(1, min(min_images, 16)) if min_images is not None else None
        max_count = max(min_count or 1, min(max_images, 16)) if max_images is not None else None

        if min_count is not None and max_count is not None:
            count_instruction = f"Plan between {min_count} and {max_count} items (inclusive, target: {max_count} items)."
            effective_min = min_count
            effective_max = max_count
            target_fallback = max_count
        elif min_count is not None:
            effective_min = min_count
            effective_max = max(min_count, 12)
            target_fallback = min_count
            count_instruction = f"Plan at least {min_count} items (maximum {effective_max})."
        elif max_count is not None:
            effective_min = min(2, max_count)
            effective_max = max_count
            target_fallback = max_count
            count_instruction = f"Plan {max_count} distinct items (or at least {effective_min})."
        else:
            effective_min = 2
            effective_max = 10
            target_fallback = 4
            count_instruction = "Decide on an ideal number of items for this collection based on the instruction (typically 3 to 8 items)."

        system_prompt = AGENTIC_SET_PLANNING_PROMPT.format(
            count_instruction=count_instruction,
        )

        user_content = (
            f"Instruction: {instruction}\n"
            f"Target Image Model: {target_model} ({target_provider})\n"
            f"Target items count guideline: {count_instruction}"
        )

        raw_content = await self._complete_json(system_prompt, user_content, llm_model)
        if raw_content is None:
            return self._fallback_plan(instruction, target_fallback)
        return self._parse_plan_json(raw_content, instruction, effective_min, effective_max)

    async def _complete_json(self, system_prompt: str, user_content: str, llm_model: str | None) -> str | None:
        """Send a system/user prompt pair to the configured planning LLM.

        Returns the raw message content, or ``None`` when no LLM is configured,
        the provider is unsupported, or the request fails (callers then use a
        fallback plan).
        """
        try:
            provider, model, api_key, _ = self._enhancement_service._resolve_llm(
                llm_model
            )
        except Exception as exc:
            logger.warning(
                "Could not resolve LLM for agentic planning (%s), using fallback.", exc
            )
            return None

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
        }

        if provider == "openai":
            url = self._settings.openai_base_url.rstrip("/") + "/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            if "gpt-4o" in model or "gpt-3.5-turbo-0125" in model:
                payload["response_format"] = {"type": "json_object"}
        elif provider == "openrouter":
            url = self._settings.openrouter_base_url.rstrip("/") + "/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Title": self._settings.app_name,
            }
        else:
            return None

        timeout = httpx.Timeout(
            self._settings.llm_enhancement_timeout_seconds,
            connect=self._settings.llm_enhancement_connect_timeout_seconds,
        )

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            except Exception as e:
                logger.error("Agentic planning LLM call failed: %s", e)
                return None

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return None
        return str(choices[0].get("message", {}).get("content", "") or "").strip()

    @staticmethod
    def _strip_code_fence(raw_content: str) -> str:
        """Remove a surrounding Markdown code fence from an LLM JSON answer."""
        clean = raw_content.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return clean.strip()

    def _parse_plan_json(
        self,
        raw_content: str,
        instruction: str,
        min_count: int,
        max_count: int,
    ) -> AgenticPlan:
        """Parse and sanitize the JSON plan returned by the LLM."""
        clean = self._strip_code_fence(raw_content)

        try:
            parsed = json.loads(clean)
        except json.JSONDecodeError:
            logger.warning("Failed to decode JSON from LLM: %s", raw_content[:200])
            return self._fallback_plan(instruction, min_count)

        set_title = str(parsed.get("set_title") or instruction[:40]).strip()
        style_anchor = str(parsed.get("common_style_anchor") or "").strip()
        neg_prompt = str(parsed.get("negative_prompt") or "").strip()

        raw_items = parsed.get("items")
        items: list[AgenticItemPlan] = []
        if isinstance(raw_items, list):
            for idx, it in enumerate(raw_items, start=1):
                if isinstance(it, dict):
                    title = str(it.get("title") or f"Item {idx}").strip()
                    detail = str(it.get("prompt_detail") or it.get("prompt") or "").strip()
                    if detail:
                        items.append(AgenticItemPlan(title=title, prompt_detail=detail))
                elif isinstance(it, str) and it.strip():
                    items.append(AgenticItemPlan(title=f"Item {idx}", prompt_detail=it.strip()))

        if len(items) < min_count:
            # Pad with fallback solitary items if count is too low
            diff = min_count - len(items)
            for d in range(diff):
                num = len(items) + 1
                items.append(
                    AgenticItemPlan(
                        title=f"{set_title} #{num}",
                        prompt_detail=f"A single isolated {set_title}, unique solitary item variation {num}, centered standalone object, dark background",
                    )
                )

        if len(items) > max_count:
            items = items[:max_count]

        return AgenticPlan(
            set_title=set_title,
            common_style_anchor=style_anchor,
            negative_prompt=neg_prompt,
            items=items,
        )

    def _fallback_plan(self, instruction: str, target_count: int) -> AgenticPlan:
        """Return a structured fallback plan if LLM planning is unavailable or fails."""
        clean_title = instruction.strip().replace("\n", " ")
        if len(clean_title) > 40:
            clean_title = clean_title[:40].rsplit(" ", 1)[0]
        set_title = clean_title or "Generated Set"

        # Sanitize instruction: strip plural/collection words that trigger grid generation in diffusion models
        sanitized = re.sub(
            r"\b(icons?|set of|collection of|sheet|sprite sheet|pack|grid|bundle)\b",
            "",
            instruction,
            flags=re.IGNORECASE,
        ).strip()
        sanitized = re.sub(r"\s+", " ", sanitized).strip(" ,.-") or "game asset"

        rpg_archetypes = [
            ("Health Potion", "A single isolated round glass flask filled with glowing ruby red healing elixir, ornate brass stopper, solitary centered object"),
            ("Iron Longsword", "A single isolated tempered steel longsword with leather-wrapped grip and ornate crossguard, solitary centered object"),
            ("Tower Shield", "A single isolated heavy metal tower shield with engraved heraldic crest, solitary centered object"),
            ("Magic Scroll", "A single isolated rolled parchment magic scroll tied with golden ribbon and glowing runes, solitary centered object"),
            ("Mana Crystal", "A single isolated floating radiant azure mana crystal pulsing with mystical energy, solitary centered object"),
            ("Ancient Spellbook", "A single isolated thick leather-bound grimoire with glowing arcane symbols, solitary centered object"),
            ("Knight Helm", "A single isolated steel knight helm with closed visor, solitary centered object"),
            ("Enchanted Ring", "A single isolated golden signet ring set with a faceted glowing emerald, solitary centered object"),
        ]

        lower_inst = instruction.lower()
        is_rpg_or_icon = any(k in lower_inst for k in ["rpg", "fantasy", "game", "icon", "inventory", "item", "loot"])

        items: list[AgenticItemPlan] = []
        for idx in range(1, target_count + 1):
            if is_rpg_or_icon and idx <= len(rpg_archetypes):
                _, detail = rpg_archetypes[idx - 1]
                items.append(
                    AgenticItemPlan(
                        title=f"Variation {idx}",
                        prompt_detail=detail,
                    )
                )
            else:
                items.append(
                    AgenticItemPlan(
                        title=f"Variation {idx}",
                        prompt_detail=f"A single isolated {sanitized}, distinct solitary variation {idx}, centered standalone object, clean studio background",
                    )
                )

        return AgenticPlan(
            set_title=set_title,
            common_style_anchor="single isolated standalone game asset icon, solitary centered object, clean dark neutral background, no grid, no sheet, sharp focus, cohesive visual style",
            negative_prompt="sheet, sprite sheet, icon sheet, grid, collage, multiple items, multiple objects, split frame, collection of icons, blurry, distorted, low quality",
            items=items,
        )

    async def plan_animation(
        self,
        instruction: str,
        min_frames: int | None = None,
        max_frames: int | None = None,
        frame_limit: int = 24,
        loop: str | None = None,
        default_frame_ms: int = 100,
        transparent: bool = False,
        target_model: str = "Unknown",
        target_provider: str = "Unknown",
        llm_model: str | None = None,
    ) -> AgenticAnimationPlan:
        """Plan a frame-by-frame animation from a high-level instruction.

        Args:
            instruction: The user's description of the animation.
            min_frames / max_frames: Optional user bounds, capped by *frame_limit*.
            frame_limit: Studio-wide maximum number of frames.
            loop: Forced loop mode (``loop``, ``pingpong``, ``once``) or ``None`` to let the LLM decide.
            default_frame_ms: Duration used for frames without an explicit duration.
            transparent: When True the plan uses a flat chroma-key background.

        Returns the parsed plan, or a generic fallback plan when the LLM is unavailable.
        """
        limit = max(2, int(frame_limit))
        lower = max(2, min(min_frames, limit)) if min_frames else None
        upper = max(lower or 2, min(max_frames, limit)) if max_frames else None
        effective_min = lower or 2
        effective_max = upper or min(limit, max(effective_min, 12))
        if lower and upper:
            count_instruction = f"Plan between {lower} and {upper} frames."
        elif lower:
            count_instruction = f"Plan at least {lower} frames (maximum {effective_max})."
        elif upper:
            count_instruction = f"Plan at most {upper} frames (at least {effective_min})."
        else:
            count_instruction = (
                f"Choose the frame count the motion needs, typically 6 to 12 frames (maximum {effective_max})."
            )

        if loop == "loop":
            loop_instruction = "The animation loops: the last frame must lead smoothly back into the first frame."
        elif loop == "pingpong":
            loop_instruction = "The animation plays forward and then backward (ping-pong): plan only the forward motion."
        elif loop == "once":
            loop_instruction = "The animation plays once: end on a clear final pose."
        else:
            loop_instruction = (
                "Decide 'loop' (cyclic motion), 'pingpong' (motion that reverses) or 'once'. "
                "For 'loop' the last frame must lead smoothly back into the first frame."
            )

        background_instruction = ""
        if transparent:
            background_instruction = (
                "7. TRANSPARENT BACKGROUND: The background is removed afterwards by chroma keying. 'scene_anchor' MUST "
                "describe a perfectly flat, uniform, solid key-colour background with no gradient, shadow, texture or "
                "floor. Use 'key_color' \"#00FF00\" (pure green), or \"#FF00FF\" (pure magenta) when the subject itself "
                "contains green. The subject must not contain the key colour."
            )

        system_prompt = AGENTIC_ANIMATION_PLANNING_PROMPT.format(
            loop_instruction=loop_instruction,
            count_instruction=count_instruction,
            default_frame_ms=default_frame_ms,
            background_instruction=background_instruction,
        )
        user_content = (
            f"Instruction: {instruction}\n"
            f"Target Image Model: {target_model} ({target_provider})\n"
            f"Frame count guideline: {count_instruction}"
        )

        raw_content = await self._complete_json(system_prompt, user_content, llm_model)
        if raw_content is None:
            plan = self._fallback_animation_plan(instruction, effective_min if lower else min(8, effective_max))
        else:
            plan = self._parse_animation_json(raw_content, instruction, effective_min, effective_max)
        return self._finalize_animation_plan(plan, loop, default_frame_ms, transparent)

    def _parse_animation_json(
        self,
        raw_content: str,
        instruction: str,
        min_count: int,
        max_count: int,
    ) -> AgenticAnimationPlan:
        """Parse and sanitize the JSON animation plan returned by the LLM."""
        try:
            parsed = json.loads(self._strip_code_fence(raw_content))
        except json.JSONDecodeError:
            logger.warning("Failed to decode animation JSON from LLM: %s", raw_content[:200])
            return self._fallback_animation_plan(instruction, min_count)
        if not isinstance(parsed, dict):
            return self._fallback_animation_plan(instruction, min_count)

        frames: list[AgenticFramePlan] = []
        raw_frames = parsed.get("frames")
        if isinstance(raw_frames, list):
            for idx, item in enumerate(raw_frames, start=1):
                if isinstance(item, dict):
                    pose = str(item.get("pose") or item.get("prompt_detail") or item.get("prompt") or "").strip()
                    if not pose:
                        continue
                    frames.append(
                        AgenticFramePlan(
                            title=str(item.get("title") or f"Frame {idx}").strip(),
                            pose=pose,
                            duration_ms=self._optional_int(item.get("duration_ms")),
                        )
                    )
                elif isinstance(item, str) and item.strip():
                    frames.append(AgenticFramePlan(title=f"Frame {idx}", pose=item.strip()))

        if len(frames) < min_count:
            # Pad by holding the last pose so the timing stays intact.
            base = frames[-1].pose if frames else f"{instruction.strip()}, subtle idle motion"
            while len(frames) < min_count:
                frames.append(AgenticFramePlan(title=f"Frame {len(frames) + 1}", pose=base))
        frames = frames[:max_count]

        return AgenticAnimationPlan(
            title=str(parsed.get("title") or instruction[:40]).strip(),
            subject_anchor=str(parsed.get("subject_anchor") or instruction).strip(),
            scene_anchor=str(parsed.get("scene_anchor") or "").strip(),
            style_anchor=str(parsed.get("style_anchor") or "").strip(),
            negative_prompt=str(parsed.get("negative_prompt") or "").strip(),
            loop=str(parsed.get("loop") or "loop").strip().lower(),
            default_frame_ms=self._optional_int(parsed.get("default_frame_ms")) or 100,
            key_color=str(parsed.get("key_color") or "").strip().upper() or None,
            frames=frames,
        )

    @staticmethod
    def _finalize_animation_plan(
        plan: AgenticAnimationPlan,
        loop: str | None,
        default_frame_ms: int,
        transparent: bool,
    ) -> AgenticAnimationPlan:
        """Apply user choices and safe defaults on top of an LLM or fallback plan."""
        if loop in {"loop", "pingpong", "once"}:
            plan.loop = loop
        elif plan.loop not in {"loop", "pingpong", "once"}:
            plan.loop = "loop"
        if not plan.default_frame_ms or plan.default_frame_ms < 20:
            plan.default_frame_ms = default_frame_ms
        for frame in plan.frames:
            if frame.duration_ms is not None:
                frame.duration_ms = max(20, min(frame.duration_ms, 10_000))
        if transparent:
            if plan.key_color not in ANIMATION_KEY_COLORS:
                plan.key_color = ANIMATION_KEY_COLORS[0]
            color_name = "pure green" if plan.key_color == "#00FF00" else "pure magenta"
            key_phrase = (
                f"perfectly flat uniform solid {color_name} ({plan.key_color}) background, "
                "no gradient, no shadow, no floor"
            )
            if plan.key_color.lower() not in plan.scene_anchor.lower():
                plan.scene_anchor = f"{plan.scene_anchor}, {key_phrase}".strip(", ")
        else:
            plan.key_color = None
        negative_extra = "sprite sheet, grid, multiple panels, collage, camera movement, different character"
        if "sprite sheet" not in plan.negative_prompt.lower():
            plan.negative_prompt = f"{plan.negative_prompt}, {negative_extra}".strip(", ")
        return plan

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        """Return *value* as int, or None when it is missing or not numeric."""
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _fallback_animation_plan(self, instruction: str, frame_count: int) -> AgenticAnimationPlan:
        """Return a generic idle-motion plan if LLM planning is unavailable or fails."""
        subject = instruction.strip().replace("\n", " ") or "a character"
        title = subject[:40].rsplit(" ", 1)[0] if len(subject) > 40 else subject
        count = max(2, frame_count)
        frames = [
            AgenticFramePlan(
                title=f"Frame {idx + 1}",
                pose=f"step {idx + 1} of {count} of a smooth, subtle motion: {subject}",
            )
            for idx in range(count)
        ]
        return AgenticAnimationPlan(
            title=title,
            subject_anchor=subject,
            scene_anchor="simple uncluttered background, fixed camera, subject centered",
            style_anchor="consistent art style, sharp focus",
            negative_prompt="blurry, distorted, low quality, text, watermark",
            loop="loop",
            default_frame_ms=100,
            frames=frames,
        )
