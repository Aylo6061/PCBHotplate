"""Small painted plot of heater resistance versus temperature."""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..core import resistance as res
from . import theme


class RTPlot(QWidget):
    """R(T) = R20 * (1 + TCR * (T - 20)) from room temperature (20 C) to the
    design (operating) temperature, with markers at both ends."""
    T_ROOM = 20.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.r20: Optional[float] = None
        self.op_temp = 100.0
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_data(self, r20: Optional[float], op_temp: float) -> None:
        self.r20 = r20
        self.op_temp = op_temp
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(theme.BG_DARK))
        small = QFont()
        small.setPointSize(8)
        p.setFont(small)
        if self.r20 is None or not math.isfinite(self.r20) or self.r20 <= 0:
            p.setPen(QColor(theme.FG_DIM))
            p.drawText(self.rect(), Qt.AlignCenter, "R vs T — generate a heater first")
            p.end()
            return

        t_min, t_max = min(self.T_ROOM, self.op_temp), max(self.T_ROOM, self.op_temp)
        if t_max - t_min < 1:
            t_max = t_min + 100
        r_lo = self.r20 * (1 + res.CU_TCR * (t_min - 20))
        r_hi = self.r20 * (1 + res.CU_TCR * (t_max - 20))
        r_min, r_max = 0.0, max(r_lo, r_hi) * 1.08
        left, right, top, bottom = 46, 10, 20, 24
        plot = QRectF(left, top, self.width() - left - right, self.height() - top - bottom)

        def sx(t: float) -> float:
            return plot.left() + (t - t_min) / (t_max - t_min) * plot.width()

        def sy(r: float) -> float:
            return plot.bottom() - (r - r_min) / (r_max - r_min) * plot.height()

        # grid + axes labels
        p.setPen(QPen(QColor(theme.BG_LIGHT), 1))
        step_t = _nice_step((t_max - t_min) / 5)
        t = math.ceil(t_min / step_t) * step_t
        while t <= t_max + 1e-9:
            x = sx(t)
            p.setPen(QPen(QColor(theme.BG_LIGHT), 1))
            p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            p.setPen(QColor(theme.FG_DIM))
            p.drawText(QRectF(x - 20, plot.bottom() + 3, 40, 14), Qt.AlignCenter, f"{t:g}")
            t += step_t
        r_step = _nice_step(r_max / 4)
        r = 0.0
        while r <= r_max + 1e-9:
            y = sy(r)
            p.setPen(QPen(QColor(theme.BG_LIGHT), 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(theme.FG_DIM))
            p.drawText(QRectF(0, y - 7, left - 4, 14), Qt.AlignRight | Qt.AlignVCenter, f"{r:g}")
            r += r_step
        p.setPen(QColor(theme.FG_DIM))
        p.drawText(QRectF(plot.left(), self.height() - 13, plot.width(), 12), Qt.AlignCenter, "°C")
        p.save()
        p.translate(9, plot.center().y())
        p.rotate(-90)
        p.drawText(QRectF(-30, -7, 60, 14), Qt.AlignCenter, "Ω")
        p.restore()

        # curve
        path = QPainterPath()
        path.moveTo(sx(t_min), sy(r_lo))
        path.lineTo(sx(t_max), sy(r_hi))
        p.setPen(QPen(QColor(theme.GREEN), 2))
        p.drawPath(path)

        # markers
        for temp, col in ((self.T_ROOM, theme.CYAN), (self.op_temp, theme.ORANGE)):
            rv = self.r20 * (1 + res.CU_TCR * (temp - 20))
            x, y = sx(temp), sy(rv)
            p.setPen(QPen(QColor(col), 1, Qt.DashLine))
            p.drawLine(QPointF(x, plot.bottom()), QPointF(x, y))
            p.drawLine(QPointF(plot.left(), y), QPointF(x, y))
            p.setPen(QPen(QColor(col), 1.5))
            p.setBrush(QColor(col))
            p.drawEllipse(QPointF(x, y), 4, 4)
            label = f"{rv:.3g} Ω @ {temp:g} °C"
            tw = 110
            lx = x + 8 if x + 8 + tw < plot.right() else x - 8 - tw
            align = Qt.AlignLeft if lx > x else Qt.AlignRight
            p.setPen(QColor(col))
            p.drawText(QRectF(lx, y - 16, tw, 14), align | Qt.AlignVCenter, label)
        p.end()


def _nice_step(raw: float) -> float:
    if raw <= 0:
        return 1.0
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag
