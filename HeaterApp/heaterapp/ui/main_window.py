"""Main window: canvas + side panel, toolbar, menus, regeneration and export."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from typing import Optional

import copy

from PySide6.QtCore import QByteArray, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QLabel, QMainWindow, QMessageBox, QSplitter,
                               QToolBar)

from .. import logging_setup, settings
from ..core import design_io, generator as gen, kicad_export
from ..core.model import Design, Params, Rect
from . import canvas as cv
from .panels import SidePanel

log = logging.getLogger("heaterapp.ui.main")

AUTO_CELL_LIMIT = 80_000


class GenWorker(QThread):
    """Runs the generator off the UI thread on a private copy of the design."""
    finished_with = Signal(int, object, object)  # seq, result | None, error | None

    def __init__(self, seq: int, design: Design, parent=None) -> None:
        super().__init__(parent)
        self.seq = seq
        self.design = copy.deepcopy(design)

    def run(self) -> None:
        t0 = time.perf_counter()
        try:
            result = gen.run(self.design)
            dt = time.perf_counter() - t0
            log.info("generated: width=%.3f cells=%dx%d coverage=%.4f length=%.1f warnings=%s (%.0f ms)",
                     result.width, result.nx, result.ny, result.coverage, result.length_mm,
                     result.warnings, dt * 1000)
            result.elapsed_ms = dt * 1000  # type: ignore[attr-defined]
            self.finished_with.emit(self.seq, result, None)
        except gen.GenError as e:
            log.info("generation not possible: %s", e)
            self.finished_with.emit(self.seq, None, str(e))
        except Exception as e:  # noqa: BLE001 - surface unexpected failures
            log.exception("generation failed")
            self.finished_with.emit(self.seq, None, f"Internal error: {e} (see log)")


def default_design() -> Design:
    d = Design(params=Params())
    d.heater = Rect(-48.5, -48.5, 97, 97)
    d.pad_a = (-48.0, -48.0)
    d.pad_b = (48.0, -48.0)
    return d


class MainWindow(QMainWindow):
    def __init__(self, cfg: settings.Settings) -> None:
        super().__init__()
        self.cfg = cfg
        self.design = default_design()
        self.result: Optional[gen.GenResult] = None
        self.design_path: Optional[str] = None
        self._worker: Optional[GenWorker] = None
        self._gen_seq = 0
        self._gen_pending = False
        self.setWindowTitle("HeaterApp – PCB heater footprint generator")
        self.resize(1280, 820)

        self.canvas = cv.DesignCanvas(self.design)
        self.panel = SidePanel(self.design)
        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.canvas)
        split.addWidget(self.panel)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)
        split.setSizes([900, 380])
        self.setCentralWidget(split)
        self._split = split

        self._build_toolbar()
        self._build_menu()
        self.coord_label = QLabel("x: –  y: –")
        self.info_label = QLabel("")
        self.statusBar().addWidget(self.coord_label)
        self.statusBar().addPermanentWidget(self.info_label)

        self._regen_timer = QTimer(self)
        self._regen_timer.setSingleShot(True)
        self._regen_timer.setInterval(150)
        self._regen_timer.timeout.connect(lambda: self.regenerate(auto=True))

        self.canvas.design_changed.connect(self._on_canvas_edit)
        self.canvas.cursor_moved.connect(lambda x, y: self.coord_label.setText(f"x: {x:.2f}  y: {y:.2f} mm"))
        self.canvas.tool_changed.connect(self._sync_tool_actions)
        self.canvas.selection_changed.connect(self._on_selection)
        self.panel.design_edited.connect(self._on_panel_edit)
        self.panel.request_tool.connect(self.canvas.set_tool)
        self.panel.request_fit.connect(self.canvas.fit_view)
        self.panel.request_generate.connect(lambda: self.regenerate(auto=False))
        self.panel.request_export.connect(self.export_footprint)
        self.panel.logging_toggled.connect(self._toggle_logging)
        self.panel.open_log_folder.connect(self._open_log_folder)
        self.panel.keepout_selected.connect(
            lambda i: self.canvas.set_selection(("keepout", i) if i >= 0 else None))

        self.panel.tabs.currentChanged.connect(self._on_tab_changed)
        self.panel.set_logging_state(logging_setup.is_enabled(), logging_setup.log_path())
        geom = cfg.get("window_geometry")
        if geom:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geom.encode("ascii")))
            except Exception:
                pass
        QTimer.singleShot(0, self._initial_layout)

    def _on_tab_changed(self, index: int) -> None:
        """The analysis table needs more room than the other tabs."""
        wide = self.panel.tabs.tabText(index) == "Analysis"
        total = sum(self._split.sizes())
        panel = min(700, int(total * 0.5)) if wide else 380
        self._split.setSizes([total - panel, panel])
        self.panel.results_group.setVisible(not wide)
        log.info("tab -> %s", self.panel.tabs.tabText(index))

    def _initial_layout(self) -> None:
        self.canvas.fit_view()
        self.regenerate(auto=True)

    # ------------------------------------------------------------ chrome
    def _build_toolbar(self) -> None:
        tb = QToolBar("Tools")
        tb.setMovable(False)
        self.addToolBar(tb)
        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_actions = {}
        for tool, label, key in ((cv.TOOL_SELECT, "Select / Pan", "V"), (cv.TOOL_HEATER, "Draw Heater", "H"),
                                 (cv.TOOL_KEEPOUT, "Draw Keepout", "K"), (cv.TOOL_PAD_A, "Place Pad A", "A"),
                                 (cv.TOOL_PAD_B, "Place Pad B", "B")):
            act = QAction(label, self)
            act.setCheckable(True)
            act.setShortcut(QKeySequence(key))
            act.setToolTip(f"{label} ({key})")
            act.triggered.connect(lambda _c, t=tool: self.canvas.set_tool(t))
            self.tool_group.addAction(act)
            tb.addAction(act)
            self.tool_actions[tool] = act
        self.tool_actions[cv.TOOL_SELECT].setChecked(True)
        tb.addSeparator()
        fit = QAction("Fit view", self)
        fit.setShortcut(QKeySequence("F"))
        fit.triggered.connect(self.canvas.fit_view)
        tb.addAction(fit)
        delete = QAction("Delete selected", self)
        delete.triggered.connect(self.canvas.delete_selection)
        tb.addAction(delete)
        tb.addSeparator()
        generate = QAction("Generate", self)
        generate.setShortcut(QKeySequence("Ctrl+G"))
        generate.triggered.connect(lambda: self.regenerate(auto=False))
        tb.addAction(generate)
        export = QAction("Export .kicad_mod", self)
        export.setShortcut(QKeySequence("Ctrl+E"))
        export.triggered.connect(self.export_footprint)
        tb.addAction(export)

    def _build_menu(self) -> None:
        m = self.menuBar().addMenu("&File")
        for label, key, fn in (("&New design", "Ctrl+N", self.new_design),
                               ("&Open design…", "Ctrl+O", self.open_design),
                               ("&Save design", "Ctrl+S", self.save_design),
                               ("Save design &as…", "Ctrl+Shift+S", self.save_design_as),
                               (None, None, None),
                               ("&Export footprint (.kicad_mod)…", "Ctrl+E", self.export_footprint),
                               (None, None, None),
                               ("&Quit", "Ctrl+Q", self.close)):
            if label is None:
                m.addSeparator()
                continue
            act = QAction(label, self)
            if key:
                act.setShortcut(QKeySequence(key))
            act.triggered.connect(fn)
            m.addAction(act)
        h = self.menuBar().addMenu("&Help")
        act = QAction("&About", self)
        act.triggered.connect(self._about)
        h.addAction(act)

    def _sync_tool_actions(self, tool: str) -> None:
        act = self.tool_actions.get(tool)
        if act and not act.isChecked():
            act.setChecked(True)

    def _on_selection(self, sel) -> None:
        self.panel.select_keepout_row(sel[1] if sel and sel[0] == "keepout" else None)

    # ------------------------------------------------------------- editing
    def _on_canvas_edit(self, what: str) -> None:
        self.panel.sync_from_design()
        self._schedule_regen(what)

    def _on_panel_edit(self, what: str) -> None:
        self.canvas.update()
        if what in ("analysis params changed", "board changed"):
            self.panel.analysis.refresh()
            return  # the trace is unaffected
        self._schedule_regen(what)

    def _schedule_regen(self, what: str) -> None:
        self.info_label.setText(f"{what} – regenerating…")
        self._regen_timer.start()

    def _estimated_cells(self) -> int:
        d = self.design
        if not d.heater or not d.heater.is_valid():
            return 0
        pitch = d.params.min_width + d.params.min_space
        if pitch <= 0:
            return 0
        return int(d.heater.area / (pitch * pitch))

    def regenerate(self, auto: bool) -> None:
        if auto and self._estimated_cells() > AUTO_CELL_LIMIT:
            msg = f"Large design (~{self._estimated_cells():,} cells): press Generate (Ctrl+G)"
            self._set_result(None, msg)
            return
        if self._worker is not None and self._worker.isRunning():
            self._gen_pending = True  # rerun with the latest design once this one finishes
            return
        self._gen_seq += 1
        self._gen_pending = False
        self.info_label.setText("generating…")
        self._worker = GenWorker(self._gen_seq, self.design, self)
        self._worker.finished_with.connect(self._on_generated)
        self._worker.start()

    def _on_generated(self, seq: int, result, error) -> None:
        if seq != self._gen_seq:
            return  # stale
        if self._gen_pending:
            self._gen_pending = False
            self.regenerate(auto=True)
            return
        self._set_result(result, error)
        if result is not None:
            self.info_label.setText(f"generated in {getattr(result, 'elapsed_ms', 0):.0f} ms")

    def _set_result(self, result: Optional[gen.GenResult], error: Optional[str]) -> None:
        self.result = result
        self.canvas.set_result(result, error)
        self.panel.set_result(result, error)
        if error:
            self.info_label.setText(error)

    # ----------------------------------------------------------------- files
    def _last_dir(self) -> str:
        return self.cfg.get("last_dir") or os.path.expanduser("~")

    def _remember_dir(self, path: str) -> None:
        self.cfg.set("last_dir", os.path.dirname(path))

    def _load_design(self, design: Design, path: Optional[str]) -> None:
        # keep the shared object identity used by canvas and panel
        self.design.heater = design.heater
        self.design.board = design.board
        self.design.keepouts = design.keepouts
        self.design.pad_a = design.pad_a
        self.design.pad_b = design.pad_b
        self.design.params = design.params
        self.design_path = path
        self.setWindowTitle(f"HeaterApp – {os.path.basename(path) if path else 'untitled'}")
        self.canvas.set_selection(None)
        self.panel.sync_from_design()
        self.canvas.fit_view()
        self.regenerate(auto=True)

    def new_design(self) -> None:
        log.info("new design")
        self._load_design(default_design(), None)

    def open_design(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open design", self._last_dir(),
                                              "HeaterApp design (*.heater.json *.json)")
        if not path:
            return
        try:
            d = design_io.load_design(path)
        except Exception as e:  # noqa: BLE001
            log.exception("open failed: %s", path)
            QMessageBox.critical(self, "Open failed", f"Could not open {path}:\n{e}")
            return
        log.info("opened design %s", path)
        self._remember_dir(path)
        self._load_design(d, path)

    def save_design(self) -> None:
        if not self.design_path:
            self.save_design_as()
            return
        self._write_design(self.design_path)

    def save_design_as(self) -> None:
        start = self.design_path or os.path.join(self._last_dir(), "heater.heater.json")
        path, _ = QFileDialog.getSaveFileName(self, "Save design", start, "HeaterApp design (*.heater.json)")
        if not path:
            return
        if not path.endswith(".json"):
            path += ".heater.json"
        self._write_design(path)

    def _write_design(self, path: str) -> None:
        try:
            design_io.save_design(path, self.design)
        except Exception as e:  # noqa: BLE001
            log.exception("save failed: %s", path)
            QMessageBox.critical(self, "Save failed", f"Could not save {path}:\n{e}")
            return
        log.info("saved design %s", path)
        self.design_path = path
        self._remember_dir(path)
        self.setWindowTitle(f"HeaterApp – {os.path.basename(path)}")
        self.info_label.setText(f"saved {os.path.basename(path)}")

    def export_footprint(self) -> None:
        if self.result is None:
            self.regenerate(auto=False)
        if self.result is None:
            QMessageBox.warning(self, "Nothing to export", "Generate a valid heater first.")
            return
        name = kicad_export.safe_name(self.design.params.name)
        start = os.path.join(self._last_dir(), f"{name}.kicad_mod")
        path, _ = QFileDialog.getSaveFileName(self, "Export KiCad footprint", start,
                                              "KiCad footprint (*.kicad_mod)")
        if not path:
            return
        if not path.endswith(".kicad_mod"):
            path += ".kicad_mod"
        try:
            kicad_export.write_footprint(path, self.design, self.result)
        except Exception as e:  # noqa: BLE001
            log.exception("export failed: %s", path)
            QMessageBox.critical(self, "Export failed", f"Could not write {path}:\n{e}")
            return
        log.info("exported footprint %s (%d segments)", path, len(self.result.segments()))
        self._remember_dir(path)
        self.info_label.setText(f"exported {os.path.basename(path)}")
        QMessageBox.information(self, "Exported",
                                f"Footprint written to:\n{path}\n\nCopy it into a .pretty library folder "
                                f"(or use File > Import > Footprint in KiCad's footprint editor).")

    # --------------------------------------------------------------- options
    def _toggle_logging(self, enabled: bool) -> None:
        logging_setup.set_enabled(enabled)
        self.cfg.set("logging_enabled", enabled)

    def _open_log_folder(self) -> None:
        folder = str(settings.log_dir())
        log.info("open log folder %s", folder)
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:  # noqa: BLE001
            QMessageBox.information(self, "Log folder", f"{folder}\n\n(could not open automatically: {e})")

    def _about(self) -> None:
        QMessageBox.about(self, "HeaterApp",
                          "HeaterApp – generates a serpentine PCB heater as a KiCad footprint.\n\n"
                          "Draw the heater area, add keepouts, place the two pads, set the copper "
                          "weight and target resistance, then export.")

    def closeEvent(self, e) -> None:
        try:
            self.cfg.set("window_geometry", bytes(self.saveGeometry().toBase64()).decode("ascii"))
        except Exception:
            pass
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(5000)
        log.info("window closed")
        super().closeEvent(e)
