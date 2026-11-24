# Concept: Agentic GIF Animation

Status: phase 1 implemented (decisions in §12) · Target: v0.7.x · Owner: TBD

## 1. Goal

Let a user describe an animation in plain language ("a pixel-art knight swinging a sword, 8 frames, loop") and have
Agentic Mode plan the frames, generate them, and assemble an animated GIF that lands in the gallery as a normal asset.
The individual frames stay available as a gallery stack so the user can inspect, regenerate or reorder them.

## 2. Current state (what we build on)

| Building block | Where | Reuse for animation |
|---|---|---|
| LLM planning (JSON plan: title, style anchor, negative prompt, items) | `app/services/agentic_service.py` → `AgenticService.plan_set()` | Add a second planner `plan_animation()` with its own prompt and dataclasses. |
| Agentic job loop (planning → per-item generation → assets with `stack_id`/`stack_order`) | `GenerationService._execute_agentic_generation_job()` | Frame loop is structurally identical; add the assembly step at the end. |
| Progress fields in `request_snapshot_json` (`agentic_step`, `total_planned`, `current_item_index`) | same, plus `app/api/generation.py` serializer | Add steps `assembling` and expose `agentic_kind`. |
| Image-to-image input (`ProviderGenerationRequest.input_images`) | `app/providers/base.py`, adapters | Feed the previous frame / keyframe as reference for consistency. |
| Video models + `ffmpeg` lookup | `ThumbnailService._find_ffmpeg()`, video adapters (Seedance, FAL …) | Alternative route: video → GIF conversion. |
| Pillow (runtime dependency) | `pyproject.toml` | GIF encoding without new dependencies. |
| GIF already accepted as asset extension / MIME | `app/main.py` `_guess_extension()` | Gallery can store GIFs; thumbnail + viewer need a check (see §7). |

**Gap:** there is no capability flag telling us whether a model accepts image input (edit / img2img). The current
capability model only distinguishes `image` vs `video` (`ProviderAdapter.media_type_for_model`).

## 3. The core problem: frame consistency

Independent text-to-image calls per frame produce flicker: the character, palette, background and camera change from
frame to frame. The current set planner even pushes in the opposite direction ("distinct variation"). The concept
therefore defines three generation strategies, picked automatically from the selected model's capabilities and
overridable by the user.

### Strategy A — Keyframe chain (default for edit-capable image models)

1. Generate **frame 0** (the keyframe) via text-to-image (with the user's seed if one is set; several models reject the parameter, so none is invented).
2. For every following frame, send an edit request with `input_images = [keyframe, previous_frame]` and a prompt that
   describes only the *delta* ("same character, same background, same camera; the sword is now raised above the head").
3. Keep seed, size, aspect ratio and style anchor constant.

Works well with Gemini image / Nano Banana (FAL, OpenRouter, Google), OpenAI `gpt-image` edit, FLUX Kontext (BFL/FAL),
ComfyUI img2img workflows. Cost: one image call per frame, strictly sequential.

### Strategy B — Sprite sheet + slice (pixel art, icons, short loops)

1. Planner produces one prompt for a single sheet: "N×M grid of animation frames, identical character, evenly spaced
   cells, plain background".
2. One generation call; the result is sliced into cells with Pillow (fixed grid from the plan, optional auto-trim).
3. Frames are stored as a stack, then assembled.

Cheapest and most consistent within the sheet, but resolution per frame is low and models do not always respect the
grid. Offer it as an explicit option ("Sprite sheet"), with a validation step (cell count / empty-cell detection) and
a fallback to Strategy A.

### Strategy C — Video model → GIF (realistic motion)

If the selected model is a video model, skip frame planning: the LLM writes one motion prompt (+ optional first-frame
image), the video adapter generates an MP4, and `ffmpeg` converts it to GIF
(`fps=N,scale=W:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse`). Optional frame extraction into a stack
for editing. Best motion quality, highest cost, requires `ffmpeg`.

### No fallback — reject unsupported models

**Decision:** there is no text-to-image-per-frame fallback. If the selected model is neither a video model nor known to
accept image input, the request is rejected up front:

- **API:** `/api/generate` returns `422` with `"The selected model does not support image input, which is required for
  animations. Choose an edit-capable or video model."` — before a generation row is queued, so no cost is incurred.
- **Composer:** the *Animation* option is disabled for such models, with the same text as tooltip.
- "Unknown" counts as "not supported". Admins can enable the `image_input` capability per model (see §5), so a missing
  heuristic is fixed by configuration, not by a weaker generation path.

Exception: Strategy B (sprite sheet) does not need image input and stays available for any image model when the user
selects it explicitly.

## 4. Planning (LLM)

New prompt `AGENTIC_ANIMATION_PLANNING_PROMPT` and dataclasses in `agentic_service.py`:

```json
{
  "title": "Knight sword swing",
  "subject_anchor": "pixel-art knight, silver armor, red cape, side view facing right",
  "scene_anchor": "flat dark-blue background, no props, fixed camera, character centered",
  "style_anchor": "16-bit pixel art, limited palette, crisp edges, no anti-aliasing",
  "negative_prompt": "camera movement, zoom, different character, extra limbs, text, watermark, grid",
  "loop": "loop",                // loop | pingpong | once
  "default_frame_ms": 100,
  "frames": [
    { "index": 0, "title": "Idle", "pose": "standing, sword lowered", "duration_ms": 150 },
    { "index": 1, "title": "Wind-up", "pose": "sword pulled back over shoulder" },
    { "index": 2, "title": "Swing", "pose": "sword mid-arc in front of body", "duration_ms": 60 }
  ]
}
```

Rules for the prompt (contrast to the set planner):

- Same subject, same scene, same camera in every frame; each frame describes **only the change**.
- Motion should be split into small, evenly spaced steps; for loops the last frame must lead back into frame 0.
- Frame count: user min/max (reuse `min_images`/`max_images`, cap at e.g. 24), otherwise 6–12.
- The planner receives the chosen strategy so it can phrase delta prompts (A), a sheet prompt (B) or a motion prompt (C).

Parsing reuses `_parse_plan_json` patterns (code-fence stripping, padding/truncation). Fallback plan: generic
"subtle idle motion" frames built from the instruction.

## 5. Execution flow

```
POST /api/generate  { is_agentic: true, agentic_kind: "animation", animation: {...} }
        │
        ▼
_execute_agentic_generation_job ──► branch on agentic_kind
        │
        ├─ step "planning"    AgenticService.plan_animation()
        ├─ step "generating"  FrameStrategy.run()  → frame assets (stack_id, stack_order, role="frame")
        ├─ step "assembling"  AnimationService.assemble_gif(frames, timing, loop)
        └─ step "completed"   GIF asset (same stack_id, stack_order=0, role="animation"; frames move to 1…n)
```

Proposed code structure (keeps `GenerationService` from growing further):

| New / changed | Responsibility |
|---|---|
| `app/services/agentic_service.py` | `plan_animation()`, `AgenticAnimationPlan`, `AgenticFramePlan`. |
| `app/services/animation_service.py` (new) | `assemble_gif()` (Pillow), `slice_sprite_sheet()`, `video_to_gif()` (ffmpeg), frame normalization. Pure functions over bytes, easy to unit-test. |
| `app/services/frame_strategies.py` (new, phase 2) | `KeyframeChainStrategy`, `SpriteSheetStrategy`, `VideoStrategy` behind one interface; choose via model capabilities, raise a validation error when none fits (§3). Phase 1 implements the keyframe chain directly in `GenerationService._execute_agentic_animation_job()`; extract it once a second strategy exists. |
| `GenerationService` | Extract the shared "write image → thumbnail → sidecar → Asset" block from the agentic loop into a helper and reuse it for frames and the GIF. |
| `app/api/generation.py` | Accept `agentic_kind` + `animation` options; serialize `agentic_kind`, `assembling` step. |
| Registry / model config | Add an `image_input` capability (per model, admin-editable, pre-filled by per-adapter heuristics, default `false`). Required in phase 1 because unsupported models are rejected (§3). Stored on the model config → needs an Alembic migration. |
| `app/services/app_settings_service.py` | New animation limit settings (§6). |

All writes go through `StorageService.write_bytes_atomic()` / `resolve_managed_path()` as today.

## 6. Assembly details (`AnimationService`)

### Output formats

`animation.output` selects what is built from the frame series:

| Output | Result | Notes |
|---|---|---|
| `gif` (default) | Animated GIF as stack cover | 256 colours, 1-bit alpha, universal support. |
| `webp` | Animated WebP as stack cover | Full 8-bit alpha, no palette limit, usually much smaller; size limit reduces quality 90 → 75 → 60 before downscaling. |
| `none` | Frame series only | Same keyframe-chain consistency, no assembled file; frame 0 is the stack cover. |

With *Transparent background* the stored frame assets are keyed at full resolution (RGBA PNG) for every output, so
a plain frame series is transparent as well. The model still receives the raw frames as references.

- **Normalize**: all frames to the size of frame 0 (`ImageOps.fit`, no stretching).
- **Palette**: build one global palette from all frames (`Image.quantize` on a montage) to avoid per-frame color
  shimmer; dithering option (`none` for pixel art, `floyd-steinberg` for photos).
- **Timing**: per-frame `duration` list from the plan, user override for global FPS; `loop=0` for infinite loop;
  `pingpong` = frames + reversed inner frames. Durations are clamped to ≥ 20 ms, because browsers render smaller GIF
  delays as 100 ms.
- **Disposal**: `disposal=2` (restore to background) so transparent frames do not leave trails.

### Transparency (decision: supported)

GIF only has 1-bit alpha (one palette index is fully transparent). Pipeline when the user enables *Transparent
background*:

1. **Source alpha**: if the provider returns RGBA (e.g. `gpt-image` with `background: transparent`), use it directly.
2. **Chroma key otherwise**: the planner is instructed to use a flat key-color background (default `#00FF00`, switch
   to `#FF00FF` when the subject is green) in `scene_anchor`. Models never paint the exact key colour and the tint
   drifts per frame, so `AnimationService` estimates the real background from key-like border pixels of each frame,
   keys by distance to that estimate plus key-channel dominance (gradients), and removes colour spill only in a thin
   ring around the keyed area.
3. **Threshold**: alpha < 128 → transparent index, everything else opaque. Reserve one palette slot for transparency
   (quantize to 255 colors).
4. Frame assets in the stack are stored as PNG with alpha; only the assembled GIF is reduced to 1-bit alpha.

Without transparency, RGBA is flattened onto the plan's background color.

### Limits (decision: sensible defaults, admin-configurable)

Stored in `UI_SETTING_DEFAULTS` (studio settings UI), each validated against a hard cap in code so a misconfiguration
cannot exhaust disk, memory or the provider budget:

| Setting key | Default | Allowed range | Purpose |
|---|---|---|---|
| `animation_max_frames` | 24 | 2–64 | Upper bound for planned frames (also caps user max). |
| `animation_max_dimension_px` | 512 | 128–1024 | Longest side of the GIF; frames are downscaled before encoding. |
| `animation_max_file_size_mb` | 10 | 1–50 | Target size of the GIF. |
| `animation_default_frame_ms` | 100 | 20–1000 | Used when the plan has no duration. |

If the encoded GIF exceeds `animation_max_file_size_mb`: (1) reduce colors (256 → 128 → 64), (2) downscale in 15 %
steps down to 50 % of the limit dimension; if it still does not fit, fail the assembly step with a clear error while the
frame stack stays in the gallery (user can re-assemble with other settings). Range validation needs to reject `bool`
for int settings (`isinstance(True, int)` is `True`).

- **Extras (later)**: APNG or MP4 (via ffmpeg) as further outputs.

## 7. Gallery & frontend

- **Composer** (`PromptComposer.vue`): inside the Agentic settings bar a segmented control *Set / Animation*. For
  Animation: frame count, FPS (or "auto from plan"), loop mode, strategy (*Auto / Keyframe chain / Sprite sheet /
  Video*), max size. Respect `frontend/AGENTS.md` primitives; English labels only.
- **Plan review (decision: for Set and Animation)**: optional toggle *Review plan before generating*. The job then
  stops after planning in a new status `awaiting_review`; the card shows the plan as an editable list (titles, prompt
  details / pose texts, style anchors, frame durations, add/remove/reorder items). *Start* sends the edited plan,
  *Discard* cancels. This splits planning and generation into two calls:
  - `POST /api/generate` with `review_plan: true` → planning only, status `awaiting_review`.
  - `POST /api/generations/{id}/plan/approve` with the (edited) plan → validated against the same limits, re-queued
    as `generating`.
  The generation loop then reads the approved plan from `request_snapshot_json["agentic_plan"]` instead of calling the
  planner. Reviewed plans that are never approved are cleaned up like cancelled generations.
- **Generation card**: progress `Planning → Frame 3/8 → Assembling GIF`.
- **Stack view (decision: GIF is the stack cover)**: the gallery treats `stack_order == 0` as cover. Frames are
  stored with `stack_order` 0…n-1 while generating (so a failed assembly still leaves a visible stack) and are shifted
  to 1…n when the GIF is written with `stack_order = 0`. Deleting the cover keeps the frames;
  deleting the stack deletes both. Actions: *Regenerate frame* (re-runs one frame with the same
  references), *Reorder / remove frame*, *Re-assemble* (new GIF from current stack order + timing, no provider cost).
- **Thumbnails**: `ThumbnailService` must take the first frame of a GIF and must not animate in the grid; the viewer plays
  the original. Verify the gallery grid and lightbox handle `image/gif` (no conversion to WebP on output normalization —
  `_normalize_image_for_output` must not be applied to the assembled GIF).

## 8. Data model

- **Assets:** no schema change. Frames and GIF share `Asset.stack_id`; `meta_json` gets `role` (`frame` |
  `animation`), `frame_index`, `duration_ms`, and for the GIF `frame_asset_ids`, `fps`, `loop`, `strategy`,
  `transparent`.
- **Plan:** lives in `request_snapshot_json["agentic_plan"]` as today; plan review adds the status `awaiting_review`
  (check that `Generation.status` has no enum/check constraint, otherwise migrate).
- **Model config:** new `image_input` capability → schema change + Alembic migration.
- **Settings:** new keys in the existing app-settings table, no migration.

If re-assembly and frame editing become first-class, consider an `animations` table later (with Alembic migration).

## 9. Cost & limits

- Estimate before start: `frames × price per image` (+ 1 planning LLM call); show it in the composer using the existing
  pricing snapshot logic.
- Strategy A is sequential → long runtimes; show per-frame progress and keep cancellation checks
  (`_raise_if_cancelled`) between frames.
- Failed frame: retry once with the same references; if it still fails, either duplicate the previous frame (keeps
  timing) or abort, configurable. Never assemble a GIF from fewer than 2 frames.

## 10. Phased rollout

| Phase | Scope |
|---|---|
| **1 – MVP** ✅ | `image_input` capability (model + admin UI + migration) and rejection of unsupported models; `plan_animation()`; Strategy A; `AnimationService.assemble_gif()` incl. transparency and size limits; limit settings; GIF as stack cover; composer toggle; progress steps. |
| **2** | Plan review for Set **and** Animation (`awaiting_review`, approve endpoint, editable plan UI); sprite-sheet strategy; re-assemble + regenerate-frame actions. |
| **3** | Video → GIF route, WebP/APNG/MP4 export, cost estimate in composer. |

## 11. Tests

- **Unit**: plan parsing (valid JSON, code fences, too few/many frames, fallback); `assemble_gif` (frame count, durations,
  loop flag, size normalization, palette); `slice_sprite_sheet`; strategy selection by capabilities.
- **Service**: agentic animation job with a stub provider → N frame assets + 1 GIF asset with same `stack_id`; cancel
  mid-run; partial failure handling.
- **Routes**: `/api/generate` accepts and validates `agentic_kind`/`animation`; serializer exposes new fields.
- **E2E** (`tests/e2e/agentic-animation.spec.js`): toggle Animation, generate with the stub model, GIF appears as stack
  cover in the gallery.

## 12. Decisions

| Question | Decision | Details |
|---|---|---|
| GIF placement | Stack cover | §7 |
| Model without known image-input support | Reject the request (no text-only fallback) | §3 |
| Transparent GIFs | Supported (1-bit alpha, chroma key if provider has no alpha) | §6 |
| Frame / size limits | Defaults 24 frames, 512 px, 10 MB, 100 ms; admin-configurable within hard caps | §6 |
| Plan review before generation | Yes, for Set and Animation | §7 |
| Output formats | GIF, animated WebP, or frames only | §6 |

Remaining open points (can be decided during implementation):

- Chroma-key tolerance and spill removal: fixed values or exposed as advanced option?
- Plan review: should it be on by default for animations (higher cost per run) and off for sets?
