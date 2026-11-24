"""Unit tests for GIF assembly in ``app.services.animation_service``."""
from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from app.services.animation_service import (
    AnimationError,
    AnimationLimits,
    AnimationOptions,
    apply_loop_mode,
    assemble_gif,
    chroma_key,
    normalize_durations,
    parse_hex_color,
)


def _frame(step: int, size: tuple[int, int] = (256, 256), background=(0, 255, 0)) -> bytes:
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    draw.ellipse((20 + step * 20, 80, 100 + step * 20, 160), fill=(20, 20, 20))
    draw.rectangle((180, 180, 230, 230), fill=(200, 30, 30))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _open(data: bytes) -> Image.Image:
    return Image.open(BytesIO(data))


def test_assemble_gif_writes_animated_loop_with_durations() -> None:
    frames = [_frame(i) for i in range(4)]
    result = assemble_gif(frames, [150, None, 60, 80], AnimationOptions(loop="loop"), AnimationLimits())

    gif = _open(result.data)
    assert gif.format == "GIF"
    assert gif.n_frames == 4
    assert gif.info.get("loop") == 0
    assert result.durations_ms == [150, 100, 60, 80]
    assert (result.width, result.height) == (256, 256)
    assert result.mime == "image/gif"


def test_assemble_gif_once_has_no_loop_flag() -> None:
    result = assemble_gif([_frame(0), _frame(1)], [], AnimationOptions(loop="once"), AnimationLimits())
    assert "loop" not in _open(result.data).info


def test_assemble_gif_pingpong_appends_reversed_inner_frames() -> None:
    result = assemble_gif([_frame(i) for i in range(4)], [], AnimationOptions(loop="pingpong"), AnimationLimits())
    # 0 1 2 3 2 1
    assert result.frame_count == 6
    assert _open(result.data).n_frames == 6


def test_assemble_gif_transparent_keys_out_background() -> None:
    result = assemble_gif(
        [_frame(0), _frame(1)], [], AnimationOptions(transparent=True), AnimationLimits()
    )
    gif = _open(result.data)
    assert "transparency" in gif.info
    rgba = gif.convert("RGBA")
    assert rgba.getpixel((5, 5))[3] == 0  # key-colour background
    assert rgba.getpixel((205, 205)) == (200, 30, 30, 255)  # subject stays opaque
    assert rgba.getpixel((60, 120))[3] == 255  # dark subject is not mistaken for transparency


def test_assemble_gif_uses_provider_alpha_when_present() -> None:
    def rgba_frame(step: int) -> bytes:
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((10 + step, 10, 40 + step, 40), fill=(0, 0, 255, 255))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    result = assemble_gif([rgba_frame(0), rgba_frame(5)], [], AnimationOptions(transparent=True), AnimationLimits())
    rgba = _open(result.data).convert("RGBA")
    assert rgba.getpixel((2, 2))[3] == 0
    assert rgba.getpixel((20, 20)) == (0, 0, 255, 255)


def test_assemble_gif_flattens_alpha_without_transparency() -> None:
    image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    result = assemble_gif(
        [buffer.getvalue(), buffer.getvalue()],
        [],
        AnimationOptions(background=(255, 255, 255)),
        AnimationLimits(),
    )
    gif = _open(result.data)
    assert "transparency" not in gif.info
    assert gif.convert("RGB").getpixel((3, 3)) == (255, 255, 255)


def test_assemble_gif_downscales_to_max_dimension_and_fits_mismatched_frames() -> None:
    frames = [_frame(0, size=(1024, 512)), _frame(1, size=(800, 800))]
    result = assemble_gif(frames, [], AnimationOptions(), AnimationLimits(max_dimension_px=256))
    assert (result.width, result.height) == (256, 128)
    gif = _open(result.data)
    gif.seek(1)
    assert gif.size == (256, 128)


def _gradient_frame(step: int) -> bytes:
    image = Image.new("RGB", (512, 512))
    image.putdata([((x * 2 + step * 9) % 256, (y + step * 5) % 256, (x + y) % 256) for y in range(512) for x in range(512)])
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_assemble_gif_reduces_colours_and_size_to_meet_file_limit() -> None:
    frames = [_gradient_frame(i) for i in range(4)]
    unlimited = assemble_gif(frames, [], AnimationOptions(dither=True), AnimationLimits())
    limit = int(len(unlimited.data) * 0.6)
    limited = assemble_gif(frames, [], AnimationOptions(dither=True), AnimationLimits(max_file_size_bytes=limit))
    assert len(limited.data) <= limit
    assert limited.colors < 256 or limited.width < unlimited.width


def test_assemble_gif_raises_when_limit_unreachable() -> None:
    with pytest.raises(AnimationError, match="exceeds the limit"):
        assemble_gif([_frame(0), _frame(1)], [], AnimationOptions(), AnimationLimits(max_file_size_bytes=10))


@pytest.mark.parametrize(
    ("frames", "limits", "options", "message"),
    [
        (1, AnimationLimits(), AnimationOptions(), "at least two frames"),
        (4, AnimationLimits(max_frames=3), AnimationOptions(), "at most 3 frames"),
        (2, AnimationLimits(), AnimationOptions(loop="bounce"), "Unsupported loop mode"),
    ],
)
def test_assemble_gif_validates_input(frames: int, limits, options, message: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(AnimationError, match=message):
        assemble_gif([_frame(i) for i in range(frames)], [], options, limits)


def test_normalize_durations_fills_defaults_and_clamps() -> None:
    assert normalize_durations([5, None, "x", 250], 5, 90) == [20, 90, 90, 250, 90]  # type: ignore[list-item]


def test_apply_loop_mode_only_changes_pingpong() -> None:
    frames = [Image.new("RGB", (1, 1)) for _ in range(3)]
    assert apply_loop_mode(frames, [1, 2, 3], "loop") == (frames, [1, 2, 3])
    looped, durations = apply_loop_mode(frames, [1, 2, 3], "pingpong")
    assert len(looped) == 4
    assert durations == [1, 2, 3, 2]


def test_chroma_key_removes_key_colour_and_spill() -> None:
    image = Image.new("RGB", (40, 40), (10, 250, 5))  # near key colour
    ImageDraw.Draw(image).rectangle((10, 10, 29, 29), fill=(150, 170, 140))  # subject with green spill
    keyed = chroma_key(image, (0, 255, 0), 60)
    assert keyed.getpixel((2, 2))[3] == 0
    r, g, b, a = keyed.getpixel((10, 20))  # edge of the subject: spill removed
    assert a == 255 and g <= max(r, b)
    assert keyed.getpixel((20, 20)) == (150, 170, 140, 255)  # interior untouched


def test_parse_hex_color() -> None:
    assert parse_hex_color("#FF00FF", (0, 0, 0)) == (255, 0, 255)
    assert parse_hex_color("nope", (1, 2, 3)) == (1, 2, 3)
    assert parse_hex_color(None, (1, 2, 3)) == (1, 2, 3)


def test_limits_from_ui_settings() -> None:
    limits = AnimationLimits.from_ui_settings(
        {
            "animation_max_frames": 10,
            "animation_max_dimension_px": 300,
            "animation_max_file_size_mb": 2,
            "animation_default_frame_ms": 80,
        }
    )
    assert limits == AnimationLimits(
        max_frames=10, max_dimension_px=300, max_file_size_bytes=2 * 1024 * 1024, default_frame_ms=80
    )


def _magenta_frame(background: tuple[int, int, int], gradient: bool = False) -> bytes:
    """Frame like real model output: tinted, not exactly #FF00FF, optionally with a vertical gradient."""
    image = Image.new("RGB", (200, 200), background)
    if gradient:
        draw = ImageDraw.Draw(image)
        for y in range(200):
            shade = y // 4
            draw.line((0, y, 199, y), fill=(background[0] - shade, background[1] + shade // 3, background[2] - shade))
    ImageDraw.Draw(image).rectangle((70, 40, 130, 170), fill=(40, 120, 50))  # green cloak
    ImageDraw.Draw(image).rectangle((85, 20, 115, 40), fill=(225, 180, 150))  # skin
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_transparent_keys_drifting_model_backgrounds_in_every_frame() -> None:
    # Real FLUX output for "#FF00FF": the tint differs per frame and is far from the exact key colour.
    backgrounds = [(253, 31, 217), (227, 53, 188), (231, 48, 185), (251, 61, 211)]
    frames = [_magenta_frame(bg, gradient=i % 2 == 1) for i, bg in enumerate(backgrounds)]
    result = assemble_gif(
        frames, [], AnimationOptions(transparent=True, key_color=(255, 0, 255)), AnimationLimits()
    )
    gif = _open(result.data)
    for index in range(gif.n_frames):
        gif.seek(index)
        rgba = gif.convert("RGBA")
        assert rgba.getpixel((3, 3))[3] == 0, f"frame {index} background stays opaque"
        assert rgba.getpixel((195, 195))[3] == 0, f"frame {index} gradient corner stays opaque"
        assert rgba.getpixel((100, 100))[3] == 255  # subject (green) is kept
        assert rgba.getpixel((100, 30))[3] == 255  # skin is not mistaken for magenta


def test_estimate_background_uses_border_and_falls_back_to_key() -> None:
    from app.services.animation_service import estimate_background

    tinted = Image.new("RGB", (100, 100), (230, 50, 190))
    assert estimate_background(tinted, (255, 0, 255)) == (230, 50, 190)
    # Border far from the key colour (e.g. subject fills the frame): keep the requested key.
    assert estimate_background(Image.new("RGB", (100, 100), (20, 20, 20)), (255, 0, 255)) == (255, 0, 255)


def test_chroma_key_removes_magenta_spill_only_at_edges() -> None:
    image = Image.new("RGB", (60, 20), (240, 50, 200))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 0, 59, 19), fill=(150, 110, 140))  # muted subject touching the key and the border
    keyed = chroma_key(image, (255, 0, 255), 60)
    assert keyed.getpixel((5, 10))[3] == 0
    r, g, b, a = keyed.getpixel((21, 10))  # edge pixel: tint removed
    assert a == 255 and min(r, b) <= g
    assert keyed.getpixel((55, 10)) == (150, 110, 140, 255)  # interior keeps its own colour



def test_assemble_animation_webp_keeps_full_alpha_and_loop() -> None:
    from app.services.animation_service import assemble_animation

    result = assemble_animation(
        [_frame(i) for i in range(3)],
        [100, 150, 200],
        AnimationOptions(transparent=True, output_format="webp", key_color=(0, 255, 0)),
        AnimationLimits(),
    )
    assert (result.mime, result.extension) == ("image/webp", "webp")
    webp = _open(result.data)
    assert webp.format == "WEBP" and webp.n_frames == 3
    assert webp.info.get("loop") == 0
    rgba = webp.convert("RGBA")
    assert rgba.getpixel((5, 5))[3] == 0
    assert rgba.getpixel((205, 205))[3] == 255


def test_assemble_animation_webp_once_plays_a_single_time() -> None:
    from app.services.animation_service import assemble_animation

    result = assemble_animation([_frame(0), _frame(1)], [], AnimationOptions(loop="once", output_format="webp"), AnimationLimits())
    assert _open(result.data).info.get("loop") == 1


def test_assemble_animation_rejects_unknown_format() -> None:
    from app.services.animation_service import assemble_animation

    with pytest.raises(AnimationError, match="Unsupported animation format"):
        assemble_animation([_frame(0), _frame(1)], [], AnimationOptions(output_format="none"), AnimationLimits())


def test_key_frame_returns_png_with_alpha_and_passes_through_real_alpha() -> None:
    from app.services.animation_service import key_frame

    keyed = Image.open(BytesIO(key_frame(_frame(0), (0, 255, 0))))
    assert keyed.format == "PNG" and keyed.mode == "RGBA"
    assert keyed.getpixel((5, 5))[3] == 0

    already = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    buffer = BytesIO()
    already.save(buffer, format="PNG")
    assert key_frame(buffer.getvalue(), (0, 255, 0)) == buffer.getvalue()



def test_frame_difference_separates_copies_from_new_poses() -> None:
    from app.services.animation_service import STATIC_FRAME_THRESHOLD, frame_difference

    assert frame_difference(_frame(0), _frame(0)) == 0
    # Same pose on a slightly different background tint (typical copy by an edit model).
    assert frame_difference(_frame(0), _frame(0, background=(5, 250, 8))) < STATIC_FRAME_THRESHOLD
    # Subject moved to a new position.
    assert frame_difference(_frame(0), _frame(4)) > STATIC_FRAME_THRESHOLD
