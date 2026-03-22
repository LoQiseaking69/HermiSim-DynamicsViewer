"""Simulation lifecycle controller with threaded physics stepping.

The :class:`Simulation` object owns a :class:`PhysicsEngine` and delegates
continuous stepping to a background ``QThread``.  All state transitions and
data updates are communicated via Qt signals so the GUI never blocks.
"""

from __future__ import annotations

import enum
import logging
from typing import Optional

import numpy as np
from PySide6.QtCore import QMutex, QMutexLocker, QObject, QThread, Signal, Slot

from physics_engine.engine import PhysicsEngine
from physics_engine.exceptions import SimulationStateError

logger = logging.getLogger(__name__)


# ======================================================================
# Simulation state
# ======================================================================

class SimulationState(enum.Enum):
    """Possible states of the simulation."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


# ======================================================================
# Worker (runs on a dedicated QThread)
# ======================================================================

class _SimulationWorker(QObject):
    """Worker that runs the physics loop on a dedicated QThread."""

    stepped = Signal(float)       # simulation time after step
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, engine: PhysicsEngine) -> None:
        super().__init__()
        self._engine = engine
        self._running = False
        self._paused = False
        self._speed_multiplier: float = 1.0
        self._mutex = QMutex()

    @Slot()
    def run(self) -> None:
        """Main simulation loop — invoked when the owning thread starts."""
        self._running = True
        logger.info("Simulation worker started")
        try:
            while self._running:
                with QMutexLocker(self._mutex):
                    paused = self._paused
                    speed = self._speed_multiplier

                if paused:
                    QThread.msleep(50)
                    continue

                dt = self._engine.get_timestep()
                wall_delay = dt / speed if speed > 0 else dt

                self._engine.step()
                sim_time = self._engine.simulation_time
                self.stepped.emit(sim_time)

                # Throttle to approximate real-time × speed_multiplier
                sleep_ms = max(1, int(wall_delay * 1000))
                QThread.msleep(sleep_ms)
        except Exception as exc:
            logger.exception("Simulation worker error")
            self.error_occurred.emit(str(exc))
        finally:
            self._running = False
            self.finished.emit()
            logger.info("Simulation worker stopped")

    def request_stop(self) -> None:
        self._running = False

    def set_paused(self, paused: bool) -> None:
        with QMutexLocker(self._mutex):
            self._paused = paused

    def set_speed(self, multiplier: float) -> None:
        with QMutexLocker(self._mutex):
            self._speed_multiplier = max(0.01, multiplier)


# ======================================================================
# Simulation controller
# ======================================================================

class Simulation(QObject):
    """High-level simulation controller.

    Manages the :class:`PhysicsEngine` lifecycle and delegates continuous
    stepping to a background :class:`_SimulationWorker` on a ``QThread``.
    """

    # Signals
    state_changed = Signal(str)            # new SimulationState value
    time_updated = Signal(float)           # simulation time
    sensor_data_updated = Signal(dict)     # sensor name -> values
    model_loaded = Signal(dict)            # model info dict
    error_occurred = Signal(str)
    frame_rendered = Signal(np.ndarray)    # RGB frame for display

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.engine = PhysicsEngine()
        self._state = SimulationState.IDLE
        self._thread: Optional[QThread] = None
        self._worker: Optional[_SimulationWorker] = None
        self._speed: float = 1.0
        self._render_enabled: bool = True

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> SimulationState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == SimulationState.RUNNING

    @property
    def robot(self):
        """Legacy compatibility — returns the engine if a model is loaded."""
        return self.engine if self.engine.is_initialized else None

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self, path: str) -> None:
        """Load a model file (MJCF XML or URDF)."""
        if self._state == SimulationState.RUNNING:
            self.stop()
        self.engine.load_model_from_path(path)
        info = self.engine.get_model_info()
        self._set_state(SimulationState.IDLE)
        self.model_loaded.emit(info)
        logger.info("Model loaded: %s — %s", path, info)

    # Legacy alias
    def load_robot(self, path: str, base_position: tuple = (0, 0, 1)) -> None:
        self.load_model(path)

    # ------------------------------------------------------------------
    # Simulation control
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start (or resume) the simulation."""
        if self._state == SimulationState.RUNNING:
            logger.warning("Simulation already running")
            return
        if not self.engine.is_initialized:
            raise SimulationStateError("Cannot start: no model loaded")

        if self._state == SimulationState.PAUSED and self._worker is not None:
            self._worker.set_paused(False)
            self._set_state(SimulationState.RUNNING)
            return

        # Start fresh worker thread
        self._thread = QThread()
        self._worker = _SimulationWorker(self.engine)
        self._worker.set_speed(self._speed)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.stepped.connect(self._on_step)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)

        self._thread.start()
        self._set_state(SimulationState.RUNNING)

    def pause(self) -> None:
        """Pause the running simulation."""
        if self._state != SimulationState.RUNNING:
            return
        if self._worker is not None:
            self._worker.set_paused(True)
        self._set_state(SimulationState.PAUSED)

    def stop(self) -> None:
        """Stop the simulation and tear down the worker thread."""
        if self._worker is not None:
            self._worker.request_stop()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(5000)
        self._worker = None
        self._thread = None
        self._set_state(SimulationState.IDLE)

    def reset(self) -> None:
        """Stop and reset the simulation to its initial state."""
        was_running = self._state == SimulationState.RUNNING
        self.stop()
        if self.engine.is_initialized:
            self.engine.reset()
        if was_running:
            self.start()

    def single_step(self) -> None:
        """Advance by exactly one timestep (useful while paused)."""
        if not self.engine.is_initialized:
            raise SimulationStateError("No model loaded")
        self.engine.step()
        self._on_step(self.engine.simulation_time)

    # ------------------------------------------------------------------
    # Speed / configuration
    # ------------------------------------------------------------------

    def set_speed(self, speed: float) -> None:
        """Set playback speed multiplier (1.0 = real-time)."""
        self._speed = max(0.01, speed)
        if self._worker is not None:
            self._worker.set_speed(self._speed)

    def set_timestep(self, dt: float) -> None:
        self.engine.set_timestep(dt)

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def get_sensor_data(self) -> dict:
        """Return current sensor readings as {name: value_array}."""
        if not self.engine.is_initialized:
            return {}
        try:
            return self.engine.get_all_sensor_data()
        except Exception:
            return {}

    def render_frame(
        self, camera_name: Optional[str] = None
    ) -> Optional[np.ndarray]:
        """Render a frame and return the RGB array."""
        if not self.engine.is_initialized:
            return None
        try:
            return self.engine.render(camera_name)
        except Exception:
            logger.debug("Render failed", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Slots / internal
    # ------------------------------------------------------------------

    def _on_step(self, sim_time: float) -> None:
        self.time_updated.emit(sim_time)
        sensor = self.get_sensor_data()
        if sensor:
            self.sensor_data_updated.emit(sensor)
        if self._render_enabled:
            frame = self.render_frame()
            if frame is not None:
                self.frame_rendered.emit(frame)

    def _on_error(self, message: str) -> None:
        logger.error("Simulation error: %s", message)
        self._set_state(SimulationState.ERROR)
        self.error_occurred.emit(message)

    def _on_thread_finished(self) -> None:
        if self._state == SimulationState.RUNNING:
            self._set_state(SimulationState.IDLE)

    def _set_state(self, new_state: SimulationState) -> None:
        if self._state != new_state:
            old = self._state
            self._state = new_state
            logger.info(
                "Simulation state: %s -> %s", old.value, new_state.value
            )
            self.state_changed.emit(new_state.value)