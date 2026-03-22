"""Simulation control tab."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from gui.simulation_controls import SimulationControls

if TYPE_CHECKING:
    from physics_engine.simulation import Simulation


class SimulationTab(QWidget):
    """Tab containing the simulation transport and speed controls."""

    def __init__(
        self, simulation: Simulation, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._simulation = simulation
        layout = QVBoxLayout(self)
        self._controls = SimulationControls(simulation)
        layout.addWidget(self._controls)