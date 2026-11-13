"""VCD waveform viewer for std/rtl simulations (and any IEEE 1364 VCD file)."""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget)

from gui.ide import theme


@dataclass
class VcdSignal:
    name: str
    width: int
    times: list = field(default_factory=list)
    values: list = field(default_factory=list)

    def value_at(self, t: int):
        i = bisect.bisect_right(self.times, t) - 1
        return self.values[i] if i >= 0 else None


def parse_vcd(text: str) -> tuple[dict, int, str]:
    sigs: dict[str, VcdSignal] = {}
    by_id: dict[str, list[VcdSignal]] = {}
    scope: list[str] = []
    timescale = "1ns"
    t = 0
    tokens = iter(text.split())
    for tok in tokens:
        if tok == "$scope":
            next(tokens)
            scope.append(next(tokens))
            next(tokens)
        elif tok == "$upscope":
            scope.pop()
            next(tokens)
        elif tok == "$timescale":
            parts = []
            for x in tokens:
                if x == "$end":
                    break
                parts.append(x)
            timescale = "".join(parts)
        elif tok == "$var":
            _kind, width, ident, ref = next(tokens), int(next(tokens)), next(tokens), next(tokens)
            for x in tokens:
                if x == "$end":
                    break
            path = ".".join(scope[1:] + [ref]) if len(scope) > 1 else ref
            s = VcdSignal(path, width)
            sigs[path] = s
            by_id.setdefault(ident, []).append(s)
        elif tok.startswith("$"):
            if tok in ("$dumpvars", "$end", "$enddefinitions"):
                continue
            for x in tokens:
                if x == "$end":
                    break
        elif tok.startswith("#"):
            t = int(tok[1:])
        elif tok[0] in "bBrR":
            val, ident = tok[1:], next(tokens)
            try:
                v = int(val, 2)
            except ValueError:
                v = None
            for s in by_id.get(ident, []):
                s.times.append(t)
                s.values.append(v)
        elif tok[0] in "01xXzZ":
            v = int(tok[0]) if tok[0] in "01" else None
            for s in by_id.get(tok[1:], []):
                s.times.append(t)
                s.values.append(v)
    return sigs, t, timescale


class _Waves(QWidget):
    cursor_moved = Signal(int)
    ROW = 26
    NAME_W = 0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.signals: list[VcdSignal] = []
        self.t_end = 1
        self.t0, self.t1 = 0, 1
        self.cursor_t = 0
        self.setMouseTracking(True)
        self.setMinimumHeight(200)
        self._drag = None

    def set_data(self, signals, t_end) -> None:
        self.signals = signals
        self.t_end = max(1, t_end)
        self.t0, self.t1 = 0, self.t_end
        self.setMinimumHeight(30 + self.ROW * len(signals))
        self.update()

    def x_of(self, t) -> float:
        return (t - self.t0) / max(1e-9, self.t1 - self.t0) * self.width()

    def t_of(self, x) -> int:
        return int(self.t0 + x / max(1, self.width()) * (self.t1 - self.t0))

    def paintEvent(self, _) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(theme.BG1))
        f = QFont(theme.mono_font(9))
        p.setFont(f)
        # time ruler
        p.setPen(QColor(theme.LINE2))
        span = self.t1 - self.t0
        step = 10 ** max(0, len(str(int(span / 8))) - 1)
        while span / step > 12:
            step *= 2
        t = (self.t0 // step) * step
        while t <= self.t1:
            x = self.x_of(t)
            p.setPen(QColor(theme.LINE))
            p.drawLine(QPointF(x, 18), QPointF(x, self.height()))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QPointF(x + 3, 13), f"{t}")
            t += step
        for i, s in enumerate(self.signals):
            y = 24 + i * self.ROW
            mid, hi, lo = y + self.ROW / 2, y + 5, y + self.ROW - 5
            color = QColor(theme.CYAN if s.width == 1 else theme.GREEN)
            p.setPen(QPen(color, 1.4))
            k = max(0, bisect.bisect_right(s.times, self.t0) - 1)
            n = len(s.times)
            if s.width == 1:
                path = QPainterPath()
                started = False
                while k < n:
                    ta = s.times[k]
                    tb = s.times[k + 1] if k + 1 < n else self.t_end
                    xa, xb = max(0.0, self.x_of(ta)), min(float(self.width()), self.x_of(tb))
                    yv = hi if s.values[k] == 1 else lo if s.values[k] == 0 else mid
                    if not started:
                        path.moveTo(xa, yv)
                        started = True
                    else:
                        path.lineTo(xa, yv)
                    path.lineTo(xb, yv)
                    if ta > self.t1:
                        break
                    k += 1
                p.drawPath(path)
            else:
                while k < n:
                    ta = s.times[k]
                    if ta > self.t1:
                        break
                    tb = s.times[k + 1] if k + 1 < n else self.t_end
                    xa, xb = max(0.0, self.x_of(ta)), min(float(self.width()), self.x_of(tb))
                    if xb - xa > 1:
                        poly = QPainterPath()
                        e = min(3.0, (xb - xa) / 2)
                        poly.moveTo(xa, mid)
                        poly.lineTo(xa + e, hi)
                        poly.lineTo(xb - e, hi)
                        poly.lineTo(xb, mid)
                        poly.lineTo(xb - e, lo)
                        poly.lineTo(xa + e, lo)
                        poly.closeSubpath()
                        p.fillPath(poly, QColor(10, 60, 45))
                        p.drawPath(poly)
                        v = s.values[k]
                        txt = "x" if v is None else f"{v:x}"
                        if p.fontMetrics().horizontalAdvance(txt) < xb - xa - 8:
                            p.setPen(QColor(theme.TEXT))
                            p.drawText(QRectF(xa, hi, xb - xa, lo - hi), Qt.AlignCenter, txt)
                            p.setPen(QPen(color, 1.4))
                    k += 1
        x = self.x_of(self.cursor_t)
        p.setPen(QPen(QColor(theme.MAGENTA), 1, Qt.DashLine))
        p.drawLine(QPointF(x, 0), QPointF(x, self.height()))

    def wheelEvent(self, e) -> None:  # noqa: N802
        tc = self.t_of(e.position().x())
        k = 0.8 if e.angleDelta().y() > 0 else 1.25
        self.t0 = max(0, int(tc - (tc - self.t0) * k))
        self.t1 = min(self.t_end, max(self.t0 + 2, int(tc + (self.t1 - tc) * k)))
        self.update()

    def mousePressEvent(self, e) -> None:  # noqa: N802
        self._drag = (e.position().x(), self.t0, self.t1)
        self.cursor_t = self.t_of(e.position().x())
        self.cursor_moved.emit(self.cursor_t)
        self.update()

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if self._drag and e.buttons() & Qt.RightButton:
            x0, a, b = self._drag
            dt = int((x0 - e.position().x()) / max(1, self.width()) * (b - a))
            dt = max(-a, min(self.t_end - b, dt))
            self.t0, self.t1 = a + dt, b + dt
            self.update()
        elif e.buttons() & Qt.LeftButton:
            self.cursor_t = self.t_of(e.position().x())
            self.cursor_moved.emit(self.cursor_t)
            self.update()

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        self._drag = None


class VcdViewer(QWidget):
    def __init__(self, path: str, parent=None) -> None:
        super().__init__(parent)
        self.path = path
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 4, 8, 4)
        self.info = QLabel("")
        self.info.setStyleSheet(f"color:{theme.MUTED};")
        self.search = QLineEdit(placeholderText="filter signals (e.g. core.)")
        self.search.setMaximumWidth(260)
        bar.addWidget(self.info)
        bar.addStretch()
        bar.addWidget(self.search)
        for label, fn in [("Fit", self.fit), ("Reload", self.reload)]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            bar.addWidget(b)
        lay.addLayout(bar)
        split = QSplitter(Qt.Horizontal)
        self.names = QListWidget()
        self.names.setFont(theme.mono_font(9))
        self.names.setMaximumWidth(330)
        self.names.setSpacing(0)
        self.waves = _Waves()
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(self.waves)
        split.addWidget(self.names)
        split.addWidget(sc)
        split.setStretchFactor(1, 1)
        lay.addWidget(split)
        self.waves.cursor_moved.connect(self._update_values)
        self.search.textChanged.connect(self._apply_filter)
        self.all: dict = {}
        self.reload()

    @property
    def title(self) -> str:
        return "⏚ " + Path(self.path).name

    def reload(self) -> None:
        self.all, self.t_end, self.timescale = parse_vcd(Path(self.path).read_text())
        self._apply_filter()
        self.info.setText(f"{len(self.all)} signals · 0 – {self.t_end} × {self.timescale} · wheel = zoom, right-drag = pan, click = cursor")

    def _apply_filter(self) -> None:
        q = self.search.text().lower()
        shown = [s for n, s in self.all.items() if q in n.lower()]
        self.waves.set_data(shown, self.t_end)
        self._update_values(self.waves.cursor_t)

    def _update_values(self, t: int) -> None:
        self.names.clear()
        for s in self.waves.signals:
            v = s.value_at(t)
            vs = "x" if v is None else (str(v) if s.width == 1 else f"0x{v:x}")
            it = QListWidgetItem(f"{s.name}  =  {vs}")
            it.setSizeHint(QSize(300, _Waves.ROW))
            self.names.addItem(it)
        self.names.setStyleSheet(f"QListWidget {{ padding-top: 24px; }}")

    def fit(self) -> None:
        self.waves.t0, self.waves.t1 = 0, self.t_end
        self.waves.update()
