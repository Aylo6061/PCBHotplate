"""Copper resistance helpers."""
from __future__ import annotations

import math

CU_RESISTIVITY = 1.72e-8      # ohm*m at 20 C
OZ_THICKNESS_M = 34.79e-6     # 1 oz/ft^2 copper thickness
CU_TCR = 0.00393              # per degree C


def sheet_resistance(copper_oz: float) -> float:
    """Ohms per square for the given copper weight (at 20 C)."""
    return CU_RESISTIVITY / (copper_oz * OZ_THICKNESS_M)


def resistance(length_mm: float, width_mm: float, copper_oz: float, temp_c: float = 20.0) -> float:
    if width_mm <= 0:
        return math.inf
    r20 = sheet_resistance(copper_oz) * length_mm / width_mm
    return r20 * (1 + CU_TCR * (temp_c - 20.0))


def solve_width(area_mm2: float, space_mm: float, target_ohms: float, copper_oz: float) -> float:
    """Trace width that hits `target_ohms` assuming the trace fills `area_mm2`
    with pitch (w + s):  R = Rsq * L / w,  L ~ A / (w + s)
    => w^2 + s*w - Rsq*A/R = 0."""
    rsq = sheet_resistance(copper_oz)
    k = rsq * area_mm2 / target_ohms
    return (-space_mm + math.sqrt(space_mm * space_mm + 4 * k)) / 2


def rescale_width(width_mm: float, space_mm: float, r_actual: float, r_target: float) -> float:
    """Given a generated trace of width w with resistance r_actual, return the
    width that would hit r_target (R is proportional to 1/(w*(w+s)))."""
    k = width_mm * (width_mm + space_mm) * r_actual / r_target
    return (-space_mm + math.sqrt(space_mm * space_mm + 4 * k)) / 2
