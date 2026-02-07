from __future__ import annotations

import re
import unicodedata


_INVALID_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_length: int = 64, fallback: str = "untitled") -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    lowered = normalized.lower().strip()
    slug = _INVALID_RE.sub("-", lowered).strip("-")
    slug = slug[:max_length].strip("-")
    return slug or fallback
