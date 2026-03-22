"""Sensor abstraction for MuJoCo-backed simulations.

In MuJoCo, sensors are defined in the model file (MJCF/URDF). This module
provides a higher-level :class:`SensorManager` that reads from
``engine.data.sensordata`` with named lookups and optional history tracking.
"""

from __future__ import annotations

import logging
from typing import Optional

import mujoco
import numpy as np

from physics_engine.engine import PhysicsEngine
from physics_engine.exceptions import SensorError

logger = logging.getLogger(__name__)


class SensorManager:
    """Structured access to MuJoCo model sensors with history tracking."""

    def __init__(
        self, engine: PhysicsEngine, history_length: int = 500
    ) -> None:
        self._engine = engine
        self._history_length = max(1, history_length)
        self._history: dict[str, list[np.ndarray]] = {}

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def available_sensors(self) -> list[str]:
        """Return names of all sensors defined in the loaded model."""
        if not self._engine.is_initialized:
            return []
        names: list[str] = []
        for i in range(self._engine.model.nsensor):
            name = mujoco.mj_id2name(
                self._engine.model, mujoco.mjtObj.mjOBJ_SENSOR, i
            )
            names.append(name or f"sensor_{i}")
        return names

    def read(self, sensor_name: str) -> np.ndarray:
        """Read the current value of a named sensor."""
        return self._engine.get_sensor_data(sensor_name)

    def read_all(self) -> dict[str, np.ndarray]:
        """Read all sensors and append to rolling history."""
        data = self._engine.get_all_sensor_data()
        for name, value in data.items():
            hist = self._history.setdefault(name, [])
            hist.append(value.copy())
            if len(hist) > self._history_length:
                hist.pop(0)
        return data

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(self, sensor_name: str) -> Optional[np.ndarray]:
        """Return recorded history for *sensor_name* as a 2-D array."""
        hist = self._history.get(sensor_name)
        if not hist:
            return None
        return np.array(hist)

    def clear_history(self) -> None:
        """Clear all stored history."""
        self._history.clear()

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def sensor_info(self, sensor_name: str) -> dict:
        """Return metadata for a single sensor."""
        if not self._engine.is_initialized:
            raise SensorError("Engine not initialized")
        model = self._engine.model
        sid = mujoco.mj_name2id(
            model, mujoco.mjtObj.mjOBJ_SENSOR, sensor_name
        )
        if sid < 0:
            raise SensorError(f"Sensor '{sensor_name}' not found")
        return {
            "name": sensor_name,
            "type": int(model.sensor_type[sid]),
            "dim": int(model.sensor_dim[sid]),
            "adr": int(model.sensor_adr[sid]),
        }