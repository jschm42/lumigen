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


def test_registry_provider_names_and_unknown_provider() -> None:
    settings = Settings()
    registry = ProviderRegistry(settings)

    names = registry.provider_names()
    assert "stub" in names
    assert "openai" in names

    with pytest.raises(ProviderError, match="Unknown provider"):
        registry.get("does-not-exist")


def test_registry_build_policy_uses_provider_specific_settings() -> None:
    settings = Settings(provider_stub_max_concurrent=9, provider_stub_min_interval_ms=777)
    registry = ProviderRegistry(settings)

    policy = registry._build_policy("stub")
    assert policy.max_concurrent == 9
    assert policy.min_interval_ms == 777
    assert policy.retry_max_attempts == settings.provider_default_retry_max_attempts


def test_registry_executor_cached_per_provider() -> None:
    settings = Settings()
    registry = ProviderRegistry(settings)

    e1 = registry._executor_for("stub")
    e2 = registry._executor_for("stub")
    e3 = registry._executor_for("openai")

    assert e1 is e2
    assert e1 is not e3


@pytest.mark.asyncio
async def test_provider_executor_wait_for_spacing_respects_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = ProviderPolicy(
        max_concurrent=1,
        min_interval_ms=100,
        retry_max_attempts=1,
        retry_base_delay_ms=100,
        retry_max_delay_ms=500,
    )
    executor = ProviderExecutor(policy)
    sleep_calls: list[float] = []
    monotonic_values = [1.00, 1.10]
    monotonic_index = {"value": 0}

    async def fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)

    def fake_monotonic() -> float:
        idx = monotonic_index["value"]
        if idx < len(monotonic_values):
            monotonic_index["value"] += 1
            return monotonic_values[idx]
        return monotonic_values[-1]

    monkeypatch.setattr("app.providers.registry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.providers.registry.time.monotonic", fake_monotonic)
    executor._last_started_at = 1.00

    await executor._wait_for_spacing()

    assert sleep_calls and abs(sleep_calls[0] - 0.10) < 1e-6


class _GenerateAdapter(ProviderAdapter):
    name = "openai"

    def __init__(self) -> None:
        self.captured_settings = None
        self.captured_request = None

    async def generate(
        self, request: ProviderGenerationRequest, settings: Settings
    ) -> ProviderGenerationResult:
        self.captured_request = request
        self.captured_settings = settings
        return ProviderGenerationResult(images=[])


@pytest.mark.asyncio
async def test_registry_generate_passes_request_and_custom_api_key() -> None:
    settings = Settings()
    registry = ProviderRegistry(settings)
    adapter = _GenerateAdapter()
    registry.register(adapter)

    request = ProviderGenerationRequest(
        prompt="p",
        width=512,
        height=512,
        n_images=1,
        seed=None,
        output_format="png",
        model="m",
        api_key="custom-openai-key",
    )

    result = await registry.generate("openai", request)

    assert isinstance(result, ProviderGenerationResult)
    assert adapter.captured_request is request
    assert adapter.captured_settings is not None
    assert adapter.captured_settings.openai_api_key == "custom-openai-key"
