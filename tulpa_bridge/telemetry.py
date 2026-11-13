"""Parse telemetry emitted by Tulpa's ``tlm::`` module (``@@tlm {json}`` lines)."""

from __future__ import annotations

import json
from typing import Optional

PREFIX = "@@tlm "


def parse(line: str) -> Optional[dict]:
    """Return the telemetry record for a ``@@tlm`` line, else ``None``."""
    if not line.startswith(PREFIX):
        return None
    try:
        rec = json.loads(line[len(PREFIX):])
    except json.JSONDecodeError:
        return None
    return rec if isinstance(rec, dict) else None


def scalars(rec: dict) -> list[tuple[str, float, float]]:
    """Flatten a plot record into ``(series, t, value)`` triples (lists become name[i])."""
    if rec.get("k") != "plot":
        return []
    name, t, v = rec.get("name", "?"), float(rec.get("t", 0.0)), rec.get("v")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return [(name, t, float(v))]
    if isinstance(v, list):
        return [(f"{name}[{i}]", t, float(x)) for i, x in enumerate(v) if isinstance(x, (int, float))]
    if isinstance(v, dict):
        return [(f"{name}.{k}", t, float(x)) for k, x in v.items() if isinstance(x, (int, float))]
    return []
