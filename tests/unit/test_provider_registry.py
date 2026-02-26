from __future__ import annotations

import pytest

from app.config import Settings
from app.providers.base import (
    ProviderAdapter,
    ProviderError,
    ProviderGenerationRequest,
    ProviderGenerationResult,
    ProviderRateLimitError,
)
from app.providers.registry import ProviderExecutor, ProviderPolicy, ProviderRegistry


@pytest.mark.asyncio
async def test_provider_executor_retries_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = ProviderPolicy(
        max_concurrent=1,
        min_interval_ms=0,
        retry_max_attempts=3,
        retry_base_delay_ms=100,
        retry_max_delay_ms=500,
    )
    executor = ProviderExecutor(policy)
    attempts = {"count": 0}
    sleep_calls: list[float] = []

    async def fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)

    monkeypatch.setattr("app.providers.registry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.providers.registry.random.uniform", lambda _a, _b: 1.0)

    async def flaky_call() -> ProviderGenerationResult:
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise ProviderRateLimitError("retry")
        return ProviderGenerationResult(images=[])

    result = await executor.run(flaky_call)

    assert attempts["count"] == 2
    assert isinstance(result, ProviderGenerationResult)
    assert sleep_calls == [0.1]


@pytest.mark.asyncio
async def test_provider_executor_does_not_retry_generic_provider_error() -> None:
    policy = ProviderPolicy(
        max_concurrent=1,
        min_interval_ms=0,
        retry_max_attempts=4,
        retry_base_delay_ms=100,
        retry_max_delay_ms=500,
    )
    executor = ProviderExecutor(policy)
    attempts = {"count": 0}

    async def always_fail() -> ProviderGenerationResult:
        attempts["count"] += 1
        raise ProviderError("boom")

    with pytest.raises(ProviderError):
        await executor.run(always_fail)

    assert attempts["count"] == 1


class _ModelsAdapter(ProviderAdapter):
    name = "demo"

    async def generate(
        self, request: ProviderGenerationRequest, settings: Settings
    ) -> ProviderGenerationResult:
        _ = request, settings
        return ProviderGenerationResult(images=[])

    async def list_models(self, settings: Settings) -> list[str]:
        _ = settings
        return [" z ", "a", "", "a", "  "]


@pytest.mark.asyncio
async def test_registry_list_models_normalizes_and_deduplicates() -> None:
    settings = Settings()
    registry = ProviderRegistry(settings)
    registry.register(_ModelsAdapter())

    models = await registry.list_models("demo")
    assert models == ["a", "z"]


def test_registry_settings_for_provider_applies_custom_api_key() -> None:
    settings = Settings()
    registry = ProviderRegistry(settings)

    overridden = registry._settings_for_provider("openai", "test-key")
    unchanged = registry._settings_for_provider("stub", "test-key")

    assert overridden is not settings
    assert overridden.openai_api_key == "test-key"
    assert unchanged is settings
