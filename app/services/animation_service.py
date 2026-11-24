"""Assemble generated frames into animated GIFs or animated WebPs.

Pure byte-in / byte-out helpers without database or provider access, so the
encoding rules (palette, transparency, timing, size limits) are easy to test.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageChops, ImageFilter, ImageOps

#: Browsers render GIF frame delays below 20 ms as 100 ms, so shorter values are clamped.
MIN_FRAME_MS = 20
#: Alpha values below this threshold become fully transparent (GIF has 1-bit alpha).
ALPHA_THRESHOLD = 128
#: Default chroma-key colour the planner uses when transparency is requested.
DEFAULT_KEY_COLOR = (0, 255, 0)
#: Colour counts tried when the encoded GIF exceeds the size limit.
_COLOR_STEPS = (256, 128, 64)
#: WebP quality levels tried when the encoded WebP exceeds the size limit.
_WEBP_QUALITY_STEPS = (90, 75, 60)
#: Each downscale step shrinks the longest side to this fraction.
_DOWNSCALE_FACTOR = 0.85
#: Downscaling stops at this fraction of the configured maximum dimension.
_MIN_SCALE_OF_LIMIT = 0.5

LOOP_MODES = ("loop", "pingpong", "once")
#: "none" keeps only the frame series (no assembled file).
OUTPUT_FORMATS = ("gif", "webp", "none")
#: File extension and MIME type of each assembled output format.
OUTPUT_FILE_TYPES: dict[str, tuple[str, str]] = {"gif": ("gif", "image/gif"), "webp": ("webp", "image/webp")}


class AnimationError(ValueError):
    """Raised when frames cannot be assembled into an animation within the limits."""


@dataclass(frozen=True)
class AnimationLimits:
    """Upper bounds applied while assembling an animation."""

    max_frames: int = 24
    max_dimension_px: int = 512
    max_file_size_bytes: int = 10 * 1024 * 1024
    default_frame_ms: int = 100

    @classmethod
    def from_ui_settings(cls, settings: dict[str, int]) -> AnimationLimits:
        """Build limits from the studio UI settings (see ``AppSettingsService``)."""
        defaults = cls()
        return cls(
            max_frames=int(settings.get("animation_max_frames", defaults.max_frames)),
            max_dimension_px=int(settings.get("animation_max_dimension_px", defaults.max_dimension_px)),
            max_file_size_bytes=int(settings.get("animation_max_file_size_mb", 10)) * 1024 * 1024,
            default_frame_ms=int(settings.get("animation_default_frame_ms", defaults.default_frame_ms)),
        )


@dataclass(frozen=True)
class AnimationOptions:
    """User-selected options for one animation."""

    loop: str = "loop"
    transparent: bool = False
    key_color: tuple[int, int, int] = DEFAULT_KEY_COLOR
    key_tolerance: int = 60
    background: tuple[int, int, int] = (255, 255, 255)
    dither: bool = False
    output_format: str = "gif"


@dataclass
class AssembledAnimation:
    """The encoded animation plus the parameters that were finally applied."""

    data: bytes
    width: int
    height: int
    frame_count: int
    durations_ms: list[int]
    #: Palette size (GIF) or quality (WebP) that met the size limit.
    colors: int
    mime: str = "image/gif"
    extension: str = "gif"


def parse_hex_color(value: str | None, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    """Parse ``#RRGGBB`` into an RGB tuple, returning *fallback* for invalid input."""
    text = str(value or "").strip().lstrip("#")
    if len(text) != 6:
        return fallback
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError:
        return fallback


def normalize_durations(durations: list[int | None], frame_count: int, default_ms: int) -> list[int]:
    """Return one duration per frame, filling gaps with *default_ms* and clamping to ``MIN_FRAME_MS``."""
    result: list[int] = []
    fallback = max(MIN_FRAME_MS, int(default_ms))
    for idx in range(frame_count):
        raw = durations[idx] if idx < len(durations) else None
        try:
            value = int(raw) if raw is not None else fallback
        except (TypeError, ValueError):
            value = fallback
        result.append(max(MIN_FRAME_MS, min(value, 10_000)))
    return result


def apply_loop_mode(frames: list[Image.Image], durations: list[int], loop: str) -> tuple[list[Image.Image], list[int]]:
    """Expand frames for ``pingpong`` (forward, then backward without repeating the ends)."""
    if loop != "pingpong" or len(frames) < 3:
        return frames, durations
    inner = list(range(len(frames) - 2, 0, -1))
    return frames + [frames[i] for i in inner], durations + [durations[i] for i in inner]


#: Max channel distance between the estimated border colour and the requested key colour.
_MAX_BACKGROUND_DRIFT = 140
#: A pixel whose key channels exceed all other channels by this margin counts as background.
_KEY_DOMINANCE = 90
#: Width in pixels of the ring around the keyed area where colour spill is removed.
_SPILL_RING_PX = 5


def _channel_distance(image: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    """Return an L image with the max per-channel distance of each pixel to *color*."""
    diff = ImageChops.difference(image, Image.new("RGB", image.size, color))
    dr, dg, db = diff.split()
    return ImageChops.lighter(ImageChops.lighter(dr, dg), db)


def estimate_background(image: Image.Image, key_color: tuple[int, int, int]) -> tuple[int, int, int]:
    """Estimate the actual key-background colour from the image border.

    Image models rarely paint the exact key colour and the tint drifts from
    frame to frame (e.g. ``(227, 58, 189)`` instead of ``#FF00FF``). Only
    border pixels that look like the key (key channels dominate, close to
    *key_color*) are considered, so a subject touching the border does not skew
    the estimate. With too few such pixels the requested key colour is kept.
    """
    rgb = image.convert("RGB")
    width, height = rgb.size
    strip = max(2, min(width, height) // 50)
    boxes = [
        (0, 0, width, strip),
        (0, height - strip, width, height),
        (0, strip, strip, height - strip),
        (width - strip, strip, width, height - strip),
    ]
    strong = [i for i in range(3) if key_color[i] > 128]
    weak = [i for i in range(3) if key_color[i] <= 128]
    total = 0
    candidates: list[tuple[int, int, int]] = []
    for box in boxes:
        raw = rgb.crop(box).tobytes()
        for offset in range(0, len(raw), 3):
            pixel = (raw[offset], raw[offset + 1], raw[offset + 2])
            total += 1
            if max(abs(pixel[i] - key_color[i]) for i in range(3)) > _MAX_BACKGROUND_DRIFT:
                continue
            if strong and weak and min(pixel[i] for i in strong) - max(pixel[i] for i in weak) < _KEY_DOMINANCE // 2:
                continue
            candidates.append(pixel)
    if not candidates or len(candidates) < total * 0.05:
        return key_color
    middle = len(candidates) // 2
    return tuple(sorted(p[i] for p in candidates)[middle] for i in range(3))  # type: ignore[return-value]


def _dominance_mask(channels: list[Image.Image], key_color: tuple[int, int, int]) -> Image.Image | None:
    """Mask pixels whose key channels clearly dominate (catches gradients and shading of the key)."""
    strong = [channels[i] for i in range(3) if key_color[i] > 128]
    weak = [channels[i] for i in range(3) if key_color[i] <= 128]
    if not strong or not weak:
        return None
    strong_min = strong[0] if len(strong) == 1 else ImageChops.darker(*strong)
    weak_max = weak[0] if len(weak) == 1 else ImageChops.lighter(*weak)
    margin = ImageChops.subtract(strong_min, weak_max)
    return margin.point(lambda v: 255 if v >= _KEY_DOMINANCE else 0)


def _despill(channels: list[Image.Image], key_color: tuple[int, int, int]) -> list[Image.Image]:
    """Remove the key tint: the key channels may not exceed the strongest other channel."""
    strong_idx = [i for i in range(3) if key_color[i] > 128]
    weak = [channels[i] for i in range(3) if key_color[i] <= 128]
    if not strong_idx or not weak:
        return channels
    cap = weak[0] if len(weak) == 1 else ImageChops.lighter(*weak)
    result = list(channels)
    if len(strong_idx) == 1:
        result[strong_idx[0]] = ImageChops.darker(channels[strong_idx[0]], cap)
    else:
        # Two key channels (magenta): subtract their shared excess over the weak channel.
        shared = ImageChops.darker(*(channels[i] for i in strong_idx))
        excess = ImageChops.subtract(shared, cap)
        for i in strong_idx:
            result[i] = ImageChops.subtract(channels[i], excess)
    return result


def chroma_key(image: Image.Image, key_color: tuple[int, int, int], tolerance: int) -> Image.Image:
    """Return an RGBA copy of *image* with the key-colour background made transparent.

    The background colour is estimated per frame from the border (see
    :func:`estimate_background`). A pixel becomes transparent when it is within
    *tolerance* (max channel distance) of that colour, or when its key channels
    clearly dominate the others. Colour spill is removed only in a thin ring
    around the keyed area so the subject's own colours stay untouched.
    """
    rgba = image.convert("RGBA")
    red, green, blue, alpha = rgba.split()
    channels = [red, green, blue]
    rgb = rgba.convert("RGB")

    background = estimate_background(rgb, key_color)
    key_mask = _channel_distance(rgb, background).point(lambda v: 255 if v <= tolerance else 0)
    dominance = _dominance_mask(channels, key_color)
    if dominance is not None:
        key_mask = ImageChops.lighter(key_mask, dominance)
    alpha = Image.composite(Image.new("L", rgba.size, 0), alpha, key_mask)

    ring = ImageChops.subtract(key_mask.filter(ImageFilter.MaxFilter(_SPILL_RING_PX * 2 + 1)), key_mask)
    despilled = _despill(channels, key_color)
    channels = [Image.composite(despilled[i], channels[i], ring) for i in range(3)]
    return Image.merge("RGBA", (*channels, alpha))


def _fit_frames(frames: list[Image.Image], max_dimension: int) -> list[Image.Image]:
    """Resize all frames to the size of frame 0, bounded by *max_dimension* on the longest side."""
    first = frames[0]
    width, height = first.size
    scale = min(1.0, max_dimension / max(width, height))
    target = (max(1, round(width * scale)), max(1, round(height * scale)))
    fitted: list[Image.Image] = []
    for frame in frames:
        if frame.size == target:
            fitted.append(frame)
        elif frame.size == first.size:
            fitted.append(frame.resize(target, Image.Resampling.LANCZOS))
        else:
            fitted.append(ImageOps.fit(frame, target, Image.Resampling.LANCZOS))
    return fitted


def _prepare_rgba(data: bytes, options: AnimationOptions, max_dimension: int) -> Image.Image:
    """Decode one frame, shrink it to *max_dimension* and apply transparency handling.

    Shrinking first keeps the per-pixel chroma key cheap for large provider images.
    """
    with Image.open(BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source)
        image.load()
    if max(image.size) > max_dimension:
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA")
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    has_alpha = image.mode in {"RGBA", "LA", "PA"} or (image.mode == "P" and "transparency" in image.info)
    if options.transparent:
        if has_alpha:
            rgba = image.convert("RGBA")
            # Ignore providers that return a fully opaque alpha channel: key the background instead.
            if rgba.getchannel("A").getextrema()[0] < 255:
                return rgba
        return chroma_key(image, options.key_color, options.key_tolerance)
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (*options.background, 255))
    background.alpha_composite(rgba)
    return background


def _encode(
    frames: list[Image.Image],
    durations: list[int],
    options: AnimationOptions,
    colors: int,
) -> bytes:
    """Encode RGBA frames to GIF bytes with one shared palette."""
    palette_colors = colors - 1 if options.transparent else colors
    # Build one global palette from a montage of all frames to avoid colour shimmer.
    width, height = frames[0].size
    montage = Image.new("RGB", (width, height * len(frames)))
    for idx, frame in enumerate(frames):
        montage.paste(frame.convert("RGB"), (0, idx * height))
    quantized = montage.quantize(colors=palette_colors, method=Image.Quantize.MEDIANCUT)
    raw_palette = (quantized.getpalette() or [0, 0, 0])[: palette_colors * 3]
    used = len(raw_palette) // 3
    # Pad unused slots with copies of entry 0: nearest-colour ties resolve to the lowest
    # index, so the padding (including the transparency slot) is never picked for pixels.
    padded = raw_palette + raw_palette[:3] * (256 - used)
    palette_image = Image.new("P", (1, 1))
    palette_image.putpalette(padded)
    palette_colors = used
    dither = Image.Dither.FLOYDSTEINBERG if options.dither else Image.Dither.NONE

    encoded: list[Image.Image] = []
    transparent_index = palette_colors  # first unused slot after the quantized colours
    for frame in frames:
        indexed = frame.convert("RGB").quantize(palette=palette_image, dither=dither)
        if options.transparent:
            alpha = frame.getchannel("A")
            mask = alpha.point(lambda v: 255 if v < ALPHA_THRESHOLD else 0)
            indexed.paste(transparent_index, mask=mask)
            indexed.info["transparency"] = transparent_index
        encoded.append(indexed)

    buffer = BytesIO()
    save_kwargs: dict[str, object] = {
        "format": "GIF",
        "save_all": True,
        "append_images": encoded[1:],
        "duration": durations,
        "disposal": 2,
        "optimize": False,
    }
    if options.loop != "once":
        save_kwargs["loop"] = 0
    if options.transparent:
        save_kwargs["transparency"] = transparent_index
    encoded[0].save(buffer, **save_kwargs)
    return buffer.getvalue()


def _encode_webp(
    frames: list[Image.Image],
    durations: list[int],
    options: AnimationOptions,
    quality: int,
) -> bytes:
    """Encode RGBA frames to an animated WebP (full 8-bit alpha, no palette limit)."""
    buffer = BytesIO()
    frames[0].save(
        buffer,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        # WebP loop count: 0 = infinite, 1 = play once.
        loop=1 if options.loop == "once" else 0,
        quality=quality,
        method=4,
        background=(0, 0, 0, 0),
    )
    return buffer.getvalue()


def key_frame(data: bytes, key_color: tuple[int, int, int], tolerance: int = 60) -> bytes:
    """Return *data* as RGBA PNG with the chroma-key background removed (full resolution).

    Frames that already carry real transparency are returned unchanged.
    """
    with Image.open(BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source)
        image.load()
    if image.mode in {"RGBA", "LA", "PA"} and image.convert("RGBA").getchannel("A").getextrema()[0] < 255:
        return data
    keyed = chroma_key(image, key_color, tolerance)
    buffer = BytesIO()
    keyed.save(buffer, format="PNG")
    return buffer.getvalue()


def assemble_gif(
    frame_data: list[bytes],
    durations_ms: list[int | None],
    options: AnimationOptions,
    limits: AnimationLimits,
) -> AssembledAnimation:
    """Assemble encoded frame images into an animated GIF within *limits* (see :func:`assemble_animation`)."""
    return assemble_animation(
        frame_data,
        durations_ms,
        AnimationOptions(**{**options.__dict__, "output_format": "gif"}),
        limits,
    )


def assemble_animation(
    frame_data: list[bytes],
    durations_ms: list[int | None],
    options: AnimationOptions,
    limits: AnimationLimits,
) -> AssembledAnimation:
    """Assemble encoded frame images into an animated GIF or WebP within *limits*.

    The format comes from ``options.output_format`` (``gif`` or ``webp``). When
    the result exceeds ``limits.max_file_size_bytes`` the palette (GIF:
    256 → 128 → 64 colours) or the quality (WebP: 90 → 75 → 60) is reduced
    first, then the frames are downscaled in 15 % steps down to half the
    configured maximum dimension. Raises ``AnimationError`` if fewer than two
    frames are given, too many frames are given, the format is unsupported, or
    the size limit cannot be met.
    """
    if options.output_format not in OUTPUT_FILE_TYPES:
        raise AnimationError(f"Unsupported animation format: {options.output_format!r}.")
    if len(frame_data) < 2:
        raise AnimationError("An animation needs at least two frames.")
    if len(frame_data) > limits.max_frames:
        raise AnimationError(f"An animation can have at most {limits.max_frames} frames.")
    if options.loop not in LOOP_MODES:
        raise AnimationError(f"Unsupported loop mode: {options.loop!r}.")

    rgba_frames = [_prepare_rgba(data, options, limits.max_dimension_px) for data in frame_data]
    durations = normalize_durations(durations_ms, len(rgba_frames), limits.default_frame_ms)

    dimension = limits.max_dimension_px
    min_dimension = max(16, int(limits.max_dimension_px * _MIN_SCALE_OF_LIMIT))
    last_size = 0
    while True:
        fitted = _fit_frames(rgba_frames, dimension)
        sequence, sequence_durations = apply_loop_mode(fitted, durations, options.loop)
        is_webp = options.output_format == "webp"
        for level in _WEBP_QUALITY_STEPS if is_webp else _COLOR_STEPS:
            if is_webp:
                data = _encode_webp(sequence, sequence_durations, options, level)
            else:
                data = _encode(sequence, sequence_durations, options, level)
            last_size = len(data)
            if last_size <= limits.max_file_size_bytes:
                width, height = fitted[0].size
                extension, mime = OUTPUT_FILE_TYPES[options.output_format]
                return AssembledAnimation(
                    data=data,
                    width=width,
                    height=height,
                    frame_count=len(sequence),
                    durations_ms=sequence_durations,
                    colors=level,
                    mime=mime,
                    extension=extension,
                )
        next_dimension = int(dimension * _DOWNSCALE_FACTOR)
        if next_dimension < min_dimension or next_dimension == dimension:
            break
        dimension = next_dimension

    raise AnimationError(
        f"The animation is {_format_size(last_size)} even after reducing quality and size, "
        f"which exceeds the limit of {_format_size(limits.max_file_size_bytes)}. Use fewer frames or a smaller size."
    )


def _format_size(size_bytes: int) -> str:
    """Return a human-readable size (KB below one megabyte, MB otherwise)."""
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
