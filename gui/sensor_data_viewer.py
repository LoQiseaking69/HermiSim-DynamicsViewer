"""Real-time sensor data display widget."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import numpy as np
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from physics_engine.simulation import Simulation

logger = logging.getLogger(__name__)


class SensorDataViewer(QWidget):
    """Table-based sensor data viewer driven by simulation signals."""

    def __init__(
        self, simulation: Simulation, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._simulation = simulation
        self._init_ui()
        self._simulation.sensor_data_updated.connect(self._update_data)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._label = QLabel("Sensor Data")
        self._label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self._label)

        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Sensor", "Value"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

    def _update_data(self, sensor_data: dict) -> None:
        self._table.setRowCount(len(sensor_data))
        for row, (name, value) in enumerate(sorted(sensor_data.items())):
            self._table.setItem(row, 0, QTableWidgetItem(name))
            formatted = self._format_value(value)
            self._table.setItem(row, 1, QTableWidgetItem(formatted))

    @staticmethod
    def _format_value(value) -> str:
        if isinstance(value, np.ndarray):
            with np.printoptions(precision=4, suppress=True):
                return str(value)
        return str(value)