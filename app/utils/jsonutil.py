from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


def _default_encoder(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Path):
        return value.as_posix()
    return str(value)


def dumps_json(payload: Any, *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(payload, default=_default_encoder, ensure_ascii=False, indent=2, sort_keys=True)
    return json.dumps(payload, default=_default_encoder, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
