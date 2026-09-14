"""Low-frequency inductance estimate of the heater trace by partial inductances:
self-inductance of every straight rectangular segment plus the signed mutual
inductance between every pair of parallel segments (Grover's filament
formula). Perpendicular segments have zero mutual inductance.

This is the loop inductance seen between the two pads if the external return
path contributes nothing (i.e. the partial inductance of the open path), which
is the usual figure for a meander heater.
"""
from __future__ import annotations

import math

MU0 = 4e-7 * math.pi
Point = tuple[float, float]


def self_inductance(length_m: float, width_m: float, thickness_m: float) -> float:
    """Straight rectangular bar (Grover / Ruehli), henries."""
    if length_m <= 0:
        return 0.0
    wt = width_m + thickness_m
    return MU0 * length_m / (2 * math.pi) * (math.log(2 * length_m / wt) + 0.5 + 0.2235 * wt / length_m)


def _f(x: float, d: float) -> float:
    return x * math.asinh(x / d) - math.sqrt(x * x + d * d)


def mutual_parallel(a1: float, b1: float, a2: float, b2: float, d_m: float) -> float:
    """Mutual inductance of two parallel filaments on lines separated by d,
    spanning [a1, b1] and [a2, b2] along the common axis (currents in the +axis
    direction), henries."""
    if d_m <= 0:
        raise ValueError("filaments must be separated")
    return MU0 / (4 * math.pi) * (_f(b1 - a2, d_m) + _f(a1 - b2, d_m) - _f(a1 - a2, d_m) - _f(b1 - b2, d_m))


def trace_inductance(segments: list[tuple[Point, Point]], width_mm: float, thickness_m: float) -> float:
    """Total partial inductance (H) of a polyline given as (start, end) segments
    in mm, traversed in order so current direction is start -> end."""
    width_m = width_mm * 1e-3
    horiz: list[tuple[float, float, float, int]] = []   # (y, x_start, x_end, dir)
    vert: list[tuple[float, float, float, int]] = []    # (x, y_start, y_end, dir)
    total = 0.0
    for (x0, y0), (x1, y1) in segments:
        dx, dy = (x1 - x0) * 1e-3, (y1 - y0) * 1e-3
        length = math.hypot(dx, dy)
        total += self_inductance(length, width_m, thickness_m)
        if abs(dy) < 1e-9:
            horiz.append((y0 * 1e-3, min(x0, x1) * 1e-3, max(x0, x1) * 1e-3, 1 if dx > 0 else -1))
        elif abs(dx) < 1e-9:
            vert.append((x0 * 1e-3, min(y0, y1) * 1e-3, max(y0, y1) * 1e-3, 1 if dy > 0 else -1))
        # diagonal segments (leads) only contribute their self-inductance
    for group in (horiz, vert):
        n = len(group)
        for i in range(n):
            ci, ai, bi, si = group[i]
            for j in range(i + 1, n):
                cj, aj, bj, sj = group[j]
                d = abs(ci - cj)
                if d < 1e-9:
                    # collinear: use the geometric-mean distance of the trace cross-section
                    d = 0.2235 * (width_m + thickness_m)
                total += 2 * si * sj * mutual_parallel(ai, bi, aj, bj, d)
    return total
