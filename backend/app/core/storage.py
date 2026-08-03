from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings


def _path(name: str) -> Path:
    return settings.data_dir / name


def read_json(name: str, default: Any):
    p = _path(name)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(name: str, obj: Any) -> None:
    p = _path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
