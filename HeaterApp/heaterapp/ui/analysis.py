"""Analysis tab: can the heater reach the design temperature under constant
voltage / PWM / constant current, flat or vertical, and what is T_max."""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QDoubleSpinBox, QGridLayout, QGroupBox, QHeaderView, QLabel,
                               QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import resistance as res, thermal as th
from ..core.generator import GenResult
from ..core.model import Design
from . import theme

log = logging.getLogger("heaterapp.ui.analysis")

COLUMNS = ("Mode", "Board", "T max", "Reaches\nT design", "P needed /\navailable", "I design /\ninrush", "Warm-up")
TOOLTIPS = (
    "Drive mode: CV = constant voltage, PWM = the same voltage switched with a duty cycle, "
    "CC = constant current with a compliance (maximum) voltage.",
    "Physical orientation of the board: lying flat with the heater facing up, or standing vertical. "
    "Only natural-convection loss differs.",
    "Steady-state temperature at full power (100 % duty for PWM): where electrical power in equals "
    "heat lost to the air. Nothing limits the temperature above this except turning the supply down.",
    "Whether T max is at or above the design temperature, and by how many °C.",
    "P needed: heat the plate loses at the design temperature (must be supplied to hold it).\n"
    "P available: electrical power the supply can deliver at the design temperature, where the copper "
    "is hotter and its resistance higher than at switch-on.\n"
    "PWM: duty = P needed / P available, the duty cycle that holds the design temperature.",
    "I design: current drawn while HOLDING the design temperature. The copper is hot, so its resistance "
    "is higher and (for CV) the current lower than at switch-on. For PWM this is the average current at "
    "the holding duty; the on-pulse current is the inrush value. For CC it is the set current, or "
    "less if the compliance voltage is reached (the voltage shown is what the supply must deliver).\n"
    "I inrush: current at switch-on with the board at ambient, when copper resistance is lowest - "
    "the highest current the heater ever draws at this voltage. Size the supply, wiring, fuse and "
    "switch (MOSFET/relay) for this value; for PWM it is the peak current during every on-pulse.",
    "Rough time from ambient to the design temperature at full power, from the plate's thermal mass "
    "alone (no load on the plate).",
)
SHORT_MODE = {th.MODES[0]: "CV", th.MODES[1]: "PWM", th.MODES[2]: "CC"}
SHORT_ORIENT = {th.ORIENTATIONS[0]: "Flat", th.ORIENTATIONS[1]: "Vertical"}


def _spin(lo: float, hi: float, step: float, decimals: int = 2, suffix: str = "") -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setDecimals(decimals)
    s.setKeyboardTracking(False)
    s.setMinimumWidth(78)
    if suffix:
        s.setSuffix(suffix)
    s.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return s


def _fmt_time(seconds: Optional[float]) -> str:
    if seconds is None:
        return "never"
    if seconds < 90:
        return f"{seconds:.0f} s"
    return f"{seconds / 60:.1f} min"


class AnalysisPanel(QWidget):
    params_edited = Signal()

    def __init__(self, design: Design, parent=None) -> None:
        super().__init__(parent)
        self.design = design
        self.result: Optional[GenResult] = None
        self._syncing = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self._build_table())
        lay.addWidget(self._build_inputs())
        lay.addWidget(self._build_assumptions())
        self.sync_from_design()

    # ------------------------------------------------------------ builders
    def _build_inputs(self) -> QGroupBox:
        g = QGroupBox("Supply and environment")
        grid = QGridLayout(g)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        self.supply_v = _spin(0.1, 1000, 1, 1, " V")
        self.supply_i = _spin(0.01, 100, 0.1, 2, " A")
        self.compliance_v = _spin(0.1, 1000, 1, 1, " V")
        self.amb = _spin(-50, 100, 1, 0, " °C")
        self.emissivity = _spin(0.02, 1.0, 0.05, 2)
        self.thickness = _spin(0.2, 10, 0.2, 2, " mm")
        self.extra_loss = _spin(0, 100, 0.05, 2, " W/K")
        fields = (("Supply V (CV / PWM)", self.supply_v), ("Ambient", self.amb),
                  ("Current (CC)", self.supply_i), ("Emissivity", self.emissivity),
                  ("Compliance V (CC)", self.compliance_v), ("Board thickness", self.thickness),
                  ("Extra loss", self.extra_loss))
        for i, (label, w) in enumerate(fields):
            r, c = divmod(i, 2)
            lab = QLabel(label)
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(lab, r, c * 2)
            grid.addWidget(w, r, c * 2 + 1)
        self.design_temp_label = QLabel()
        self.design_temp_label.setProperty("role", "dim")
        self.design_temp_label.setWordWrap(True)
        grid.addWidget(self.design_temp_label, 4, 0, 1, 4)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        for w in (self.supply_v, self.supply_i, self.compliance_v, self.amb, self.emissivity,
                  self.thickness, self.extra_loss):
            w.valueChanged.connect(self._edited)
        return g

    def _build_table(self) -> QGroupBox:
        g = QGroupBox("Estimate")
        v = QVBoxLayout(g)
        self.table = QTableWidget(len(th.MODES) * len(th.ORIENTATIONS), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        for col, tip in enumerate(TOOLTIPS):
            self.table.horizontalHeaderItem(col).setToolTip(tip)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setWordWrap(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setStretchLastSection(True)
        hh.setDefaultAlignment(Qt.AlignCenter)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        v.addWidget(self.table)
        legend = QLabel("CV = constant voltage, PWM = PWM'd voltage (T max at 100 % duty), CC = constant current. "
                        "I design = current while holding the design temperature (hot copper, higher R; average "
                        "for PWM). I inrush = current at switch-on from ambient (cold copper, lowest R) - size the "
                        "supply, wiring and switch for this. Hover the table headers and cells for details.")
        legend.setWordWrap(True)
        legend.setProperty("role", "dim")
        v.addWidget(legend)
        self.breakdown = QLabel()
        self.breakdown.setWordWrap(True)
        self.breakdown.setProperty("role", "dim")
        self.breakdown.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(self.breakdown)
        return g

    def _build_assumptions(self) -> QGroupBox:
        g = QGroupBox("What this estimate is built on")
        v = QVBoxLayout(g)
        lab = QLabel(th.ASSUMPTIONS)
        lab.setWordWrap(True)
        lab.setProperty("role", "dim")
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(lab)
        return g

    # ------------------------------------------------------------- sync
    def sync_from_design(self) -> None:
        self._syncing = True
        try:
            p = self.design.params
            self.supply_v.setValue(p.supply_v)
            self.supply_i.setValue(p.supply_i)
            self.compliance_v.setValue(p.compliance_v)
            self.amb.setValue(p.amb_temp_c)
            self.emissivity.setValue(p.emissivity)
            self.thickness.setValue(p.board_thickness_mm)
            self.extra_loss.setValue(p.extra_loss_w_per_k)
        finally:
            self._syncing = False
        self.refresh()

    def _edited(self) -> None:
        if self._syncing:
            return
        p = self.design.params
        old = p.to_dict()
        p.supply_v = self.supply_v.value()
        p.supply_i = self.supply_i.value()
        p.compliance_v = self.compliance_v.value()
        p.amb_temp_c = self.amb.value()
        p.emissivity = self.emissivity.value()
        p.board_thickness_mm = self.thickness.value()
        p.extra_loss_w_per_k = self.extra_loss.value()
        new = p.to_dict()
        diff = {k: (old[k], new[k]) for k in new if old[k] != new[k]}
        if diff:
            log.info("analysis params changed: %s", diff)
            self.params_edited.emit()
        self.refresh()

    def set_result(self, result: Optional[GenResult]) -> None:
        self.result = result
        self.refresh()

    # ------------------------------------------------------------- compute
    def refresh(self) -> None:
        p = self.design.params
        self.design_temp_label.setText(
            f"Design temperature: {p.op_temp_c:g} °C (set under Parameters ▸ Design temperature).")
        self.table.clearContents()
        if self.result is None or self.design.heater is None:
            self.breakdown.setText("Generate a heater first.")
            return
        r = self.result
        h = self.design.board_rect()
        r20 = res.resistance(r.length_mm, r.width, p.copper_oz)
        cu_mass = r.length_mm * 1e-3 * r.width * 1e-3 * p.copper_oz * res.OZ_THICKNESS_M * th.CU_DENSITY
        plate = th.Plate(h.w * 1e-3, h.h * 1e-3, r20, p.amb_temp_c, p.emissivity,
                         p.board_thickness_mm * 1e-3, p.extra_loss_w_per_k, cu_mass)
        if p.op_temp_c <= p.amb_temp_c:
            self.breakdown.setText("Design temperature must be above ambient.")
            return
        try:
            rows = th.analyse_all(plate, p.supply_v, p.supply_i, p.compliance_v, p.op_temp_c)
        except Exception as e:  # noqa: BLE001
            log.exception("analysis failed")
            self.breakdown.setText(f"Analysis failed: {e}")
            return
        for i, a in enumerate(rows):
            self._fill_row(i, a)
        self.table.resizeRowsToContents()
        self._fit_table_height()
        parts = []
        for o in th.ORIENTATIONS:
            lb = th.loss_breakdown(plate, p.op_temp_c, o)
            parts.append(f"{o}: convection {lb.convection_w:.1f} W (h = {lb.h_face1:.1f} / {lb.h_face2:.1f} W/m²K) "
                         f"+ radiation {lb.radiation_w:.1f} W + extra {lb.extra_w:.1f} W = {lb.total:.1f} W needed "
                         f"at {p.op_temp_c:g} °C")
        r_design = plate.resistance(p.op_temp_c)
        parts.append(f"Heater: {r20:.3f} Ω at 20 °C → {r_design:.3f} Ω at {p.op_temp_c:g} °C; plate "
                     f"{h.w:g} × {h.h:g} mm ({'PCB outline' if self.design.board else 'heater area'}), thermal mass "
                     f"≈ {plate.heat_capacity():.0f} J/K.")
        self.breakdown.setText("\n".join(parts))

    def _fit_table_height(self) -> None:
        h = self.table.horizontalHeader().height() + 2 * self.table.frameWidth() + 4
        for r in range(self.table.rowCount()):
            h += self.table.rowHeight(r)
        self.table.setFixedHeight(h)

    def _cell_tip(self, col: int, a: th.Analysis) -> str:
        """Header explanation plus this row's actual numbers."""
        p = self.design.params
        if col == 5:
            r_amb = a.i_inrush and (a.v_at_design / a.i_inrush if a.mode != th.MODES[2] else None)
            lines = [TOOLTIPS[5], ""]
            if a.mode == th.MODES[1]:
                lines.append(f"This row: {a.i_at_design:.2f} A average at {p.op_temp_c:g} °C "
                             f"(duty {min(a.duty_at_design or 0, 1) * 100:.0f} %), "
                             f"{a.i_inrush:.2f} A during each on-pulse and at switch-on.")
            elif a.mode == th.MODES[2]:
                lines.append(f"This row: {a.i_at_design:.2f} A at {a.v_at_design:.1f} V while holding "
                             f"{p.op_temp_c:g} °C; {a.i_inrush:.2f} A at switch-on.")
            else:
                lines.append(f"This row: {a.i_at_design:.2f} A at {p.op_temp_c:g} °C, "
                             f"{a.i_inrush:.2f} A at switch-on ({p.amb_temp_c:g} °C"
                             + (f", R = {r_amb:.2f} Ω" if r_amb else "") + ").")
            return "\n".join(lines)
        if col == 4 and a.duty_at_design is not None and a.duty_at_design > 1:
            return TOOLTIPS[4] + "\n\nThis row needs more than 100 % duty: the supply voltage is too low to hold " \
                                 "the design temperature."
        return TOOLTIPS[col]

    def _fill_row(self, row: int, a: th.Analysis) -> None:
        if a.runaway:
            tmax = f"> {th.T_LIMIT_C:.0f} (runaway)"
        else:
            tmax = f"{a.t_max_c:.0f} °C"
        reach = "yes" if a.reaches else "no"
        if a.reaches and not a.runaway:
            reach += f" (+{a.t_max_c - self.design.params.op_temp_c:.0f} °C)"
        elif not a.reaches:
            reach += f" ({a.t_max_c - self.design.params.op_temp_c:.0f} °C)"
        power = f"{a.p_needed_w:.1f} / {a.p_available_w:.1f} W"
        if a.duty_at_design is not None:
            power += f"\nduty {a.duty_at_design * 100:.0f}%" if a.duty_at_design <= 1 \
                else f"\nneeds {a.duty_at_design * 100:.0f}%"
        current = f"{a.i_at_design:.2f} / {a.i_inrush:.2f} A"
        if a.mode == th.MODES[2]:
            current += f"\n{a.v_at_design:.1f} V"
        warm = _fmt_time(a.time_to_design_s) if a.reaches else "—"
        values = (SHORT_MODE[a.mode], SHORT_ORIENT[a.orientation], tmax, reach, power, current, warm)
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            item.setToolTip(self._cell_tip(col, a))
            if col == 3:
                item.setForeground(QColor(theme.GREEN if a.reaches else theme.PINK))
            if col == 2 and a.runaway:
                item.setForeground(QColor(theme.ORANGE))
            if col == 4 and a.duty_at_design is not None and a.duty_at_design > 1:
                item.setForeground(QColor(theme.PINK))
            self.table.setItem(row, col, item)
