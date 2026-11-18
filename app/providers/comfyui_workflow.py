"""ComfyUI workflow templates: built-in default graph, placeholder substitution and validation.

Workflows use ComfyUI's *API format* (``Save (API Format)`` / ``Export (API)`` in the
ComfyUI menu): a dict of ``node_id -> {"class_type": ..., "inputs": {...}}``.
String values may contain placeholders that Lumigen fills in per request:

``{{prompt}}``, ``{{negative_prompt}}``, ``{{seed}}``, ``{{width}}``, ``{{height}}``,
``{{batch_size}}``, ``{{model}}`` and ``{{input_image}}`` (uploaded reference image).

A value that consists of exactly one placeholder is replaced with the typed value
(``"{{seed}}"`` becomes the integer seed); placeholders inside longer strings are
interpolated as text.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

PLACEHOLDERS: tuple[str, ...] = (
    "prompt",
    "negative_prompt",
    "seed",
    "width",
    "height",
    "batch_size",
    "model",
    "input_image",
)

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
_EXACT_PLACEHOLDER_RE = re.compile(r"^\{\{\s*([a-z_]+)\s*\}\}$")


class WorkflowError(ValueError):
    """Raised when a workflow is not a usable ComfyUI API-format graph."""


#: Built-in text-to-image graph (checkpoint loader -> KSampler -> VAE decode -> save).
#: ``{{model}}`` is the model identifier of the model configuration (a checkpoint file name).
DEFAULT_WORKFLOW: dict[str, Any] = {
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": "{{seed}}",
            "steps": 25,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
    },
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "{{model}}"}},
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": "{{width}}", "height": "{{height}}", "batch_size": "{{batch_size}}"},
    },
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{prompt}}", "clip": ["4", 1]}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{negative_prompt}}", "clip": ["4", 1]}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "lumigen", "images": ["8", 0]}},
}


def parse_workflow(value: Any) -> dict[str, Any]:
    """Return a validated API-format workflow from a dict or JSON string.

    Raises ``WorkflowError`` with a user-facing message when the input is not JSON,
    is the UI (non-API) export format, or contains no ``{{prompt}}`` placeholder.
    """
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise WorkflowError("The workflow is empty.")
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"The workflow is not valid JSON (line {exc.lineno}: {exc.msg}).") from exc

    if not isinstance(value, dict) or not value:
        raise WorkflowError("The workflow must be a JSON object of nodes.")
    if "nodes" in value and "links" in value:
        raise WorkflowError(
            "This is the ComfyUI UI format. Export the workflow with \"Export (API)\" / \"Save (API Format)\" instead."
        )
    for node_id, node in value.items():
        if not isinstance(node, dict) or "class_type" not in node or not isinstance(node.get("inputs"), dict):
            raise WorkflowError(f"Node {node_id!r} is not an API-format node (needs class_type and inputs).")

    used = used_placeholders(value)
    if "prompt" not in used:
        raise WorkflowError("The workflow must contain the {{prompt}} placeholder in a text input.")
    unknown = sorted(used - set(PLACEHOLDERS))
    if unknown:
        raise WorkflowError(f"Unknown placeholder(s): {', '.join('{{' + name + '}}' for name in unknown)}.")
    return value


def used_placeholders(workflow: Any) -> set[str]:
    """Return the names of all placeholders that occur anywhere in *workflow*."""
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            found.update(match.group(1) for match in _PLACEHOLDER_RE.finditer(node))

    walk(workflow)
    return found


def fill_workflow(workflow: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of *workflow* with all placeholders replaced by *values*."""

    def substitute(node: Any) -> Any:
        if isinstance(node, dict):
            return {key: substitute(item) for key, item in node.items()}
        if isinstance(node, list):
            return [substitute(item) for item in node]
        if isinstance(node, str):
            exact = _EXACT_PLACEHOLDER_RE.match(node)
            if exact and exact.group(1) in values:
                return values[exact.group(1)]
            return _PLACEHOLDER_RE.sub(
                lambda match: str(values.get(match.group(1), match.group(0))), node
            )
        return node

    return substitute(copy.deepcopy(workflow))
