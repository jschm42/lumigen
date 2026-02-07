from __future__ import annotations

from app.config import Settings
from app.providers.base import (
    ProviderAdapter,
    ProviderConfigError,
    ProviderError,
    ProviderGenerationRequest,
    ProviderGenerationResult,
)


class OpenRouterAdapter(ProviderAdapter):
    name = "openrouter"

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        if not settings.openrouter_api_key:
            raise ProviderConfigError("OpenRouter adapter requires OPENROUTER_API_KEY in .env.")

        # TODO: implement real OpenRouter image generation API call and response mapping.
        # Keep rate-limit related responses translated to ProviderRateLimitError / ProviderServiceUnavailableError.
        raise ProviderError("OpenRouter adapter skeleton is present but API call implementation is pending.")
