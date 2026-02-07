from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import Settings


@dataclass
class ProviderGenerationRequest:
    prompt: str
    negative_prompt: Optional[str]
    width: Optional[int]
    height: Optional[int]
    aspect_ratio: Optional[str]
    n_images: int
    seed: Optional[int]
    output_format: str
    model: str
    params: dict[str, Any] = field(default_factory=dict)


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
    async def generate(self, request: ProviderGenerationRequest, settings: Settings) -> ProviderGenerationResult:
        raise NotImplementedError

    async def list_models(self, settings: Settings) -> list[str]:
        return []
