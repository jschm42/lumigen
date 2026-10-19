from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.providers.base import ExpandSpec
from app.services.expand_service import ExpandService


def test_build_mask_marks_padded_edges_white_and_source_area_black() -> None:
    spec = ExpandSpec(top=2, right=3, bottom=4, left=5)

    mask_bytes = ExpandService.build_mask(spec, target_width=20, target_height=16)

    with Image.open(BytesIO(mask_bytes)) as mask:
        assert mask.mode == "RGBA"
        # top padding
        assert mask.getpixel((10, 0)) == (255, 255, 255, 255)
        # left padding
        assert mask.getpixel((0, 6)) == (255, 255, 255, 255)
        # right padding
        assert mask.getpixel((19, 6)) == (255, 255, 255, 255)
        # bottom padding
        assert mask.getpixel((10, 15)) == (255, 255, 255, 255)
        # preserved source area
        assert mask.getpixel((6, 3)) == (255, 255, 255, 0)
