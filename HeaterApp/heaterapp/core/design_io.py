"""Save / load a Design as JSON."""
from __future__ import annotations

import json

from .model import Design


def save_design(path: str, design: Design) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(design.to_dict(), f, indent=2)


def load_design(path: str) -> Design:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "params" not in data:
        raise ValueError("Not a HeaterApp design file")
    return Design.from_dict(data)
