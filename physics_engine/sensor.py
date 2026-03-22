"""Sensor manager — reads and tracks MuJoCo sensor data with rolling history."""

from __future__ import annotations

import logging
from collections import deque
from typing import Optional

import numpy as np

from physics_engine.engine import PhysicsEngine
from physics_engine.exceptions import SensorError

logger = logging.getLogger(__name__)


class SensorManager:
    """Reads from MuJoCo's built-in sensor system and maintains history.

    Sensors are defined in the MJCF model file (``<sensor>`` element).
    This class provides named access, rolling history, and metadata queries.
    """

    def __init__(self, engine: PhysicsEngine, history_length: int = 500) -> None:
        self._engine = engine
        self._history_length = history_length
        self._history: dict[str, deque[np.ndarray]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def available_sensors(self) -> list[str]:
        """Return names of all sensors in the loaded model."""
        if not self._engine.is_initialized:
            return []
        import mujoco
        model = self._engine.model
        names: list[str] = []
        for i in range(model.nsensor):
            name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_SENSOR, i)
            names.append(name or f"sensor_{i}")
        return names

    def read(self, sensor_name: str) -> np.ndarray:
        """Read the latest value for *sensor_name*."""
        try:
            return self._engine.get_sensor_data(sensor_name)
        except (ValueError, Exception) as exc:
            raise SensorError(f"Cannot read sensor '{sensor_name}': {exc}") from exc

    def read_all(self) -> dict[str, np.ndarray]:
        """Read all sensors and update history; return {name: value}."""
        data = self._engine.get_all_sensor_data()
        for name, value in data.items():
            if name not in self._history:
                self._history[name] = deque(maxlen=self._history_length)
            self._history[name].append(value.copy())
        return data

    def get_history(self, sensor_name: str) -> Optional[np.ndarray]:
        """Return the rolling history for *sensor_name* as a 2-D array."""
        hist = self._history.get(sensor_name)
        if hist is None or len(hist) == 0:
            return None
        return np.array(hist)

    def sensor_info(self, sensor_name: str) -> dict:
        """Return metadata about a sensor (dimension, address, etc.)."""
        if not self._engine.is_initialized:
            raise SensorError("Engine not initialized")
        import mujoco
        model = self._engine.model
        sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, sensor_name)
        if sid < 0:
            raise SensorError(f"Sensor '{sensor_name}' not found")
        return {
            "name": sensor_name,
            "id": sid,
            "dim": int(model.sensor_dim[sid]),
            "adr": int(model.sensor_adr[sid]),
        }

    def clear_history(self) -> None:
        """Clear all recorded sensor history."""
        self._history.clear()
