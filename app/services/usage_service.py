"""Normalize provider-specific token/cost usage metadata into one shape."""
from __future__ import annotations

from typing import Any

_INPUT_KEYS = ("prompt_tokens", "input_tokens", "promptTokenCount")
_OUTPUT_KEYS = ("completion_tokens", "output_tokens", "candidatesTokenCount")
_TOTAL_KEYS = ("total_tokens", "totalTokenCount")


def _first_int(source: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = source.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
    return None


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def extract_usage(raw_meta: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return normalized usage from a provider ``raw_meta`` dict, or ``None`` if absent.

    The result contains ``input_tokens``, ``output_tokens``, ``total_tokens`` (ints or
    ``None``) plus ``cost`` and ``cost_unit`` (``"usd"`` for OpenRouter, ``"credits"`` for
    BFL). Supports OpenRouter/OpenAI (``usage``), Gemini (``usageMetadata`` keys stored
    under ``usage``) and BFL (top-level ``cost``).
    """
    if not isinstance(raw_meta, dict):
        return None

    result: dict[str, Any] = {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "cost": None,
        "cost_unit": None,
    }

    usage = raw_meta.get("usage")
    if isinstance(usage, dict):
        result["input_tokens"] = _first_int(usage, _INPUT_KEYS)
        result["output_tokens"] = _first_int(usage, _OUTPUT_KEYS)
        result["total_tokens"] = _first_int(usage, _TOTAL_KEYS)
        cost = _as_number(usage.get("cost"))
        if cost is not None:
            result["cost"] = cost
            result["cost_unit"] = "usd"

    if result["cost"] is None:
        cost = _as_number(raw_meta.get("cost"))
        if cost is not None:
            result["cost"] = cost
            result["cost_unit"] = "credits"

    if result["total_tokens"] is None and (
        result["input_tokens"] is not None or result["output_tokens"] is not None
    ):
        result["total_tokens"] = (result["input_tokens"] or 0) + (result["output_tokens"] or 0)

    if all(result[key] is None for key in ("input_tokens", "output_tokens", "total_tokens", "cost")):
        return None
    return result


def sum_usage(items: list[dict[str, Any] | None]) -> dict[str, Any] | None:
    """Add up a list of normalized usage dicts; costs are only summed per matching unit."""
    present = [item for item in items if item]
    if not present:
        return None
    total: dict[str, Any] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost": None,
        "cost_unit": None,
    }
    for item in present:
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            total[key] += int(item.get(key) or 0)
        cost = item.get("cost")
        if cost is None:
            continue
        unit = item.get("cost_unit")
        if total["cost_unit"] in (None, unit):
            total["cost_unit"] = unit
            total["cost"] = (total["cost"] or 0.0) + float(cost)
        else:
            total["cost_unit"] = "mixed"
    if total["cost_unit"] == "mixed":
        total["cost"] = None
    return total
