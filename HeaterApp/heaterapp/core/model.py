"""Data model for a heater design. All dimensions are millimetres, KiCad
convention (y grows downwards)."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Rect:
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0

    @staticmethod
    def from_corners(x1: float, y1: float, x2: float, y2: float) -> "Rect":
        return Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    @property
    def area(self) -> float:
        return self.w * self.h

    def is_valid(self) -> bool:
        return self.w > 0 and self.h > 0

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px <= self.x2 and self.y <= py <= self.y2

    def intersects_box(self, x1: float, y1: float, x2: float, y2: float) -> bool:
        """Open-interval overlap test against an axis-aligned box (touching edges
        do not count as intersecting)."""
        return self.x < x2 and self.x2 > x1 and self.y < y2 and self.y2 > y1

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Rect":
        return Rect(float(d["x"]), float(d["y"]), float(d["w"]), float(d["h"]))


@dataclass
class Params:
    min_width: float = 0.75       # mm, minimum trace width
    min_space: float = 0.19       # mm, minimum trace-to-trace / trace-to-keepout gap
    copper_oz: float = 1.0        # copper weight
    target_ohms: Optional[float] = 6.5  # None => just use min_width
    op_temp_c: float = 100.0      # temperature at which to also report resistance
    pad_w: float = 2.0
    pad_h: float = 2.0
    snap_mm: float = 0.5
    orientation: str = "horizontal"   # "horizontal" (long runs along X) or "vertical"
    name: str = "Heater"
    # analysis tab (power supply + thermal environment)
    amb_temp_c: float = 25.0
    supply_v: float = 24.0
    supply_i: float = 2.0
    compliance_v: float = 30.0
    emissivity: float = 0.9
    board_thickness_mm: float = 1.6
    extra_loss_w_per_k: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Params":
        p = Params()
        for k, v in d.items():
            if hasattr(p, k):
                setattr(p, k, v)
        if p.target_ohms is not None:
            p.target_ohms = float(p.target_ohms)
        return p


@dataclass
class Design:
    heater: Optional[Rect] = None
    board: Optional[Rect] = None      # PCB outline; None => same as the heater rectangle
    keepouts: list[Rect] = field(default_factory=list)
    pad_a: Optional[tuple[float, float]] = None
    pad_b: Optional[tuple[float, float]] = None
    params: Params = field(default_factory=Params)

    def board_rect(self) -> Optional[Rect]:
        """The PCB outline actually in effect (explicit board, else the heater)."""
        if self.board is not None and self.board.is_valid():
            return self.board
        return self.heater

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "heater": self.heater.to_dict() if self.heater else None,
            "board": self.board.to_dict() if self.board else None,
            "keepouts": [k.to_dict() for k in self.keepouts],
            "pad_a": list(self.pad_a) if self.pad_a else None,
            "pad_b": list(self.pad_b) if self.pad_b else None,
            "params": self.params.to_dict(),
        }

    @staticmethod
    def from_dict(d: dict) -> "Design":
        des = Design()
        if d.get("heater"):
            des.heater = Rect.from_dict(d["heater"])
        if d.get("board"):
            des.board = Rect.from_dict(d["board"])
        des.keepouts = [Rect.from_dict(k) for k in d.get("keepouts", [])]
        if d.get("pad_a"):
            des.pad_a = (float(d["pad_a"][0]), float(d["pad_a"][1]))
        if d.get("pad_b"):
            des.pad_b = (float(d["pad_b"][0]), float(d["pad_b"][1]))
        des.params = Params.from_dict(d.get("params", {}))
        return des
