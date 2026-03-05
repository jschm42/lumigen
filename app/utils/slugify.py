from __future__ import annotations

import re
import unicodedata

_INVALID_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_length: int = 64, fallback: str = "untitled") -> str:
    # Normalize Unicode characters (decompose accented characters)
    normalized = unicodedata.normalize("NFKD", text)
    # Filter to only ASCII characters - avoids encoding errors
    ascii_text = "".join(c for c in normalized if ord(c) < 128)
    lowered = ascii_text.lower().strip()
    slug = _INVALID_RE.sub("-", lowered).strip("-")
    slug = slug[:max_length].strip("-")
    return slug or fallback
