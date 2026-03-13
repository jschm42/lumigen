from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass

from app.config import Settings
from app.providers.base import (
    ProviderAdapter,
    ProviderError,
    ProviderGenerationRequest,
    ProviderGenerationResult,
    ProviderRateLimitError,
    ProviderServiceUnavailableError,
)
from app.providers.bfl_adapter import BFLAdapter
from app.providers.google_adapter import GoogleAdapter
from app.providers.openai_adapter import OpenAIAdapter
from app.providers.openrouter_adapter import OpenRouterAdapter
from app.providers.stub_adapter import StubAdapter


@dataclass
class ProviderPolicy:
    """Concurrency and retry settings applied to a specific provider's executor."""

    max_concurrent: int
    min_interval_ms: int
    retry_max_attempts: int
    retry_base_delay_ms: int
    retry_max_delay_ms: int


class ProviderExecutor:
    """Enforces concurrency limits, request spacing, and exponential-backoff retries for a provider."""

    def __init__(self, policy: ProviderPolicy) -> None:
        self._policy = policy
        self._semaphore = asyncio.Semaphore(max(1, policy.max_concurrent))
        self._spacing_lock = asyncio.Lock()
        self._last_started_at = 0.0

    async def _wait_for_spacing(self) -> None:
        min_interval_s = max(0, self._policy.min_interval_ms) / 1000
        if min_interval_s == 0:
            return
        async with self._spacing_lock:
            now = time.monotonic()
            wait = (self._last_started_at + min_interval_s) - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._last_started_at = now

    async def run(self, func) -> ProviderGenerationResult:  # type: ignore[no-untyped-def]
        """Execute *func* under the semaphore and spacing lock, retrying on rate-limit errors."""
        attempts = max(1, self._policy.retry_max_attempts)
        for attempt in range(1, attempts + 1):
            try:
                async with self._semaphore:
                    await self._wait_for_spacing()
                    return await func()
            except (ProviderRateLimitError, ProviderServiceUnavailableError):
                if attempt >= attempts:
                    raise

                base_delay = max(1, self._policy.retry_base_delay_ms)
                raw_delay = base_delay * (2 ** (attempt - 1))
                bounded_delay = min(
                    raw_delay, max(base_delay, self._policy.retry_max_delay_ms)
                )
                jitter = random.uniform(0.8, 1.25)
                await asyncio.sleep((bounded_delay / 1000) * jitter)
            except ProviderError:
                raise

        raise RuntimeError("Unreachable retry loop branch")


class ProviderRegistry:
    """Registry that holds all provider adapters and dispatches generation requests through their executors."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._adapters: dict[str, ProviderAdapter] = {}
        self._executors: dict[str, ProviderExecutor] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(StubAdapter())
        self.register(OpenAIAdapter())
        self.register(OpenRouterAdapter())
        self.register(GoogleAdapter())
        self.register(BFLAdapter())

    def register(self, adapter: ProviderAdapter) -> None:
        """Register *adapter* under its ``name`` attribute, replacing any existing entry."""
        self._adapters[adapter.name] = adapter

    def provider_names(self) -> list[str]:
        """Return a sorted list of all registered provider names."""
        return sorted(self._adapters.keys())

    def get(self, provider: str) -> ProviderAdapter:
        """Return the adapter for *provider*, raising ``ProviderError`` if unknown."""
        adapter = self._adapters.get(provider)
        if not adapter:
            raise ProviderError(f"Unknown provider: {provider}")
        return adapter

    def _build_policy(self, provider: str) -> ProviderPolicy:
        defaults = self._settings
        return ProviderPolicy(
            max_concurrent=int(
                getattr(
                    defaults,
                    f"provider_{provider}_max_concurrent",
                    defaults.provider_default_max_concurrent,
                )
            ),
            min_interval_ms=int(
                getattr(
                    defaults,
                    f"provider_{provider}_min_interval_ms",
                    defaults.provider_default_min_interval_ms,
                )
            ),
            retry_max_attempts=int(defaults.provider_default_retry_max_attempts),
            retry_base_delay_ms=int(defaults.provider_default_retry_base_delay_ms),
            retry_max_delay_ms=int(defaults.provider_default_retry_max_delay_ms),
        )

    def _executor_for(self, provider: str) -> ProviderExecutor:
        existing = self._executors.get(provider)
        if existing:
            return existing
        policy = self._build_policy(provider)
        executor = ProviderExecutor(policy)
        self._executors[provider] = executor
        return executor

    async def generate(
        self, provider: str, request: ProviderGenerationRequest
    ) -> ProviderGenerationResult:
        """Dispatch *request* to the named *provider* via its executor and return the result."""
        adapter = self.get(provider)
        settings = self._settings_for_provider(provider, request.api_key)
        executor = self._executor_for(provider)
        return await executor.run(lambda: adapter.generate(request, settings))

    async def list_models(self, provider: str) -> list[str]:
        """Return sorted, deduplicated model IDs available from *provider*."""
        adapter = self.get(provider)
        models = await adapter.list_models(self._settings_for_provider(provider, None))
        normalized = [str(item).strip() for item in models if str(item).strip()]
        return sorted(set(normalized))

    def _settings_for_provider(self, provider: str, api_key: str | None) -> Settings:
        if not api_key:
            return self._settings

        update: dict[str, str] = {}
        if provider == "openai":
            update["openai_api_key"] = api_key
        elif provider == "openrouter":
            update["openrouter_api_key"] = api_key
        elif provider == "google":
            update["google_api_key"] = api_key
        elif provider == "bfl":
            update["bfl_api_key"] = api_key
        else:
            return self._settings

        return self._settings.model_copy(update=update)
