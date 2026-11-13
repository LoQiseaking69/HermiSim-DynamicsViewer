"""Live telemetry plots fed by Tulpa's tlm:: module (pyqtgraph)."""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QSplitter, QVBoxLayout, QWidget)

from gui.ide import theme

try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover
    pg = None

PALETTE = [theme.CYAN, theme.VIOLET, theme.MAGENTA, theme.GREEN, theme.AMBER, "#59a8ff", "#ff8f6b", "#4fe0c8"]


class TelemetryPanel(QWidget):
    def __init__(self, parent=None, maxlen: int = 6000) -> None:
        super().__init__(parent)
        self.maxlen = maxlen
        self.series: dict[str, tuple[deque, deque]] = {}
        self.curves: dict[str, object] = {}
        self.units: dict[str, str] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 4, 8, 4)
        self.info = QLabel("Telemetry: call tlm::plot(\"name\", value) from Tulpa")
        self.info.setStyleSheet(f"color:{theme.MUTED};")
        bar.addWidget(self.info)
        bar.addStretch()
        for label, fn in [("Auto-range", self._autorange), ("Clear", self.clear)]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            bar.addWidget(b)
        lay.addLayout(bar)
        split = QSplitter(Qt.Horizontal)
        self.list = QListWidget()
        self.list.setMaximumWidth(220)
        self.list.itemChanged.connect(self._toggle)
        split.addWidget(self.list)
        if pg is not None:
            pg.setConfigOptions(antialias=True, background=theme.BG1, foreground=theme.MUTED)
            self.plot = pg.PlotWidget()
            self.plot.showGrid(x=True, y=True, alpha=0.15)
            self.plot.addLegend(offset=(10, 10), labelTextColor=theme.TEXT)
            self.plot.setLabel("bottom", "time", units="s")
            split.addWidget(self.plot)
        else:
            self.plot = None
            split.addWidget(QLabel("install pyqtgraph for live plots"))
        split.setStretchFactor(1, 1)
        lay.addWidget(split)
        self._dirty = False
        self._timer = QTimer(self, interval=100)
        self._timer.timeout.connect(self._redraw)
        self._timer.start()

    def clear(self) -> None:
        self.series.clear()
        self.list.clear()
        if self.plot is not None:
            for c in self.curves.values():
                self.plot.removeItem(c)
        self.curves.clear()

    def add(self, name: str, t: float, v: float, unit=None) -> None:
        if name not in self.series:
            self.series[name] = (deque(maxlen=self.maxlen), deque(maxlen=self.maxlen))
            if unit:
                self.units[name] = unit
            color = PALETTE[len(self.curves) % len(PALETTE)]
            it = QListWidgetItem(name + (f"  [{unit}]" if unit else ""))
            it.setData(Qt.UserRole, name)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if len(self.curves) < 4 else Qt.Unchecked)
            it.setForeground(pg.mkColor(color) if pg else Qt.white)
            if self.plot is not None:
                curve = self.plot.plot([], [], name=name, pen=pg.mkPen(color, width=2))
                curve.setVisible(it.checkState() == Qt.Checked)
                self.curves[name] = curve
            self.list.addItem(it)
        xs, ys = self.series[name]
        xs.append(t)
        ys.append(v)
        self._dirty = True

    def _toggle(self, it) -> None:
        c = self.curves.get(it.data(Qt.UserRole))
        if c is not None:
            c.setVisible(it.checkState() == Qt.Checked)

    def _redraw(self) -> None:
        if not self._dirty or self.plot is None:
            return
        self._dirty = False
        for name, (xs, ys) in self.series.items():
            c = self.curves.get(name)
            if c is not None and c.isVisible():
                c.setData(list(xs), list(ys))
        self.info.setText(f"{len(self.series)} series · {sum(len(x) for x, _ in self.series.values())} samples")

    def _autorange(self) -> None:
        if self.plot is not None:
            self.plot.enableAutoRange()
