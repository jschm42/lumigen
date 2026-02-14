from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import Settings


@dataclass
class ProviderGenerationRequest:
    prompt: str
    width: Optional[int]
    height: Optional[int]
    n_images: int
    seed: Optional[int]
    output_format: str
    model: str
    api_key: Optional[str] = None
    params: dict[str, Any] = field(default_factory=dict)
    input_images: list["ProviderInputImage"] = field(default_factory=list)


@dataclass
class ProviderInputImage:
    data: bytes
    mime: str


@dataclass
class ProviderImage:
    data: bytes
    mime: str
    width: int
    height: int
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderGenerationResult:
    images: list[ProviderImage]
    raw_meta: dict[str, Any] = field(default_factory=dict)


class ProviderError(RuntimeError):
    pass


class ProviderConfigError(ProviderError):
    pass


class ProviderRateLimitError(ProviderError):
    pass


class ProviderServiceUnavailableError(ProviderError):
    pass


class ProviderAdapter(ABC):
    name: str

    @abstractmethod
    async def generate(
        self, request: ProviderGenerationRequest, settings: Settings
    ) -> ProviderGenerationResult:
        raise NotImplementedError

    async def list_models(self, settings: Settings) -> list[str]:
        return []
