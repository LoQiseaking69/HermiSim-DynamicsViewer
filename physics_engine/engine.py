"""MuJoCo-backed physics engine with thread-safe lifecycle management."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

import mujoco
import numpy as np

from physics_engine.exceptions import EngineNotInitializedError, ModelLoadError

logger = logging.getLogger(__name__)


class PhysicsEngine:
    """Core wrapper around MuJoCo providing model loading, stepping, and rendering.

    All public methods are thread-safe through an internal reentrant lock.
    """

    _SUPPORTED_FORMATS = {".xml", ".mjcf", ".urdf"}

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._model: Optional[mujoco.MjModel] = None
        self._data: Optional[mujoco.MjData] = None
        self._renderer: Optional[mujoco.Renderer] = None
        self._render_width: int = 640
        self._render_height: int = 480

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def model(self) -> Optional[mujoco.MjModel]:
        return self._model

    @property
    def data(self) -> Optional[mujoco.MjData]:
        return self._data

    @property
    def is_initialized(self) -> bool:
        return self._model is not None and self._data is not None

    @property
    def simulation_time(self) -> float:
        self._require_initialized()
        return self._data.time

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load_model_from_path(self, path: str) -> None:
        """Load an MJCF or URDF model from *path*."""
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise ModelLoadError(f"Model file not found: {resolved}")

        suffix = resolved.suffix.lower()
        if suffix not in self._SUPPORTED_FORMATS:
            raise ModelLoadError(
                f"Unsupported model format '{suffix}'. "
                f"Supported: {', '.join(sorted(self._SUPPORTED_FORMATS))}"
            )

        with self._lock:
            try:
                self._model = mujoco.MjModel.from_xml_path(str(resolved))
                self._data = mujoco.MjData(self._model)
                self._renderer = None  # lazily recreated on next render
                logger.info("Model loaded: %s", resolved)
            except Exception as exc:
                self._model = None
                self._data = None
                raise ModelLoadError(
                    f"Failed to load model '{resolved}': {exc}"
                ) from exc

    def load_model_from_xml(self, xml_string: str) -> None:
        """Load a model from an MJCF XML string."""
        with self._lock:
            try:
                self._model = mujoco.MjModel.from_xml_string(xml_string)
                self._data = mujoco.MjData(self._model)
                self._renderer = None
                logger.info("Model loaded from XML string")
            except Exception as exc:
                self._model = None
                self._data = None
                raise ModelLoadError(
                    f"Failed to load model from XML: {exc}"
                ) from exc

    def reset(self) -> None:
        """Reset simulation state to the initial configuration."""
        with self._lock:
            self._require_initialized()
            mujoco.mj_resetData(self._model, self._data)
            mujoco.mj_forward(self._model, self._data)
            logger.debug("Simulation state reset")

    def close(self) -> None:
        """Release all resources held by the engine."""
        with self._lock:
            self._renderer = None
            self._data = None
            self._model = None
            logger.info("Physics engine resources released")

    # ------------------------------------------------------------------
    # Simulation stepping
    # ------------------------------------------------------------------

    def step(self) -> None:
        """Advance the simulation by one timestep."""
        with self._lock:
            self._require_initialized()
            mujoco.mj_step(self._model, self._data)

    def forward(self) -> None:
        """Compute forward kinematics without advancing time."""
        with self._lock:
            self._require_initialized()
            mujoco.mj_forward(self._model, self._data)

    # ------------------------------------------------------------------
    # Timestep
    # ------------------------------------------------------------------

    def get_timestep(self) -> float:
        self._require_initialized()
        return self._model.opt.timestep

    def set_timestep(self, dt: float) -> None:
        with self._lock:
            self._require_initialized()
            self._model.opt.timestep = dt

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def set_render_size(self, width: int, height: int) -> None:
        with self._lock:
            self._render_width = max(1, width)
            self._render_height = max(1, height)
            self._renderer = None  # force recreation

    def render(self, camera_name: Optional[str] = None,
               camera: Optional[mujoco.MjvCamera] = None) -> np.ndarray:
        """Render the scene, returning an RGB uint8 array (H, W, 3).

        If *camera* (an MjvCamera) is provided it takes precedence over
        *camera_name*.
        """
        with self._lock:
            self._require_initialized()
            if self._renderer is None:
                self._renderer = mujoco.Renderer(
                    self._model,
                    height=self._render_height,
                    width=self._render_width,
                )
            if camera is not None:
                self._renderer.update_scene(self._data, camera=camera)
            else:
                camera_id = -1
                if camera_name is not None:
                    camera_id = mujoco.mj_name2id(
                        self._model, mujoco.mjtObj.mjOBJ_CAMERA, camera_name
                    )
                    if camera_id < 0:
                        logger.warning(
                            "Camera '%s' not found — using free camera",
                            camera_name,
                        )
                        camera_id = -1
                self._renderer.update_scene(self._data, camera=camera_id)
            return self._renderer.render().copy()

    def render_depth(self, camera_name: Optional[str] = None) -> np.ndarray:
        """Render depth buffer, returning a float32 array (H, W)."""
        with self._lock:
            self._require_initialized()
            if self._renderer is None:
                self._renderer = mujoco.Renderer(
                    self._model,
                    height=self._render_height,
                    width=self._render_width,
                )
            camera_id = -1
            if camera_name is not None:
                camera_id = mujoco.mj_name2id(
                    self._model, mujoco.mjtObj.mjOBJ_CAMERA, camera_name
                )
            self._renderer.update_scene(self._data, camera=camera_id)
            self._renderer.enable_depth_rendering()
            depth = self._renderer.render().copy()
            self._renderer.disable_depth_rendering()
            return depth

    # ------------------------------------------------------------------
    # Body / joint queries
    # ------------------------------------------------------------------

    def get_body_position(self, body_name: str) -> np.ndarray:
        self._require_initialized()
        body_id = mujoco.mj_name2id(
            self._model, mujoco.mjtObj.mjOBJ_BODY, body_name
        )
        if body_id < 0:
            raise ValueError(f"Body '{body_name}' not found in model")
        return self._data.xpos[body_id].copy()

    def get_body_quaternion(self, body_name: str) -> np.ndarray:
        self._require_initialized()
        body_id = mujoco.mj_name2id(
            self._model, mujoco.mjtObj.mjOBJ_BODY, body_name
        )
        if body_id < 0:
            raise ValueError(f"Body '{body_name}' not found in model")
        return self._data.xquat[body_id].copy()

    def get_joint_positions(self) -> np.ndarray:
        self._require_initialized()
        return self._data.qpos.copy()

    def get_joint_velocities(self) -> np.ndarray:
        self._require_initialized()
        return self._data.qvel.copy()

    def set_joint_positions(self, qpos: np.ndarray) -> None:
        self._require_initialized()
        with self._lock:
            np.copyto(self._data.qpos, qpos)
            mujoco.mj_forward(self._model, self._data)

    # ------------------------------------------------------------------
    # Force / control
    # ------------------------------------------------------------------

    def set_control(self, ctrl: np.ndarray) -> None:
        """Set actuator control signals."""
        with self._lock:
            self._require_initialized()
            np.copyto(self._data.ctrl, ctrl)

    def apply_force(
        self, body_name: str, force: np.ndarray, torque: np.ndarray
    ) -> None:
        """Apply an external force and torque to a named body."""
        with self._lock:
            self._require_initialized()
            body_id = mujoco.mj_name2id(
                self._model, mujoco.mjtObj.mjOBJ_BODY, body_name
            )
            if body_id < 0:
                raise ValueError(f"Body '{body_name}' not found")
            self._data.xfrc_applied[body_id, :3] = force
            self._data.xfrc_applied[body_id, 3:] = torque

    def clear_forces(self) -> None:
        """Clear all applied external forces."""
        with self._lock:
            self._require_initialized()
            self._data.xfrc_applied[:] = 0

    # ------------------------------------------------------------------
    # Sensor data
    # ------------------------------------------------------------------

    def get_all_sensor_data(self) -> dict[str, np.ndarray]:
        """Return a dict mapping sensor name -> latest sensor reading."""
        with self._lock:
            self._require_initialized()
            result: dict[str, np.ndarray] = {}
            for i in range(self._model.nsensor):
                name = mujoco.mj_id2name(
                    self._model, mujoco.mjtObj.mjOBJ_SENSOR, i
                )
                adr = self._model.sensor_adr[i]
                dim = self._model.sensor_dim[i]
                result[name or f"sensor_{i}"] = self._data.sensordata[
                    adr : adr + dim
                ].copy()
            return result

    def get_sensor_data(self, sensor_name: str) -> np.ndarray:
        """Return data for a single named sensor."""
        with self._lock:
            self._require_initialized()
            sensor_id = mujoco.mj_name2id(
                self._model, mujoco.mjtObj.mjOBJ_SENSOR, sensor_name
            )
            if sensor_id < 0:
                raise ValueError(f"Sensor '{sensor_name}' not found")
            adr = self._model.sensor_adr[sensor_id]
            dim = self._model.sensor_dim[sensor_id]
            return self._data.sensordata[adr : adr + dim].copy()

    # ------------------------------------------------------------------
    # State snapshot
    # ------------------------------------------------------------------

    def get_state(self) -> dict[str, np.ndarray | float]:
        """Capture the current simulation state as a serialisable dict."""
        with self._lock:
            self._require_initialized()
            return {
                "qpos": self._data.qpos.copy(),
                "qvel": self._data.qvel.copy(),
                "ctrl": self._data.ctrl.copy(),
                "time": float(self._data.time),
            }

    def set_state(self, state: dict[str, np.ndarray | float]) -> None:
        """Restore a previously captured simulation state."""
        with self._lock:
            self._require_initialized()
            if "qpos" in state:
                np.copyto(self._data.qpos, state["qpos"])
            if "qvel" in state:
                np.copyto(self._data.qvel, state["qvel"])
            if "ctrl" in state:
                np.copyto(self._data.ctrl, state["ctrl"])
            if "time" in state:
                self._data.time = float(state["time"])
            mujoco.mj_forward(self._model, self._data)
            logger.debug("Simulation state restored")

    # ------------------------------------------------------------------
    # Model info
    # ------------------------------------------------------------------

    def get_model_info(self) -> dict:
        """Return a summary dict describing the loaded model."""
        self._require_initialized()
        return {
            "nbody": self._model.nbody,
            "njnt": self._model.njnt,
            "ngeom": self._model.ngeom,
            "nsensor": self._model.nsensor,
            "nq": self._model.nq,
            "nv": self._model.nv,
            "nu": self._model.nu,
            "ncam": self._model.ncam,
            "timestep": self._model.opt.timestep,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_initialized(self) -> None:
        if not self.is_initialized:
            raise EngineNotInitializedError(
                "Physics engine not initialized — load a model first"
            )
