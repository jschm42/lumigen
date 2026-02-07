from __future__ import annotations

from app.config import Settings
from app.providers.base import (
    ProviderAdapter,
    ProviderConfigError,
    ProviderError,
    ProviderGenerationRequest,
    ProviderGenerationResult,
)


class BFLAdapter(ProviderAdapter):
    name = "bfl"

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        if not settings.bfl_api_key:
            raise ProviderConfigError("BFL adapter requires BFL_API_KEY in .env.")

        # TODO: implement Black Forest Labs image generation API call and response mapping.
        raise ProviderError("BFL adapter skeleton is present but API call implementation is pending.")
