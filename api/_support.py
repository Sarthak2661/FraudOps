from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


def now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def json_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return list(value)
