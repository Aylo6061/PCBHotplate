"""Interactive design canvas: draws the heater area, keepouts, pads and the
generated trace; lets the user draw rectangles and place pads with the mouse."""
from __future__ import annotations

import logging
import math
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QKeyEvent, QMouseEvent, QPainter, QPainterPath,
                           QPaintEvent, QPen, QWheelEvent)
from PySide6.QtWidgets import QWidget

from ..core.generator import GenResult
from ..core.model import Design, Rect
from . import theme

log = logging.getLogger("heaterapp.ui.canvas")

TOOL_SELECT = "select"
TOOL_HEATER = "heater"
TOOL_KEEPOUT = "keepout"
TOOL_PAD_A = "pad_a"
TOOL_PAD_B = "pad_b"

HINTS = {
    TOOL_SELECT: "Select: click keepout/pad, drag to move, Del removes · drag or middle-mouse pans · wheel zooms · F fits",
    TOOL_HEATER: "Heater area: drag a rectangle",
    TOOL_KEEPOUT: "Keepout: drag a rectangle (repeat for more) · Esc to finish",
    TOOL_PAD_A: "Click to place pad A (1) · outside the heater area a lead trace is added",
    TOOL_PAD_B: "Click to place pad B (2) · outside the heater area a lead trace is added",
}

GRID_STEPS = (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200)


class DesignCanvas(QWidget):
    design_changed = Signal(str)          # description of the edit
    cursor_moved = Signal(float, float)   # world mm
    tool_changed = Signal(str)
    selection_changed = Signal(object)    # ("keepout", index) | ("pad", "a"/"b") | None

    def __init__(self, design: Design, parent=None) -> None:
        super().__init__(parent)
        self.design = design
        self.result: Optional[GenResult] = None
        self.error: Optional[str] = None
        self.scale = 6.0            # px per mm
        self.offset = QPointF(80, 80)
        self.tool = TOOL_SELECT
        self.selection = None
        self._drag_start_world: Optional[QPointF] = None
        self._drag_cur_world: Optional[QPointF] = None
        self._panning = False
        self._pan_last = QPointF()
        self._moving = None  # (kind, index/key, orig, start_world)
        self.auto_fit = True  # keep the design fitted until the user zooms/pans
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(300, 300)
        self.setCursor(Qt.CrossCursor)

    # ---------------------------------------------------------------- coords
    def to_screen(self, x: float, y: float) -> QPointF:
        return QPointF(self.offset.x() + x * self.scale, self.offset.y() + y * self.scale)

    def to_world(self, p: QPointF) -> QPointF:
        return QPointF((p.x() - self.offset.x()) / self.scale, (p.y() - self.offset.y()) / self.scale)

    def snap(self, v: float) -> float:
        s = self.design.params.snap_mm
        if s and s > 0:
            return round(v / s) * s
        return v

    def snapped(self, p: QPointF) -> QPointF:
        return QPointF(self.snap(p.x()), self.snap(p.y()))

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if self.auto_fit:
            self.fit_view()

    def fit_view(self) -> None:
        self.auto_fit = True
        r = self._design_bounds()
        if r is None:
            self.scale = 6.0
            self.offset = QPointF(self.width() / 2, self.height() / 2)
        else:
            margin = 40
            sx = (self.width() - 2 * margin) / max(r.w, 1e-3)
            sy = (self.height() - 2 * margin) / max(r.h, 1e-3)
            self.scale = max(0.05, min(sx, sy))
            self.offset = QPointF(self.width() / 2 - r.cx * self.scale, self.height() / 2 - r.cy * self.scale)
        log.debug("fit_view: canvas %dx%d scale=%.2f", self.width(), self.height(), self.scale)
        self.update()

    def _design_bounds(self) -> Optional[Rect]:
        xs, ys = [], []
        d = self.design
        if d.heater and d.heater.is_valid():
            xs += [d.heater.x, d.heater.x2]
            ys += [d.heater.y, d.heater.y2]
        if d.board and d.board.is_valid():
            xs += [d.board.x, d.board.x2]
            ys += [d.board.y, d.board.y2]
        for k in d.keepouts:
            xs += [k.x, k.x2]
            ys += [k.y, k.y2]
        for pad in (d.pad_a, d.pad_b):
            if pad:
                xs.append(pad[0])
                ys.append(pad[1])
        if not xs:
            return None
        r = Rect.from_corners(min(xs), min(ys), max(xs), max(ys))
        if r.w < 1:
            r = Rect(r.x - 5, r.y, r.w + 10, r.h)
        if r.h < 1:
            r = Rect(r.x, r.y - 5, r.w, r.h + 10)
        return r

    # ------------------------------------------------------------------ tools
    def set_tool(self, tool: str) -> None:
        if tool == self.tool:
            return
        self.tool = tool
        self._drag_start_world = None
        self._drag_cur_world = None
        log.info("tool -> %s", tool)
        self.setCursor(Qt.ArrowCursor if tool == TOOL_SELECT else Qt.CrossCursor)
        self.tool_changed.emit(tool)
        self.update()

    def set_result(self, result: Optional[GenResult], error: Optional[str]) -> None:
        self.result = result
        self.error = error
        self.update()

    def set_selection(self, sel) -> None:
        if sel != self.selection:
            self.selection = sel
            self.selection_changed.emit(sel)
            self.update()

    # ------------------------------------------------------------------ mouse
    def wheelEvent(self, e: QWheelEvent) -> None:
        delta = e.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        self.auto_fit = False
        pos = e.position()
        world = self.to_world(pos)
        self.scale = max(0.05, min(400.0, self.scale * factor))
        self.offset = QPointF(pos.x() - world.x() * self.scale, pos.y() - world.y() * self.scale)
        self.update()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        self.setFocus()
        pos = e.position()
        if e.button() in (Qt.MiddleButton, Qt.RightButton):
            self.auto_fit = False
            self._panning = True
            self._pan_last = pos
            self.setCursor(Qt.ClosedHandCursor)
            return
        if e.button() != Qt.LeftButton:
            return
        world = self.to_world(pos)
        if self.tool in (TOOL_HEATER, TOOL_KEEPOUT):
            self._drag_start_world = self.snapped(world)
            self._drag_cur_world = self._drag_start_world
        elif self.tool == TOOL_PAD_A:
            self._place_pad("a", self.snapped(world))
        elif self.tool == TOOL_PAD_B:
            self._place_pad("b", self.snapped(world))
        else:
            hit = self._hit_test(world)
            self.set_selection(hit)
            if hit is not None:
                kind, key = hit
                orig = self.design.keepouts[key] if kind == "keepout" else getattr(self.design, f"pad_{key}")
                if kind == "keepout":
                    orig = Rect(orig.x, orig.y, orig.w, orig.h)
                self._moving = (kind, key, orig, world)
            else:
                self.auto_fit = False
                self._panning = True
                self._pan_last = pos
                self.setCursor(Qt.ClosedHandCursor)
        self.update()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        pos = e.position()
        world = self.to_world(pos)
        self.cursor_moved.emit(world.x(), world.y())
        if self._panning:
            d = pos - self._pan_last
            self.offset += d
            self._pan_last = pos
            self.update()
            return
        if self._drag_start_world is not None:
            self._drag_cur_world = self.snapped(world)
            self.update()
            return
        if self._moving is not None:
            kind, key, orig, start = self._moving
            dx = self.snap(world.x() - start.x())
            dy = self.snap(world.y() - start.y())
            if kind == "keepout":
                self.design.keepouts[key] = Rect(orig.x + dx, orig.y + dy, orig.w, orig.h)
            else:
                setattr(self.design, f"pad_{key}", (orig[0] + dx, orig[1] + dy))
            self.update()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if self._panning and e.button() in (Qt.MiddleButton, Qt.RightButton, Qt.LeftButton):
            self._panning = False
            self.setCursor(Qt.ArrowCursor if self.tool == TOOL_SELECT else Qt.CrossCursor)
            return
        if e.button() != Qt.LeftButton:
            return
        if self._drag_start_world is not None and self._drag_cur_world is not None:
            a, b = self._drag_start_world, self._drag_cur_world
            rect = Rect.from_corners(a.x(), a.y(), b.x(), b.y())
            self._drag_start_world = None
            self._drag_cur_world = None
            if rect.w > 0 and rect.h > 0:
                if self.tool == TOOL_HEATER:
                    self.design.heater = rect
                    log.info("heater drawn: %s", rect)
                    self.design_changed.emit("heater drawn")
                    self.set_tool(TOOL_SELECT)
                else:
                    self.design.keepouts.append(rect)
                    log.info("keepout drawn: %s", rect)
                    self.design_changed.emit("keepout added")
            self.update()
            return
        if self._moving is not None:
            kind, key, orig, _ = self._moving
            self._moving = None
            cur = self.design.keepouts[key] if kind == "keepout" else getattr(self.design, f"pad_{key}")
            if cur != orig:
                log.info("%s %s moved to %s", kind, key, cur)
                self.design_changed.emit(f"{kind} moved")

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key_Escape:
            self.set_tool(TOOL_SELECT)
            self.set_selection(None)
        elif e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.selection is not None:
            self.delete_selection()
        elif e.key() == Qt.Key_F:
            self.fit_view()
        else:
            super().keyPressEvent(e)

    def delete_selection(self) -> None:
        if self.selection is None:
            return
        kind, key = self.selection
        if kind == "keepout":
            del self.design.keepouts[key]
            log.info("keepout %d deleted", key)
            self.design_changed.emit("keepout removed")
        else:
            setattr(self.design, f"pad_{key}", None)
            log.info("pad %s cleared", key)
            self.design_changed.emit(f"pad {key} cleared")
        self.set_selection(None)

    def _place_pad(self, key: str, p: QPointF) -> None:
        setattr(self.design, f"pad_{key}", (p.x(), p.y()))
        log.info("pad %s placed at (%.3f, %.3f)", key, p.x(), p.y())
        self.design_changed.emit(f"pad {key} placed")
        self.set_tool(TOOL_SELECT)

    def _hit_test(self, w: QPointF):
        d = self.design
        tol = 6 / self.scale
        for key in ("a", "b"):
            pad = getattr(d, f"pad_{key}")
            if pad and abs(pad[0] - w.x()) <= max(tol, d.params.pad_w / 2) \
                    and abs(pad[1] - w.y()) <= max(tol, d.params.pad_h / 2):
                return ("pad", key)
        for i in range(len(d.keepouts) - 1, -1, -1):
            if d.keepouts[i].contains(w.x(), w.y()):
                return ("keepout", i)
        return None

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _e: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(theme.BG_DARK))
        self._draw_grid(p)
        d = self.design

        if d.board and d.board.is_valid():
            self._draw_rect(p, d.board, QColor(theme.FG_DIM), fill_alpha=10, width=1.2)
            p.setPen(QColor(theme.FG_DIM))
            p.drawText(self.to_screen(d.board.x, d.board.y) + QPointF(4, -4), "PCB")
        if d.heater and d.heater.is_valid():
            self._draw_rect(p, d.heater, QColor(theme.GREEN), fill_alpha=18, width=1.5)

        if self.result is not None:
            self._draw_result(p)

        for i, k in enumerate(d.keepouts):
            selected = self.selection == ("keepout", i)
            self._draw_rect(p, k, QColor(theme.PINK), fill_alpha=45, width=2.5 if selected else 1.2,
                            hatch=True)

        for key, label in (("a", "1"), ("b", "2")):
            pad = getattr(d, f"pad_{key}")
            if pad is None:
                continue
            pos = pad
            if self.result is not None:
                pos = self.result.pad_a if key == "a" else self.result.pad_b
            self._draw_pad(p, pos, label, selected=self.selection == ("pad", key))

        if self._drag_start_world is not None and self._drag_cur_world is not None:
            a, b = self._drag_start_world, self._drag_cur_world
            col = QColor(theme.GREEN if self.tool == TOOL_HEATER else theme.PINK)
            pen = QPen(col, 1, Qt.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            sa, sb = self.to_screen(a.x(), a.y()), self.to_screen(b.x(), b.y())
            p.drawRect(QRectF(sa, sb).normalized())
            w, h = abs(b.x() - a.x()), abs(b.y() - a.y())
            p.setPen(QColor(theme.FG))
            p.drawText(sb + QPointF(8, -8), f"{w:.2f} x {h:.2f} mm")

        self._draw_overlay(p)
        p.end()

    def _draw_grid(self, p: QPainter) -> None:
        step = GRID_STEPS[-1]
        for s in GRID_STEPS:
            if s * self.scale >= 12:
                step = s
                break
        w, h = self.width(), self.height()
        x0 = (0 - self.offset.x()) / self.scale
        y0 = (0 - self.offset.y()) / self.scale
        x1 = (w - self.offset.x()) / self.scale
        y1 = (h - self.offset.y()) / self.scale
        minor = QPen(QColor(theme.BG_LIGHT), 1)
        major = QPen(QColor(theme.BORDER), 1)
        ix = math.floor(x0 / step)
        while ix * step <= x1:
            x = ix * step
            sx = self.to_screen(x, 0).x()
            p.setPen(major if ix % 5 == 0 else minor)
            p.drawLine(QPointF(sx, 0), QPointF(sx, h))
            ix += 1
        iy = math.floor(y0 / step)
        while iy * step <= y1:
            y = iy * step
            sy = self.to_screen(0, y).y()
            p.setPen(major if iy % 5 == 0 else minor)
            p.drawLine(QPointF(0, sy), QPointF(w, sy))
            iy += 1
        # origin axes
        p.setPen(QPen(QColor(theme.FG_DIM), 1))
        o = self.to_screen(0, 0)
        p.drawLine(QPointF(o.x(), 0), QPointF(o.x(), h))
        p.drawLine(QPointF(0, o.y()), QPointF(w, o.y()))
        p.setPen(QColor(theme.FG_DIM))
        p.drawText(QPointF(6, h - 6), f"grid {step:g} mm")

    def _draw_rect(self, p: QPainter, r: Rect, col: QColor, fill_alpha: int, width: float,
                   hatch: bool = False) -> None:
        a = self.to_screen(r.x, r.y)
        b = self.to_screen(r.x2, r.y2)
        sr = QRectF(a, b).normalized()
        fill = QColor(col)
        fill.setAlpha(fill_alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(fill))
        p.drawRect(sr)
        if hatch:
            hb = QBrush(QColor(col), Qt.BDiagPattern)
            p.setBrush(hb)
            p.drawRect(sr)
        p.setPen(QPen(col, width))
        p.setBrush(Qt.NoBrush)
        p.drawRect(sr)

    def _draw_result(self, p: QPainter) -> None:
        r = self.result
        assert r is not None
        # uncovered cells
        if r.uncovered:
            c = QColor(theme.YELLOW)
            c.setAlpha(140)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            hw = r.width / 2
            for cell in r.uncovered:
                cx, cy = r.grid.center(cell)
                a = self.to_screen(cx - hw, cy - hw)
                b = self.to_screen(cx + hw, cy + hw)
                p.drawRect(QRectF(a, b))
        pen_w = max(1.0, r.width * self.scale)
        trace = QColor(theme.GREEN)
        trace.setAlpha(210)
        pen = QPen(trace, pen_w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        pts = r.path
        if pts:
            path.moveTo(self.to_screen(*pts[0]))
            for x, y in pts[1:]:
                path.lineTo(self.to_screen(x, y))
            p.drawPath(path)
        lead_pen = QPen(QColor(theme.ORANGE), pen_w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(lead_pen)
        for lead in (r.lead_a, r.lead_b):
            if lead:
                p.drawLine(self.to_screen(*lead[0]), self.to_screen(*lead[1]))

    def _draw_pad(self, p: QPainter, pos, label: str, selected: bool) -> None:
        pw, ph = self.design.params.pad_w, self.design.params.pad_h
        a = self.to_screen(pos[0] - pw / 2, pos[1] - ph / 2)
        b = self.to_screen(pos[0] + pw / 2, pos[1] + ph / 2)
        sr = QRectF(a, b)
        col = QColor(theme.CYAN)
        fill = QColor(col)
        fill.setAlpha(170)
        p.setPen(QPen(QColor(theme.FG) if selected else col, 2 if selected else 1))
        p.setBrush(fill)
        p.drawRect(sr)
        # marker so tiny pads remain visible at low zoom
        c = self.to_screen(pos[0], pos[1])
        p.setPen(QPen(col, 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, 7, 7)
        p.setPen(QColor(theme.BG_DARK if sr.width() > 14 else theme.FG))
        f = QFont()
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(c.x() - 10, c.y() - 10, 20, 20), Qt.AlignCenter, label)

    def _draw_overlay(self, p: QPainter) -> None:
        p.setFont(QFont())
        p.setPen(QColor(theme.FG))
        flags = Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop
        p.drawText(QRectF(8, 6, self.width() - 16, 60), flags, HINTS.get(self.tool, ""))
        if self.error:
            p.setPen(QColor(theme.PINK))
            p.drawText(QRectF(8, 40, self.width() - 16, 80), flags, self.error)
