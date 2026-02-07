from __future__ import annotations

from app.config import Settings
from app.providers.base import (
    ProviderAdapter,
    ProviderConfigError,
    ProviderError,
    ProviderGenerationRequest,
    ProviderGenerationResult,
)


class OpenAIAdapter(ProviderAdapter):
    name = "openai"

    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        if not settings.openai_api_key:
            raise ProviderConfigError("OpenAI adapter requires OPENAI_API_KEY in .env.")

        # TODO: implement real OpenAI Images API call and map response to ProviderGenerationResult.
        # Keep rate-limit related responses translated to ProviderRateLimitError / ProviderServiceUnavailableError.
        raise ProviderError("OpenAI adapter skeleton is present but API call implementation is pending.")
