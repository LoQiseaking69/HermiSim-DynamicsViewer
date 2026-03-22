"""Simulation control toolbar with state-aware buttons."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from physics_engine.simulation import Simulation

logger = logging.getLogger(__name__)


class SimulationControls(QWidget):
    """Control panel for simulation lifecycle and speed."""

    def __init__(
        self, simulation: Simulation, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._simulation = simulation
        self._init_ui()
        self._connect_signals()
        self._update_button_states("idle")

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # -- Transport controls --
        transport_group = QGroupBox("Transport")
        transport_layout = QHBoxLayout()

        self._start_btn = QPushButton("Start")
        self._pause_btn = QPushButton("Pause")
        self._stop_btn = QPushButton("Stop")
        self._reset_btn = QPushButton("Reset")
        self._step_btn = QPushButton("Step")

        for btn in (
            self._start_btn,
            self._pause_btn,
            self._stop_btn,
            self._reset_btn,
            self._step_btn,
        ):
            btn.setMinimumHeight(36)
            transport_layout.addWidget(btn)

        transport_group.setLayout(transport_layout)
        main_layout.addWidget(transport_group)

        # -- Speed controls --
        speed_group = QGroupBox("Playback Speed")
        speed_layout = QGridLayout()

        self._speed_slider = QSlider(Qt.Horizontal)
        self._speed_slider.setRange(1, 200)
        self._speed_slider.setValue(100)
        speed_layout.addWidget(QLabel("Speed:"), 0, 0)
        speed_layout.addWidget(self._speed_slider, 0, 1)

        self._speed_label = QLabel("1.00x")
        self._speed_label.setMinimumWidth(50)
        speed_layout.addWidget(self._speed_label, 0, 2)

        self._timestep_spin = QDoubleSpinBox()
        self._timestep_spin.setRange(0.0001, 0.1)
        self._timestep_spin.setDecimals(4)
        self._timestep_spin.setSingleStep(0.001)
        self._timestep_spin.setValue(0.002)
        speed_layout.addWidget(QLabel("Timestep (s):"), 1, 0)
        speed_layout.addWidget(self._timestep_spin, 1, 1, 1, 2)

        speed_group.setLayout(speed_layout)
        main_layout.addWidget(speed_group)

        # -- Status bar --
        self._status_label = QLabel("Status: Idle")
        self._status_label.setStyleSheet("font-weight: bold; padding: 4px;")
        main_layout.addWidget(self._status_label)

        self._time_label = QLabel("Sim time: 0.000 s")
        main_layout.addWidget(self._time_label)

        main_layout.addStretch()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._start_btn.clicked.connect(self._on_start)
        self._pause_btn.clicked.connect(self._on_pause)
        self._stop_btn.clicked.connect(self._on_stop)
        self._reset_btn.clicked.connect(self._on_reset)
        self._step_btn.clicked.connect(self._on_step)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)
        self._timestep_spin.valueChanged.connect(self._on_timestep_changed)

        self._simulation.state_changed.connect(self._update_button_states)
        self._simulation.time_updated.connect(self._on_time_updated)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    @Slot()
    def _on_start(self) -> None:
        try:
            self._simulation.start()
        except Exception as exc:
            logger.error("Start failed: %s", exc)

    @Slot()
    def _on_pause(self) -> None:
        self._simulation.pause()

    @Slot()
    def _on_stop(self) -> None:
        self._simulation.stop()

    @Slot()
    def _on_reset(self) -> None:
        self._simulation.reset()

    @Slot()
    def _on_step(self) -> None:
        try:
            self._simulation.single_step()
        except Exception as exc:
            logger.error("Single step failed: %s", exc)

    @Slot(int)
    def _on_speed_changed(self, value: int) -> None:
        speed = value / 100.0
        self._speed_label.setText(f"{speed:.2f}x")
        self._simulation.set_speed(speed)

    @Slot(float)
    def _on_timestep_changed(self, dt: float) -> None:
        try:
            self._simulation.set_timestep(dt)
        except Exception:
            pass

    @Slot(float)
    def _on_time_updated(self, sim_time: float) -> None:
        self._time_label.setText(f"Sim time: {sim_time:.3f} s")

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @Slot(str)
    def _update_button_states(self, state: str) -> None:
        running = state == "running"
        paused = state == "paused"
        idle = state in ("idle", "error")

        self._start_btn.setEnabled(idle or paused)
        self._pause_btn.setEnabled(running)
        self._stop_btn.setEnabled(running or paused)
        self._reset_btn.setEnabled(True)
        self._step_btn.setEnabled(idle or paused)
        self._timestep_spin.setEnabled(idle or paused)

        self._status_label.setText(f"Status: {state.capitalize()}")