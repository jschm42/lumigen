from __future__ import annotations

import random
from io import BytesIO

from PIL import Image, ImageDraw

from app.config import Settings
from app.providers.base import (
    ProviderAdapter,
    ProviderGenerationRequest,
    ProviderGenerationResult,
    ProviderImage,
)


class StubAdapter(ProviderAdapter):
    name = "stub"

    async def list_models(self, settings: Settings) -> list[str]:
        _ = settings
        return ["stub-v1"]

    async def generate(
        self, request: ProviderGenerationRequest, settings: Settings
    ) -> ProviderGenerationResult:
        n_images = max(1, request.n_images)
        width = request.width or 768
        height = request.height or 768
        output_format = request.output_format.lower().strip(".")

        pil_format = {
            "png": "PNG",
            "jpg": "JPEG",
            "jpeg": "JPEG",
            "webp": "WEBP",
        }.get(output_format, "PNG")
        ext = "jpg" if pil_format == "JPEG" else output_format
        mime = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
        }.get(ext, "image/png")

        images: list[ProviderImage] = []
        seed = (
            request.seed if request.seed is not None else random.randint(0, 9_999_999)
        )
        rng = random.Random(seed)

        for idx in range(1, n_images + 1):
            background = (
                rng.randint(20, 220),
                rng.randint(20, 220),
                rng.randint(20, 220),
            )
            image = Image.new("RGB", (width, height), color=background)
            draw = ImageDraw.Draw(image)

            prompt_preview = request.prompt.strip().replace("\n", " ")[:180]
            text = f"Pixelforge stub\nmodel={request.model}\nseed={seed} idx={idx}\n{prompt_preview}"
            draw.text((24, 24), text, fill=(255, 255, 255))

            output = BytesIO()
            image.save(output, format=pil_format)

            images.append(
                ProviderImage(
                    data=output.getvalue(),
                    mime=mime,
                    width=width,
                    height=height,
                    meta={"provider": self.name, "index": idx, "seed": seed},
                )
            )

        return ProviderGenerationResult(
            images=images, raw_meta={"adapter": self.name, "seed": seed}
        )
