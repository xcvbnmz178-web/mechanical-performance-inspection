"""Inspection staff catalog loaded from an optional local file."""

import json
from pathlib import Path


def _load_local_staff():
    path = Path(__file__).with_name("staff.local.json")
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    return [dict(item) for item in data if isinstance(item, dict)] if isinstance(data, list) else []


STAFF_LIST = _load_local_staff()
