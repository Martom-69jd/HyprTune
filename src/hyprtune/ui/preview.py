"""A tiny live rendering of your tiling setup: gaps, borders, rounding, opacity, shadows, layout."""
from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from .widgets import qcolor

SCREEN_W, SCREEN_H = 1920.0, 1080.0


def dwindle(area: QRectF, n: int, ratio: float, wide_bias: float) -> list[QRectF]:
    out, r = [], QRectF(area)
    f = min(max(ratio / 2.0, 0.05), 0.95)
    for _ in range(n - 1):
        if r.width() >= r.height() * wide_bias:
            a = QRectF(r.x(), r.y(), r.width() * f, r.height())
            r = QRectF(a.right(), r.y(), r.width() - a.width(), r.height())
        else:
            a = QRectF(r.x(), r.y(), r.width(), r.height() * f)
            r = QRectF(r.x(), a.bottom(), r.width(), r.height() - a.height())
        out.append(a)
    out.append(r)
    return out


def _stack(r: QRectF, count: int, vertical: bool) -> list[QRectF]:
    if count <= 0:
        return []
    if vertical:
        h = r.height() / count
        return [QRectF(r.x(), r.y() + i * h, r.width(), h) for i in range(count)]
    w = r.width() / count
    return [QRectF(r.x() + i * w, r.y(), w, r.height()) for i in range(count)]


def master(area: QRectF, n: int, mfact: float, orientation: str) -> list[QRectF]:
    m = min(max(mfact, 0.1), 0.9)
    slaves = n - 1
    x, y, w, h = area.x(), area.y(), area.width(), area.height()
    if orientation == "right":
        return [QRectF(x + w * (1 - m), y, w * m, h)] + _stack(QRectF(x, y, w * (1 - m), h), slaves, True)
    if orientation == "top":
        return [QRectF(x, y, w, h * m)] + _stack(QRectF(x, y + h * m, w, h * (1 - m)), slaves, False)
    if orientation == "bottom":
        return [QRectF(x, y + h * (1 - m), w, h * m)] + _stack(QRectF(x, y, w, h * (1 - m)), slaves, False)
    if orientation == "center" and slaves >= 2:
        side = w * (1 - m) / 2
        right_n = (slaves + 1) // 2
        left_n = slaves - right_n
        return ([QRectF(x + side, y, w * m, h)] + _stack(QRectF(x + side + w * m, y, side, h), right_n, True)
                + _stack(QRectF(x, y, side, h), left_n, True))
    return [QRectF(x, y, w * m, h)] + _stack(QRectF(x + w * m, y, w * (1 - m), h), slaves, True)


def scrolling(area: QRectF, n: int, col_w: float) -> list[QRectF]:
    cw = area.width() * min(max(col_w, 0.1), 1.0)
    x0 = area.x() + (area.width() - cw) / 2 - cw  # focused column (index 1) centred
    return [QRectF(x0 + i * cw, area.y(), cw, area.height()) for i in range(n)]


class DesktopPreview(QWidget):
    def __init__(self, model: Any) -> None:
        super().__init__()
        self.model = model
        self.setFixedHeight(246)
        model.optionChanged.connect(lambda _k: self.update())
        model.refreshed.connect(self.update)

    def v(self, key: str) -> Any:
        return self.model.value(key)

    # -- geometry -------------------------------------------------------------------------------------
    def tiles(self) -> tuple[list[QRectF], int]:
        gi, go = float(self.v("general:gaps_in")), float(self.v("general:gaps_out"))
        d = go - gi
        area = QRectF(d, d, SCREEN_W - 2 * d, SCREEN_H - 2 * d)
        layout = self.v("general:layout")
        if layout == "master":
            return master(area, 4, float(self.v("master:mfact")), self.v("master:orientation")), 0
        if layout == "scrolling":
            return scrolling(area, 4, float(self.v("scrolling:column_width"))), 1
        if layout == "monocle":
            return [area], 0
        return dwindle(area, 4, float(self.v("dwindle:default_split_ratio")),
                       float(self.v("dwindle:split_width_multiplier"))), 0

    # -- painting -------------------------------------------------------------------------------------
    def paintEvent(self, _e: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        pal = self.palette()
        p.fillRect(self.rect(), pal.color(pal.ColorRole.AlternateBase))
        p.setPen(QPen(pal.color(pal.ColorRole.Mid), 1))
        p.drawLine(0, H - 1, W, H - 1)
        sh = H - 36.0
        sw = sh * 16 / 9
        if sw > W - 64:
            sw = W - 64.0
            sh = sw * 9 / 16
        stage = QRectF((W - sw) / 2, (H - sh) / 2, sw, sh)
        k = sw / SCREEN_W

        clip = QPainterPath()
        clip.addRoundedRect(stage, 9, 9)
        p.save()
        p.setClipPath(clip)
        bg = QLinearGradient(stage.topLeft(), stage.bottomRight())
        bg.setColorAt(0, QColor("#33406e"))
        bg.setColorAt(0.55, QColor("#241f3d"))
        bg.setColorAt(1, QColor("#14182b"))
        p.fillRect(stage, bg)
        glow = QRadialGradient(stage.center() + QPointF(sw * 0.22, -sh * 0.2), sw * 0.45)
        glow.setColorAt(0, QColor(90, 200, 220, 70))
        glow.setColorAt(1, QColor(90, 200, 220, 0))
        p.fillRect(stage, glow)

        rects, active = self.tiles()
        gi = float(self.v("general:gaps_in"))
        scaled = []
        for r in rects:
            r = r.adjusted(gi, gi, -gi, -gi)
            scaled.append(QRectF(stage.x() + r.x() * k, stage.y() + r.y() * k, r.width() * k, r.height() * k))
        for i, r in enumerate(scaled):
            if self.v("decoration:shadow:enabled"):
                self._shadow(p, r, k)
        for i, r in enumerate(scaled):
            self._window(p, r, i == active, k, i)
        p.restore()
        p.setPen(QPen(QColor(255, 255, 255, 28), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(stage, 9, 9)

    def _shadow(self, p: QPainter, r: QRectF, k: float) -> None:
        col = self.v("decoration:shadow:color")
        base = qcolor(col["colors"][0]) if col.get("colors") else QColor(0, 0, 0, 200)
        reach = max(float(self.v("decoration:shadow:range")) * k * float(self.v("decoration:shadow:scale") or 1), 1)
        rad = float(self.v("decoration:rounding")) * k
        steps = 7
        p.setPen(Qt.NoPen)
        for s in range(steps, 0, -1):
            grow = reach * s / steps
            c = QColor(base)
            c.setAlphaF(min(1.0, base.alphaF() * 0.16 * (1 - s / (steps + 1)) ** 1.5))
            p.setBrush(c)
            p.drawRoundedRect(r.adjusted(-grow, -grow, grow, grow), rad + grow, rad + grow)

    def _border_brush(self, key: str, r: QRectF) -> QBrush:
        g = self.v(key)
        cols = [qcolor(c) for c in g.get("colors", [])] or [QColor(255, 255, 255, 200)]
        if len(cols) == 1:
            return QBrush(cols[0])
        a = math.radians(float(g.get("angle", 0)))
        c, half = r.center(), (abs(r.width() * math.cos(a)) + abs(r.height() * math.sin(a))) / 2
        d = QPointF(math.cos(a), math.sin(a)) * half
        grad = QLinearGradient(c - d, c + d)
        for i, col in enumerate(cols):
            grad.setColorAt(i / (len(cols) - 1), col)
        return QBrush(grad)

    def _window(self, p: QPainter, r: QRectF, active: bool, k: float, idx: int) -> None:
        rad = max(float(self.v("decoration:rounding")) * k, 0)
        bw = float(self.v("general:border_size"))
        bw = 0 if bw <= 0 else max(bw * k, 1.0)
        opacity = float(self.v("decoration:active_opacity" if active else "decoration:inactive_opacity"))
        half = bw / 2
        body = r.adjusted(half, half, -half, -half)
        fill = QColor("#232837")
        fill.setAlphaF(min(max(opacity, 0.05), 1.0))
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawRoundedRect(body, max(rad - half, 0), max(rad - half, 0))
        # text-like bars so the windows read as windows
        bar = QColor(255, 255, 255, 46 if active else 28)
        p.setBrush(bar)
        pad = max(min(r.width(), r.height()) * 0.1, 3)
        y = r.y() + pad * 1.4
        for j, frac in enumerate((0.55, 0.8, 0.4, 0.65)):
            bw_ = (r.width() - 2 * pad) * frac
            if y + 3 > r.bottom() - pad or bw_ <= 2:
                break
            p.drawRoundedRect(QRectF(r.x() + pad, y, bw_, 3), 1.5, 1.5)
            y += 8
        if not active and self.v("decoration:dim_inactive"):
            dim = QColor(0, 0, 0)
            dim.setAlphaF(float(self.v("decoration:dim_strength")))
            p.setBrush(dim)
            p.drawRoundedRect(body, max(rad - half, 0), max(rad - half, 0))
        if bw > 0:
            pen = QPen(self._border_brush("general:col.active_border" if active else "general:col.inactive_border", r), bw)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(body, max(rad - half, 0), max(rad - half, 0))
