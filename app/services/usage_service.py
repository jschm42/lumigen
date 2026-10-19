"""Normalize provider token usage and compute costs from configured model prices."""
from __future__ import annotations

from typing import Any

_INPUT_KEYS = ("prompt_tokens", "input_tokens", "promptTokenCount")
_OUTPUT_KEYS = ("completion_tokens", "output_tokens", "candidatesTokenCount")
_TOTAL_KEYS = ("total_tokens", "totalTokenCount")
_PRICE_KEYS = ("input_per_mtok", "output_per_mtok", "per_image")


def _first_int(source: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = source.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
    return None


def _price(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value >= 0 else None


def extract_tokens(raw_meta: dict[str, Any] | None) -> dict[str, int | None] | None:
    """Return ``input_tokens``/``output_tokens``/``total_tokens`` from provider ``raw_meta``.

    Supports OpenRouter/OpenAI (``usage``) and Gemini (``usageMetadata`` stored under
    ``usage``). Returns ``None`` when the provider reported no token counts.
    """
    if not isinstance(raw_meta, dict):
        return None
    usage = raw_meta.get("usage")
    if not isinstance(usage, dict):
        return None
    tokens = {
        "input_tokens": _first_int(usage, _INPUT_KEYS),
        "output_tokens": _first_int(usage, _OUTPUT_KEYS),
        "total_tokens": _first_int(usage, _TOTAL_KEYS),
    }
    if tokens["total_tokens"] is None and (
        tokens["input_tokens"] is not None or tokens["output_tokens"] is not None
    ):
        tokens["total_tokens"] = (tokens["input_tokens"] or 0) + (tokens["output_tokens"] or 0)
    if all(value is None for value in tokens.values()):
        return None
    return tokens


def build_pricing(
    *,
    input_per_mtok: Any,
    output_per_mtok: Any,
    per_image: Any,
    currency: str,
) -> dict[str, Any] | None:
    """Return a pricing snapshot dict, or ``None`` when no price is configured."""
    prices = {
        "input_per_mtok": _price(input_per_mtok),
        "output_per_mtok": _price(output_per_mtok),
        "per_image": _price(per_image),
    }
    if all(value is None for value in prices.values()):
        return None
    return {**prices, "currency": currency}


def compute_usage(
    raw_meta: dict[str, Any] | None,
    pricing: dict[str, Any] | None,
    image_count: int,
) -> dict[str, Any] | None:
    """Combine reported tokens with configured prices into one usage dict.

    ``cost`` is only set when prices are configured; without prices only the tokens are
    returned. Token prices are per one million tokens, ``per_image`` per generated image.
    Returns ``None`` when there are neither tokens nor a cost.
    """
    tokens = extract_tokens(raw_meta)
    result: dict[str, Any] = {
        "input_tokens": tokens["input_tokens"] if tokens else None,
        "output_tokens": tokens["output_tokens"] if tokens else None,
        "total_tokens": tokens["total_tokens"] if tokens else None,
        "cost": None,
        "currency": None,
    }

    if isinstance(pricing, dict) and any(_price(pricing.get(key)) is not None for key in _PRICE_KEYS):
        cost = 0.0
        priced = False
        input_price = _price(pricing.get("input_per_mtok"))
        output_price = _price(pricing.get("output_per_mtok"))
        image_price = _price(pricing.get("per_image"))
        if tokens and input_price is not None and tokens["input_tokens"] is not None:
            cost += tokens["input_tokens"] * input_price / 1_000_000
            priced = True
        if tokens and output_price is not None and tokens["output_tokens"] is not None:
            cost += tokens["output_tokens"] * output_price / 1_000_000
            priced = True
        if image_price is not None and image_count > 0:
            cost += image_count * image_price
            priced = True
        if priced:
            result["cost"] = round(cost, 6)
            result["currency"] = str(pricing.get("currency") or "USD")

    if tokens is None and result["cost"] is None:
        return None
    return result


def sum_usage(items: list[dict[str, Any] | None]) -> dict[str, Any] | None:
    """Add up usage dicts; costs are only summed when all share the same currency."""
    present = [item for item in items if item]
    if not present:
        return None
    total: dict[str, Any] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost": None,
        "currency": None,
    }
    for item in present:
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            total[key] += int(item.get(key) or 0)
        cost = item.get("cost")
        if cost is None:
            continue
        currency = item.get("currency")
        if total["currency"] in (None, currency):
            total["currency"] = currency
            total["cost"] = round((total["cost"] or 0.0) + float(cost), 6)
        else:
            total["currency"] = "mixed"
    if total["currency"] == "mixed":
        total["cost"] = None
    return total
