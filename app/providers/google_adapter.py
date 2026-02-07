from __future__ import annotations

from app.config import Settings
from app.providers.base import (
    ProviderAdapter,
    ProviderConfigError,
    ProviderError,
    ProviderGenerationRequest,
    ProviderGenerationResult,
)


class GoogleAdapter(ProviderAdapter):
    name = "google"

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        if not settings.google_api_key:
            raise ProviderConfigError("Google adapter requires GOOGLE_API_KEY in .env.")

        # TODO: implement Google image generation API call and map response to ProviderGenerationResult.
        raise ProviderError("Google adapter skeleton is present but API call implementation is pending.")
