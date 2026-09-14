"""Right-hand control panel: geometry inputs, parameters, results, options."""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QScrollArea,
                               QSizePolicy, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
                               QAbstractItemView, QHeaderView)

from ..core.generator import GenResult
from ..core.model import Design, Rect
from ..core import inductance as ind, resistance as res
from . import canvas as cv
from .plot import RTPlot
from .analysis import AnalysisPanel

log = logging.getLogger("heaterapp.ui.panel")


def _spin(lo: float, hi: float, step: float, decimals: int = 3, suffix: str = "") -> QDoubleSpinBox:
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


def _label(text: str = "", role: str = "") -> QLabel:
    lab = QLabel(text)
    if role:
        lab.setProperty("role", role)
    lab.setWordWrap(True)
    lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lab


class SidePanel(QWidget):
    """Tabs (Design / Parameters / Options) with the results and the action
    buttons always visible underneath, whatever the window height."""
    design_edited = Signal(str)       # design (geometry/params) changed via the panel
    request_tool = Signal(str)
    request_fit = Signal()
    request_generate = Signal()
    request_export = Signal()
    logging_toggled = Signal(bool)
    open_log_folder = Signal()
    keepout_selected = Signal(int)

    def __init__(self, design: Design, parent=None) -> None:
        super().__init__(parent)
        self.design = design
        self._syncing = False
        self.setMinimumWidth(320)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._scroll(self._build_heater_group(), self._build_board_group(),
                                      self._build_keepout_group(), self._build_endpoint_group()), "Design")
        self.tabs.addTab(self._scroll(self._build_param_group(), self._build_plot_group()), "Parameters")
        self.analysis = AnalysisPanel(design)
        self.analysis.params_edited.connect(lambda: self.design_edited.emit("analysis params changed"))
        self.tabs.addTab(self._scroll(self.analysis), "Analysis")
        self.tabs.addTab(self._scroll(self._build_options_group()), "Options")
        lay.addWidget(self.tabs, 1)
        results = self.results_group = self._build_results_group()
        results.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        lay.addWidget(results)
        lay.addLayout(self._build_actions())
        self.sync_from_design()

    @staticmethod
    def _scroll(*groups: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(4, 6, 4, 4)
        v.setSpacing(8)
        for g in groups:
            v.addWidget(g)
        v.addStretch(1)
        area.setWidget(inner)
        return area

    # ------------------------------------------------------------- builders
    def _build_heater_group(self) -> QGroupBox:
        g = QGroupBox("Heater area (mm)")
        grid = QGridLayout(g)
        grid.setHorizontalSpacing(6)
        self.hx, self.hy = _spin(-10000, 10000, 0.5), _spin(-10000, 10000, 0.5)
        self.hw, self.hh = _spin(0, 10000, 0.5), _spin(0, 10000, 0.5)
        for i, (name, w) in enumerate((("X", self.hx), ("Y", self.hy), ("W", self.hw), ("H", self.hh))):
            grid.addWidget(QLabel(name), i // 2, (i % 2) * 2)
            grid.addWidget(w, i // 2, (i % 2) * 2 + 1)
            w.valueChanged.connect(self._heater_edited)
        row = QHBoxLayout()
        b = QPushButton("Draw heater")
        b.clicked.connect(lambda: self.request_tool.emit(cv.TOOL_HEATER))
        row.addWidget(b)
        b = QPushButton("Fit view")
        b.clicked.connect(self.request_fit.emit)
        row.addWidget(b)
        grid.addLayout(row, 2, 0, 1, 4)
        return g

    def _build_board_group(self) -> QGroupBox:
        g = QGroupBox("PCB outline (mm)")
        grid = QGridLayout(g)
        grid.setHorizontalSpacing(6)
        self.board_same = QCheckBox("Same as heater area")
        self.board_same.toggled.connect(self._board_same_toggled)
        grid.addWidget(self.board_same, 0, 0, 1, 4)
        self.bx, self.by = _spin(-10000, 10000, 0.5), _spin(-10000, 10000, 0.5)
        self.bw, self.bh = _spin(0, 10000, 0.5), _spin(0, 10000, 0.5)
        self.board_spins = (self.bx, self.by, self.bw, self.bh)
        for i, (name, w) in enumerate((("X", self.bx), ("Y", self.by), ("W", self.bw), ("H", self.bh))):
            grid.addWidget(QLabel(name), 1 + i // 2, (i % 2) * 2)
            grid.addWidget(w, 1 + i // 2, (i % 2) * 2 + 1)
            w.valueChanged.connect(self._board_edited)
        b = QPushButton("Centre on heater")
        b.clicked.connect(self._board_centre)
        grid.addWidget(b, 3, 0, 1, 4)
        note = _label("Used for the thermal analysis (loss area), the canvas outline and the footprint "
                      "courtyard. The trace itself only fills the heater area.", "dim")
        grid.addWidget(note, 4, 0, 1, 4)
        return g

    def _build_keepout_group(self) -> QGroupBox:
        g = QGroupBox("Keepouts (mm)")
        v = QVBoxLayout(g)
        self.ktable = QTableWidget(0, 4)
        self.ktable.setHorizontalHeaderLabels(["X", "Y", "W", "H"])
        self.ktable.verticalHeader().setVisible(False)
        self.ktable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ktable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ktable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ktable.setMinimumHeight(80)
        self.ktable.setMaximumHeight(140)
        self.ktable.itemChanged.connect(self._keepout_item_changed)
        self.ktable.itemSelectionChanged.connect(self._keepout_selection)
        v.addWidget(self.ktable)
        row = QHBoxLayout()
        b = QPushButton("Draw keepout")
        b.clicked.connect(lambda: self.request_tool.emit(cv.TOOL_KEEPOUT))
        row.addWidget(b)
        b = QPushButton("Add")
        b.clicked.connect(self._add_keepout)
        row.addWidget(b)
        b = QPushButton("Remove")
        b.clicked.connect(self._remove_keepout)
        row.addWidget(b)
        v.addLayout(row)
        return g

    def _build_endpoint_group(self) -> QGroupBox:
        g = QGroupBox("Endpoints (mm)")
        grid = QGridLayout(g)
        grid.setHorizontalSpacing(6)
        self.pad_spins = {}
        for r, (key, label, tool) in enumerate((("a", "Pad A (1)", cv.TOOL_PAD_A), ("b", "Pad B (2)", cv.TOOL_PAD_B))):
            grid.addWidget(QLabel(label), r, 0)
            sx, sy = _spin(-10000, 10000, 0.5), _spin(-10000, 10000, 0.5)
            self.pad_spins[key] = (sx, sy)
            sx.valueChanged.connect(lambda _v, k=key: self._pad_edited(k))
            sy.valueChanged.connect(lambda _v, k=key: self._pad_edited(k))
            grid.addWidget(sx, r, 1)
            grid.addWidget(sy, r, 2)
            b = QPushButton("Place")
            b.clicked.connect(lambda _c, t=tool: self.request_tool.emit(t))
            grid.addWidget(b, r, 3)
        note = _label("Pads inside the area snap to the trace grid; outside, a lead trace is added.", "dim")
        grid.addWidget(note, 2, 0, 1, 4)
        return g

    def _build_param_group(self) -> QGroupBox:
        g = QGroupBox("Parameters")
        form = QFormLayout(g)
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.min_width = _spin(0.01, 50, 0.05, suffix=" mm")
        self.min_space = _spin(0.01, 50, 0.05, suffix=" mm")
        self.copper = _spin(0.1, 10, 0.5, 2, suffix=" oz")
        self.target = _spin(0, 100000, 0.5, 3, suffix=" Ω")
        self.target.setSpecialValueText("none (use min width)")
        self.op_temp = _spin(-50, 400, 10, 0, suffix=" °C")
        self.pad_w = _spin(0.1, 50, 0.5, 2, suffix=" mm")
        self.pad_h = _spin(0.1, 50, 0.5, 2, suffix=" mm")
        self.snap = _spin(0, 10, 0.1, 2, suffix=" mm")
        self.snap.setSpecialValueText("off")
        self.orientation = QComboBox()
        self.orientation.addItems(["horizontal", "vertical"])
        self.name = QLineEdit()
        form.addRow("Min trace width", self.min_width)
        form.addRow("Min spacing", self.min_space)
        form.addRow("Copper weight", self.copper)
        form.addRow("Target resistance", self.target)
        form.addRow("Design temperature", self.op_temp)
        form.addRow("Pad width", self.pad_w)
        form.addRow("Pad height", self.pad_h)
        form.addRow("Snap grid", self.snap)
        form.addRow("Run direction", self.orientation)
        form.addRow("Footprint name", self.name)
        for w in (self.min_width, self.min_space, self.copper, self.target, self.op_temp,
                  self.pad_w, self.pad_h, self.snap):
            w.valueChanged.connect(self._params_edited)
        self.orientation.currentTextChanged.connect(self._params_edited)
        self.name.editingFinished.connect(self._params_edited)
        return g

    def _build_plot_group(self) -> QGroupBox:
        g = QGroupBox("Resistance vs temperature")
        v = QVBoxLayout(g)
        self.rt_plot = RTPlot()
        v.addWidget(self.rt_plot)
        v.addWidget(_label("Copper TCR 0.393 %/°C, from room temperature to the design temperature.", "dim"))
        return g

    def _build_results_group(self) -> QGroupBox:
        g = QGroupBox("Result")
        grid = QGridLayout(g)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(3)
        self.res_labels = {}
        keys = [("width", "Trace width"), ("pitch", "Pitch (x / y)"), ("cells", "Grid"),
                ("coverage", "Coverage"), ("length", "Trace length"), ("r20", "R @ 20 °C"),
                ("rt", "R @ T"), ("power", "Power @ 12 / 24 V"), ("induct", "Inductance (est.)")]
        for i, (k, label) in enumerate(keys):
            lab = _label(label, "dim")
            val = _label("–", "value")
            grid.addWidget(lab, i, 0)
            grid.addWidget(val, i, 1)
            self.res_labels[k] = val
            if k == "induct":
                tip = ("Low-frequency loop inductance between the pads, from partial inductances: the "
                       "self-inductance of every straight segment plus the signed mutual inductance of every "
                       "pair of parallel segments (adjacent runs carry opposite current, so most of it cancels). "
                       "Lead segments count only their self-inductance. L/R is the electrical time constant; "
                       "with a few µH it is far below any PWM period, so switching is resistive for practical "
                       "purposes (the L·di/dt kick on a fast edge is tens of mV).")
                lab.setToolTip(tip)
                val.setToolTip(tip)
        grid.setColumnStretch(1, 1)
        self.error_label = _label("", "error")
        grid.addWidget(self.error_label, len(keys), 0, 1, 2)
        self.warn_list = QListWidget()
        self.warn_list.setFixedHeight(64)
        self.warn_list.setStyleSheet("color: #e6db74;")
        self.warn_list.setWordWrap(True)
        self.warn_list.hide()
        grid.addWidget(self.warn_list, len(keys) + 1, 0, 1, 2)
        return g

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        b = QPushButton("Generate")
        b.clicked.connect(self.request_generate.emit)
        row.addWidget(b)
        self.export_btn = QPushButton("Export .kicad_mod")
        self.export_btn.setProperty("role", "primary")
        self.export_btn.clicked.connect(self.request_export.emit)
        self.export_btn.setEnabled(False)
        row.addWidget(self.export_btn)
        return row

    def _build_options_group(self) -> QGroupBox:
        g = QGroupBox("Options")
        v = QVBoxLayout(g)
        self.log_check = QCheckBox("Enable logging (actions, errors, crashes)")
        self.log_check.setChecked(True)
        self.log_check.toggled.connect(self.logging_toggled.emit)
        v.addWidget(self.log_check)
        row = QHBoxLayout()
        b = QPushButton("Open log folder")
        b.clicked.connect(self.open_log_folder.emit)
        row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        self.log_path_label = _label("", "dim")
        v.addWidget(self.log_path_label)
        return g

    # ------------------------------------------------------------ sync in/out
    def sync_from_design(self) -> None:
        """Push the design into the widgets without triggering edits."""
        self._syncing = True
        try:
            d = self.design
            h = d.heater or Rect()
            for w, v in ((self.hx, h.x), (self.hy, h.y), (self.hw, h.w), (self.hh, h.h)):
                w.setValue(v)
            b = d.board
            self.board_same.setChecked(b is None)
            shown = b if b is not None else h
            for w, v in ((self.bx, shown.x), (self.by, shown.y), (self.bw, shown.w), (self.bh, shown.h)):
                w.setValue(v)
                w.setEnabled(b is not None)
            self.ktable.setRowCount(len(d.keepouts))
            for i, k in enumerate(d.keepouts):
                for j, v in enumerate((k.x, k.y, k.w, k.h)):
                    item = QTableWidgetItem(f"{v:g}")
                    item.setTextAlignment(Qt.AlignCenter)
                    self.ktable.setItem(i, j, item)
            for key in ("a", "b"):
                pad = getattr(d, f"pad_{key}")
                sx, sy = self.pad_spins[key]
                sx.setValue(pad[0] if pad else 0)
                sy.setValue(pad[1] if pad else 0)
            p = d.params
            self.min_width.setValue(p.min_width)
            self.min_space.setValue(p.min_space)
            self.copper.setValue(p.copper_oz)
            self.target.setValue(p.target_ohms or 0)
            self.op_temp.setValue(p.op_temp_c)
            self.pad_w.setValue(p.pad_w)
            self.pad_h.setValue(p.pad_h)
            self.snap.setValue(p.snap_mm)
            self.orientation.setCurrentText(p.orientation)
            self.name.setText(p.name)
        finally:
            self._syncing = False
        if hasattr(self, "analysis"):
            self.analysis.sync_from_design()

    def select_keepout_row(self, index: Optional[int]) -> None:
        self._syncing = True
        try:
            self.ktable.clearSelection()
            if index is not None and 0 <= index < self.ktable.rowCount():
                self.ktable.selectRow(index)
        finally:
            self._syncing = False

    def set_logging_state(self, enabled: bool, path: str) -> None:
        self.log_check.blockSignals(True)
        self.log_check.setChecked(enabled)
        self.log_check.blockSignals(False)
        # zero-width spaces let the long path wrap at separators
        zwsp = "​"
        self.log_path_label.setText(path.replace("\\", "\\" + zwsp).replace("/", "/" + zwsp))

    def set_result(self, result: Optional[GenResult], error: Optional[str]) -> None:
        self.export_btn.setEnabled(result is not None)
        self.analysis.set_result(result)
        self.warn_list.clear()
        if result is None:
            self.rt_plot.set_data(None, self.design.params.op_temp_c)
            for lab in self.res_labels.values():
                lab.setText("–")
            self.error_label.setText(error or "")
            self.warn_list.hide()
            return
        self.error_label.setText("")
        p = self.design.params
        r20 = res.resistance(result.length_mm, result.width, p.copper_oz)
        rt = res.resistance(result.length_mm, result.width, p.copper_oz, p.op_temp_c)
        self.rt_plot.set_data(r20, p.op_temp_c)
        self.res_labels["width"].setText(f"{result.width:.3f} mm  (space ≥ {min(result.pitch_x, result.pitch_y) - result.width:.3f} mm)")
        self.res_labels["pitch"].setText(f"{result.pitch_x:.3f} / {result.pitch_y:.3f} mm")
        self.res_labels["cells"].setText(f"{result.nx} × {result.ny} cells, {result.free_cells} free")
        self.res_labels["coverage"].setText(f"{100 * result.coverage:.1f}%  ({result.covered} cells)")
        self.res_labels["length"].setText(f"{result.length_mm:.1f} mm")
        self.res_labels["r20"].setText(f"{r20:.3f} Ω")
        self.res_labels["rt"].setText(f"{rt:.3f} Ω @ {p.op_temp_c:g} °C")
        if r20 > 0:
            self.res_labels["power"].setText(f"{144 / r20:.1f} W / {576 / r20:.1f} W  (at 20 °C)")
        else:
            self.res_labels["power"].setText("–")
        try:
            L = ind.trace_inductance(result.segments(), result.width, p.copper_oz * res.OZ_THICKNESS_M)
            tau_ns = L / r20 * 1e9 if r20 > 0 else 0
            self.res_labels["induct"].setText(f"{L * 1e6:.2f} µH  (L/R ≈ {tau_ns:.0f} ns)")
        except Exception:  # noqa: BLE001 - never let the estimate break the result panel
            log.exception("inductance estimate failed")
            self.res_labels["induct"].setText("–")
        if result.warnings:
            for w in result.warnings:
                self.warn_list.addItem(w)
            self.warn_list.show()
        else:
            self.warn_list.hide()

    # --------------------------------------------------------------- slots
    def _heater_edited(self) -> None:
        if self._syncing:
            return
        self.design.heater = Rect(self.hx.value(), self.hy.value(), self.hw.value(), self.hh.value())
        log.info("heater edited via panel: %s", self.design.heater)
        self.design_edited.emit("heater edited")

    def _board_same_toggled(self, same: bool) -> None:
        if self._syncing:
            return
        if same:
            self.design.board = None
        else:
            h = self.design.heater or Rect(0, 0, 10, 10)
            self.design.board = Rect(h.x - 1.5, h.y - 1.5, h.w + 3, h.h + 3)
        log.info("board outline %s", "same as heater" if same else self.design.board)
        self.sync_from_design()
        self.design_edited.emit("board changed")

    def _board_edited(self) -> None:
        if self._syncing or self.design.board is None:
            return
        self.design.board = Rect(self.bx.value(), self.by.value(), self.bw.value(), self.bh.value())
        log.info("board edited via panel: %s", self.design.board)
        self.design_edited.emit("board changed")

    def _board_centre(self) -> None:
        h, b = self.design.heater, self.design.board
        if h is None or b is None:
            return
        self.design.board = Rect(h.cx - b.w / 2, h.cy - b.h / 2, b.w, b.h)
        log.info("board centred on heater: %s", self.design.board)
        self.sync_from_design()
        self.design_edited.emit("board changed")

    def _keepout_item_changed(self, item: QTableWidgetItem) -> None:
        if self._syncing:
            return
        row = item.row()
        if row >= len(self.design.keepouts):
            return
        try:
            vals = [float(self.ktable.item(row, j).text()) for j in range(4)]
        except (ValueError, AttributeError):
            self.sync_from_design()
            return
        self.design.keepouts[row] = Rect(vals[0], vals[1], max(0.0, vals[2]), max(0.0, vals[3]))
        log.info("keepout %d edited via panel: %s", row, self.design.keepouts[row])
        self.design_edited.emit("keepout edited")

    def _keepout_selection(self) -> None:
        if self._syncing:
            return
        rows = self.ktable.selectionModel().selectedRows()
        self.keepout_selected.emit(rows[0].row() if rows else -1)

    def _add_keepout(self) -> None:
        h = self.design.heater
        if h and h.is_valid():
            r = Rect(h.cx - 2.5, h.cy - 2.5, 5, 5)
        else:
            r = Rect(0, 0, 5, 5)
        self.design.keepouts.append(r)
        log.info("keepout added via panel: %s", r)
        self.sync_from_design()
        self.design_edited.emit("keepout added")

    def _remove_keepout(self) -> None:
        rows = self.ktable.selectionModel().selectedRows()
        if not rows:
            return
        i = rows[0].row()
        if 0 <= i < len(self.design.keepouts):
            del self.design.keepouts[i]
            log.info("keepout %d removed via panel", i)
            self.sync_from_design()
            self.design_edited.emit("keepout removed")

    def _pad_edited(self, key: str) -> None:
        if self._syncing:
            return
        sx, sy = self.pad_spins[key]
        setattr(self.design, f"pad_{key}", (sx.value(), sy.value()))
        log.info("pad %s edited via panel: (%.3f, %.3f)", key, sx.value(), sy.value())
        self.design_edited.emit(f"pad {key} edited")

    def _params_edited(self) -> None:
        if self._syncing:
            return
        p = self.design.params
        old = p.to_dict()
        p.min_width = self.min_width.value()
        p.min_space = self.min_space.value()
        p.copper_oz = self.copper.value()
        p.target_ohms = self.target.value() or None
        p.op_temp_c = self.op_temp.value()
        p.pad_w = self.pad_w.value()
        p.pad_h = self.pad_h.value()
        p.snap_mm = self.snap.value()
        p.orientation = self.orientation.currentText()
        p.name = self.name.text().strip() or "Heater"
        new = p.to_dict()
        diff = {k: (old[k], new[k]) for k in new if old[k] != new[k]}
        if diff:
            log.info("params changed: %s", diff)
            self.design_edited.emit("params changed")
