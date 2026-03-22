"""Sensor data tab — displays real-time readings from MuJoCo sensors."""

from __future__ import annotations

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


class SensorTab(QWidget):
    """Tab that shows a live table of sensor data from the simulation."""

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
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Sensor", "Dimensions", "Value"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

    def _update_data(self, sensor_data: dict) -> None:
        self._table.setRowCount(len(sensor_data))
        for row, (name, value) in enumerate(sorted(sensor_data.items())):
            self._table.setItem(row, 0, QTableWidgetItem(name))
            dim = str(value.shape) if isinstance(value, np.ndarray) else "scalar"
            self._table.setItem(row, 1, QTableWidgetItem(dim))
            formatted = self._format_value(value)
            self._table.setItem(row, 2, QTableWidgetItem(formatted))

    @staticmethod
    def _format_value(value) -> str:
        if isinstance(value, np.ndarray):
            with np.printoptions(precision=4, suppress=True):
                return str(value)
        return str(value)
