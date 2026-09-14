"""Steady-state / transient thermal estimate of the heater plate under
constant-voltage, PWM and constant-current drive.

Model: a lumped, isothermal plate of area A (the heater rectangle) losing heat
from both faces by natural convection (flat-plate correlations) and grey-body
radiation, plus an optional linear "extra" loss for mounts and wiring.  The
heater resistance follows copper's TCR.  See ASSUMPTIONS for the caveats
shown to the user.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from . import resistance as res

SIGMA = 5.670374e-8      # Stefan-Boltzmann, W/m^2K^4
G = 9.80665
FR4_DENSITY = 1850.0     # kg/m^3
FR4_CP = 1100.0          # J/kgK
CU_DENSITY = 8960.0
CU_CP = 385.0
T_LIMIT_C = 1500.0       # search ceiling for the equilibrium solve

MODES = ("Constant voltage", "PWM voltage", "Constant current")
ORIENTATIONS = ("Flat (heater up)", "Vertical")

# Dry air at 1 atm: T [K] -> (k [W/mK], nu [m^2/s], Pr)
_AIR = (
    (250.0, 0.0223, 1.140e-5, 0.720),
    (300.0, 0.0263, 1.589e-5, 0.707),
    (350.0, 0.0300, 2.092e-5, 0.700),
    (400.0, 0.0338, 2.641e-5, 0.690),
    (450.0, 0.0373, 3.239e-5, 0.686),
    (500.0, 0.0407, 3.855e-5, 0.684),
    (600.0, 0.0469, 5.219e-5, 0.685),
    (700.0, 0.0524, 6.690e-5, 0.695),
    (800.0, 0.0573, 8.230e-5, 0.709),
    (900.0, 0.0620, 9.870e-5, 0.720),
    (1000.0, 0.0667, 1.159e-4, 0.726),
)


def air_properties(t_k: float) -> tuple[float, float, float]:
    """Linear interpolation of (k, nu, Pr); clamped to the table range."""
    if t_k <= _AIR[0][0]:
        return _AIR[0][1:]
    for (t0, k0, n0, p0), (t1, k1, n1, p1) in zip(_AIR, _AIR[1:]):
        if t_k <= t1:
            f = (t_k - t0) / (t1 - t0)
            return k0 + f * (k1 - k0), n0 + f * (n1 - n0), p0 + f * (p1 - p0)
    return _AIR[-1][1:]


@dataclass
class Plate:
    width_m: float
    height_m: float
    r20: float               # heater resistance at 20 C
    t_amb_c: float = 25.0
    emissivity: float = 0.9
    board_thickness_m: float = 1.6e-3
    extra_loss_w_per_k: float = 0.0
    copper_mass_kg: float = 0.0

    @property
    def area(self) -> float:
        return self.width_m * self.height_m

    def resistance(self, t_c: float) -> float:
        return self.r20 * (1 + res.CU_TCR * (t_c - 20.0))

    def heat_capacity(self) -> float:
        return self.area * self.board_thickness_m * FR4_DENSITY * FR4_CP + self.copper_mass_kg * CU_CP


# --------------------------------------------------------------------- losses

def _nusselt_flat_up(ra: float) -> float:
    """Hot surface facing up (or cold facing down)."""
    if ra < 1e7:
        return 0.54 * ra ** 0.25
    return 0.15 * ra ** (1 / 3)


def _nusselt_flat_down(ra: float) -> float:
    """Hot surface facing down."""
    return 0.27 * ra ** 0.25


def _nusselt_vertical(ra: float) -> float:
    if ra < 1e9:
        return 0.59 * ra ** 0.25
    return 0.10 * ra ** (1 / 3)


def convection_coefficients(plate: Plate, t_c: float, orientation: str) -> tuple[float, float]:
    """(h_face1, h_face2) in W/m^2K for the two faces at plate temperature t_c."""
    dt = max(t_c - plate.t_amb_c, 1e-6)
    t_film = (t_c + plate.t_amb_c) / 2 + 273.15
    k, nu, pr = air_properties(t_film)
    beta = 1 / t_film
    alpha = nu / pr

    def rayleigh(length: float) -> float:
        return G * beta * dt * length ** 3 / (nu * alpha)

    if orientation == ORIENTATIONS[1]:  # vertical: the shorter side stands vertical
        length = min(plate.width_m, plate.height_m)
        h = _nusselt_vertical(rayleigh(length)) * k / length
        return h, h
    perimeter = 2 * (plate.width_m + plate.height_m)
    length = plate.area / perimeter
    ra = rayleigh(length)
    return _nusselt_flat_up(ra) * k / length, _nusselt_flat_down(ra) * k / length


@dataclass
class LossBreakdown:
    convection_w: float
    radiation_w: float
    extra_w: float
    h_face1: float
    h_face2: float

    @property
    def total(self) -> float:
        return self.convection_w + self.radiation_w + self.extra_w


def loss_breakdown(plate: Plate, t_c: float, orientation: str) -> LossBreakdown:
    dt = t_c - plate.t_amb_c
    if dt <= 0:
        return LossBreakdown(0.0, 0.0, 0.0, 0.0, 0.0)
    h1, h2 = convection_coefficients(plate, t_c, orientation)
    conv = (h1 + h2) * plate.area * dt
    t_k, ta_k = t_c + 273.15, plate.t_amb_c + 273.15
    rad = 2 * plate.emissivity * SIGMA * plate.area * (t_k ** 4 - ta_k ** 4)
    return LossBreakdown(conv, rad, plate.extra_loss_w_per_k * dt, h1, h2)


def power_loss(plate: Plate, t_c: float, orientation: str) -> float:
    return loss_breakdown(plate, t_c, orientation).total


# ---------------------------------------------------------------------- drive

@dataclass
class Supply:
    mode: str                  # one of MODES
    voltage: float = 24.0      # CV / PWM supply voltage
    current: float = 2.0       # CC set point
    compliance_v: float = 30.0 # CC supply voltage limit
    duty: float = 1.0          # PWM duty (1.0 for the T_max solve)

    def power_in(self, plate: Plate, t_c: float) -> float:
        r = plate.resistance(t_c)
        if self.mode == MODES[2]:
            v = min(self.current * r, self.compliance_v)
            return v * v / r
        p = self.voltage ** 2 / r
        return p * self.duty if self.mode == MODES[1] else p

    def current_at(self, plate: Plate, t_c: float, duty: float = 1.0) -> float:
        r = plate.resistance(t_c)
        if self.mode == MODES[2]:
            return min(self.current, self.compliance_v / r)
        return self.voltage / r * (duty if self.mode == MODES[1] else 1.0)


# --------------------------------------------------------------------- solves

def steady_state(plate: Plate, supply: Supply, orientation: str) -> tuple[float, bool]:
    """(T_max in C, runaway).  runaway=True means power in still exceeds loss
    at T_LIMIT_C (constant current with a high compliance voltage)."""
    def f(t: float) -> float:
        return supply.power_in(plate, t) - power_loss(plate, t, orientation)

    lo, hi = plate.t_amb_c, T_LIMIT_C
    if f(lo) <= 0:
        return lo, False
    if f(hi) > 0:
        return hi, True
    for _ in range(80):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2, False


def time_to_temperature(plate: Plate, supply: Supply, orientation: str, t_target_c: float,
                        t_max_s: float = 3600.0, dt_s: float = 0.2) -> Optional[float]:
    """Explicit-Euler warm-up time from ambient to t_target_c, or None if it is
    not reached within t_max_s."""
    c = plate.heat_capacity()
    t = plate.t_amb_c
    elapsed = 0.0
    while elapsed < t_max_s:
        p = supply.power_in(plate, t) - power_loss(plate, t, orientation)
        if p <= 0 and t < t_target_c:
            return None
        t += p / c * dt_s
        elapsed += dt_s
        if t >= t_target_c:
            return elapsed
    return None


@dataclass
class Analysis:
    mode: str
    orientation: str
    t_max_c: float
    runaway: bool
    reaches: bool
    p_needed_w: float          # loss at T_design
    p_available_w: float       # power in at T_design (full duty for PWM)
    duty_at_design: Optional[float]   # PWM only
    i_at_design: float
    v_at_design: float
    i_inrush: float            # current at ambient (CV/PWM at full duty)
    time_to_design_s: Optional[float]
    tau_s: float               # thermal time constant near T_design
    losses: LossBreakdown      # at T_design


def analyse(plate: Plate, supply: Supply, orientation: str, t_design_c: float) -> Analysis:
    full = Supply(supply.mode, supply.voltage, supply.current, supply.compliance_v, 1.0)
    t_max, runaway = steady_state(plate, full, orientation)
    losses = loss_breakdown(plate, t_design_c, orientation)
    p_needed = losses.total
    p_avail = full.power_in(plate, t_design_c)
    reaches = runaway or t_max >= t_design_c
    duty = None
    if supply.mode == MODES[1]:
        duty = p_needed / p_avail if p_avail > 0 else math.inf
    r_design = plate.resistance(t_design_c)
    if supply.mode == MODES[2]:
        i_design = min(supply.current, supply.compliance_v / r_design)
        v_design = i_design * r_design
    else:
        v_design = supply.voltage
        i_design = supply.voltage / r_design
        if duty is not None:
            i_design *= min(duty, 1.0)  # average current at the holding duty
    i_inrush = full.current_at(plate, plate.t_amb_c)
    t_time = time_to_temperature(plate, full, orientation, t_design_c) if reaches else None
    # thermal time constant: C / (dP_loss/dT)
    d = 1.0
    dpdt = (power_loss(plate, t_design_c + d, orientation) - power_loss(plate, t_design_c - d, orientation)) / (2 * d)
    tau = plate.heat_capacity() / dpdt if dpdt > 0 else math.inf
    return Analysis(supply.mode, orientation, t_max, runaway, reaches, p_needed, p_avail, duty,
                    i_design, v_design, i_inrush, t_time, tau, losses)


def analyse_all(plate: Plate, supply_v: float, supply_i: float, compliance_v: float,
                t_design_c: float) -> list[Analysis]:
    out = []
    for mode in MODES:
        sup = Supply(mode, supply_v, supply_i, compliance_v)
        for orientation in ORIENTATIONS:
            out.append(analyse(plate, sup, orientation, t_design_c))
    return out


ASSUMPTIONS = """\
• The board is a lumped, isothermal plate the size of the PCB outline (Design tab; the heater rectangle if none \
is set). Heat leaves from BOTH faces (FR4 is thin, so top and bottom are taken to be at the same temperature). \
A board much larger than the heater will not really be isothermal, so its edges lose less than assumed. \
Standoffs and the object being heated are not modelled except through "Extra loss".
• Convection: natural (still-air) flat-plate correlations with air properties at the film temperature. \
Flat: hot face up Nu = 0.54·Ra¼ (0.15·Ra⅓ above Ra 10⁷), hot face down Nu = 0.27·Ra¼, L = area/perimeter. \
Vertical: Nu = 0.59·Ra¼ (0.10·Ra⅓ above Ra 10⁹) on both faces, L = the shorter side (assumed to stand vertical). \
Any draft or fan raises losses well beyond this; an enclosure or insulation lowers them.
• Radiation: grey body to surroundings at ambient, both faces, P = 2·ε·σ·A·(T⁴ − T_amb⁴). Solder mask / FR4 ε ≈ 0.9, \
bare or HASL copper ε ≈ 0.05–0.3. At hot-plate temperatures radiation is about as large as convection.
• Heater resistance follows copper's TCR (0.393 %/°C) from R at 20 °C of the generated trace.
• Constant voltage: P = V²/R(T). PWM: average power D·V²/R(T) (switching assumed fast compared with the thermal \
time constant); the duty shown is what holds the design temperature, T_max is at 100 % duty. Constant current: \
P = I²·R(T) until the supply hits its compliance voltage, then it behaves as constant voltage. Supplies are \
otherwise ideal; wiring resistance is ignored.
• T_max is where power in equals power out. "Reaches" means T_max ≥ design temperature. "Runaway" means constant \
current still out-powers the losses at 1500 °C (only the compliance limit or the copper failing would stop it).
• Warm-up time integrates dT/dt = (P_in − P_loss)/C with C from FR4 (1.6 mm default, 1850 kg/m³, 1100 J/kg·K) plus \
the copper trace; the thermal mass of whatever sits on the plate is not included, so real warm-up is slower.
• Expect roughly ±20 % on power and ±15–25 °C on T_max in still air; treat the results as a sizing guide, not a spec.\
"""
