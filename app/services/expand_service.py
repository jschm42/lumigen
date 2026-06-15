from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image, ImageDraw

from app.providers.base import ExpandSpec

logger = logging.getLogger(__name__)


# Hard cap on the total pixel count of the expanded canvas. Matches the BFL
# outpainting limit; downstream providers may further restrict this.
MAX_EXPAND_PIXELS = 4_000_000  # ≈ 4 MP

# Per-side cap to avoid abusive requests that would blow up memory.
MAX_SIDE_PIXELS = 3840

# Minimum per-side pad to keep the prompt-meaningful for the model.
MIN_SIDE_PIXELS = 8


class ExpandValidationError(ValueError):
    """Raised when an ``ExpandSpec`` is invalid (negative pixels, oversize, …)."""


@dataclass(frozen=True)
class PaddedImage:
    """Result of padding a source image into a larger canvas for outpainting."""

    data: bytes
    width: int
    height: int
    source_offset_x: int
    source_offset_y: int


@dataclass(frozen=True)
class ExpandArtifacts:
    """Bundle of prepared artifacts needed to dispatch an expand to a provider."""

    padded: PaddedImage
    mask_bytes: bytes
    target_width: int
    target_height: int


class ExpandService:
    """Prepare padded images and inpaint masks for image expansion (outpainting).

    The service is provider-agnostic: it only handles image manipulation. The
    actual provider dispatch is handled by the existing
    :class:`GenerationService` and the per-provider adapters; this class is the
    single source of truth for the pad+mask contract so the adapters can stay
    thin.
    """

    @staticmethod
    def validate(spec: ExpandSpec) -> None:
        """Validate *spec* dimensions against hard limits. Raises ``ExpandValidationError``."""
        for side_name, value in (
            ("top", spec.top),
            ("right", spec.right),
            ("bottom", spec.bottom),
            ("left", spec.left),
        ):
            if not isinstance(value, int):
                raise ExpandValidationError(
                    f"expand.{side_name} must be an integer (got {type(value).__name__})"
                )
            if value < 0:
                raise ExpandValidationError(
                    f"expand.{side_name} must be non-negative (got {value})"
                )
            if value > MAX_SIDE_PIXELS:
                raise ExpandValidationError(
                    f"expand.{side_name} exceeds per-side limit of {MAX_SIDE_PIXELS} px (got {value})"
                )
        fill = (spec.fill or "transparent").strip().lower()
        if fill not in {"transparent", "white", "black", "blur"} and not fill.startswith("#"):
            raise ExpandValidationError(
                "expand.fill must be 'transparent', 'white', 'black', 'blur', or a #rrggbb colour"
            )

    @staticmethod
    def compute_target_dimensions(
        source_width: int,
        source_height: int,
        spec: ExpandSpec,
    ) -> tuple[int, int]:
        """Return ``(target_width, target_height)`` for *spec* applied to *source_width*/*source_height*."""
        if source_width <= 0 or source_height <= 0:
            raise ExpandValidationError("Source image has zero dimensions")
        target_w = int(source_width) + int(spec.left) + int(spec.right)
        target_h = int(source_height) + int(spec.top) + int(spec.bottom)
        if target_w * target_h > MAX_EXPAND_PIXELS:
            raise ExpandValidationError(
                f"Expanded canvas would be {target_w}x{target_h}={target_w * target_h} px, "
                f"exceeding the {MAX_EXPAND_PIXELS} px limit"
            )
        return target_w, target_h

    @staticmethod
    def pad_image(
        data: bytes,
        spec: ExpandSpec,
        target_width: int,
        target_height: int,
    ) -> PaddedImage:
        """Pad *data* into a ``target_width`` × ``target_height`` canvas.

        The original image is anchored at the top-left of the padded region
        defined by ``(left, top)``; the surrounding area is filled according
        to ``spec.fill``.
        """
        ExpandService.validate(spec)
        with Image.open(BytesIO(data)) as source:
            source_rgba = _ensure_rgba(source)
            canvas = _render_filled_canvas(
                target_width=target_width,
                target_height=target_height,
                fill=spec.fill,
            )
            canvas.paste(source_rgba, (int(spec.left), int(spec.top)), source_rgba)
            buffer = BytesIO()
            canvas.save(buffer, format="PNG")
            return PaddedImage(
                data=buffer.getvalue(),
                width=target_width,
                height=target_height,
                source_offset_x=int(spec.left),
                source_offset_y=int(spec.top),
            )

    @staticmethod
    def build_mask(spec: ExpandSpec, target_width: int, target_height: int) -> bytes:
        """Build an alpha-mask PNG marking the padded region as "regenerate".

        Pixels inside the source image bounds are transparent/black
        (alpha 0 = preserve); pixels in the padded ring are opaque/white
        (alpha 255 = regenerate). OpenAI's edit endpoint expects the mask PNG
        to contain an alpha channel, so we first draw a grayscale guidance mask
        and then copy it into the output alpha channel.
        """
        ExpandService.validate(spec)
        alpha_mask = Image.new("L", (int(target_width), int(target_height)), color=0)
        draw = ImageDraw.Draw(alpha_mask)
        # Source area (preserved) — black.
        # Padded area (regenerate) — white. We draw four rectangles around it.
        white = 255
        t, r, b, left_pad = int(spec.top), int(spec.right), int(spec.bottom), int(spec.left)
        if t > 0:
            draw.rectangle(((0, 0), (target_width, t)), fill=white)
        if b > 0:
            draw.rectangle(((0, target_height - b), (target_width, target_height)), fill=white)
        if left_pad > 0:
            draw.rectangle(((0, t), (left_pad, target_height - b)), fill=white)
        if r > 0:
            draw.rectangle(
                ((target_width - r, t), (target_width, target_height - b)),
                fill=white,
            )
        # Build an RGBA mask where the alpha channel encodes editable regions.
        mask = Image.new("RGBA", (int(target_width), int(target_height)), (255, 255, 255, 0))
        mask.putalpha(alpha_mask)
        buffer = BytesIO()
        mask.save(buffer, format="PNG")
        return buffer.getvalue()

    @classmethod
    def prepare(
        cls,
        data: bytes,
        spec: ExpandSpec,
    ) -> ExpandArtifacts:
        """Validate, pad, and build a mask in a single call.

        Returns a :class:`ExpandArtifacts` ready to be dispatched to a
        provider. Raises :class:`ExpandValidationError` on invalid input.
        """
        cls.validate(spec)
        with Image.open(BytesIO(data)) as source:
            source_width, source_height = source.size
        target_w, target_h = cls.compute_target_dimensions(source_width, source_height, spec)
        padded = cls.pad_image(data, spec, target_w, target_h)
        mask_bytes = cls.build_mask(spec, target_w, target_h)
        return ExpandArtifacts(
            padded=padded,
            mask_bytes=mask_bytes,
            target_width=target_w,
            target_height=target_h,
        )

    @staticmethod
    def normalize_uniform(value: int) -> int:
        """Clamp a uniform padding value into the supported range."""
        if value < MIN_SIDE_PIXELS:
            return 0
        return min(int(value), MAX_SIDE_PIXELS)


def _ensure_rgba(image: Image.Image) -> Image.Image:
    """Return *image* in ``RGBA`` mode without mutating the original."""
    if image.mode == "RGBA":
        return image.copy()
    return image.convert("RGBA")


def _render_filled_canvas(
    target_width: int,
    target_height: int,
    fill: str,
) -> Image.Image:
    """Return an ``RGBA`` canvas filled according to *fill*."""
    normalized = (fill or "transparent").strip().lower()
    if normalized == "transparent":
        return Image.new("RGBA", (int(target_width), int(target_height)), (0, 0, 0, 0))
    if normalized == "white":
        return Image.new("RGBA", (int(target_width), int(target_height)), (255, 255, 255, 255))
    if normalized == "black":
        return Image.new("RGBA", (int(target_width), int(target_height)), (0, 0, 0, 255))
    if normalized.startswith("#") and len(normalized) in (7, 9):
        try:
            r = int(normalized[1:3], 16)
            g = int(normalized[3:5], 16)
            b = int(normalized[5:7], 16)
            a = int(normalized[7:9], 16) if len(normalized) == 9 else 255
        except ValueError as exc:
            raise ExpandValidationError(
                f"expand.fill colour '{fill}' is not a valid #rrggbb[/aa] value"
            ) from exc
        return Image.new("RGBA", (int(target_width), int(target_height)), (r, g, b, a))
    # Unknown values are rejected at validation time; fall back to transparent.
    return Image.new("RGBA", (int(target_width), int(target_height)), (0, 0, 0, 0))


def expand_to_provider_params(artifacts: ExpandArtifacts) -> dict[str, Any]:
    """Translate prepared :class:`ExpandArtifacts` into provider-param hints.

    Providers consume the artifacts differently: OpenAI edits wants the
    padded image + mask as multipart form fields, BFL wants a base64
    ``input_image`` + ``width`` + ``height`` + ``reference_offset_x/y``,
    OpenRouter just gets the image_url part. The dict returned here is the
    common shape that adapters can read from ``request.params``.
    """
    return {
        "padded_image": artifacts.padded.data,
        "padded_width": artifacts.padded.width,
        "padded_height": artifacts.padded.height,
        "padded_offset_x": artifacts.padded.source_offset_x,
        "padded_offset_y": artifacts.padded.source_offset_y,
        "mask": artifacts.mask_bytes,
        "target_width": artifacts.target_width,
        "target_height": artifacts.target_height,
    }
