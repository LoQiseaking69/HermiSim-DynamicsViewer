"""3-D scene rendering using MuJoCo's offscreen renderer displayed in Qt."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Optional

import mujoco
import numpy as np
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QImage, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from physics_engine.simulation import Simulation

logger = logging.getLogger(__name__)

# Sensitivity factors
_ORBIT_SENSITIVITY = 0.3  # degrees per pixel
_PAN_SENSITIVITY = 0.005  # world-units per pixel
_ZOOM_SENSITIVITY = 0.05  # distance factor per wheel step


class ObjectRenderer(QWidget):
    """Widget that displays the latest rendered frame from the simulation.

    Supports interactive orbit (left-drag), pan (middle-drag / Shift+left),
    and zoom (scroll wheel / right-drag vertical).
    """

    def __init__(
        self, simulation: Simulation, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._simulation = simulation
        self._camera_name: Optional[str] = None

        # Interactive MjvCamera (free-camera mode)
        self._mjv_camera = mujoco.MjvCamera()
        self._reset_camera()

        self._last_mouse: Optional[QPoint] = None

        self._image_label = QLabel(alignment=Qt.AlignCenter)
        self._image_label.setMinimumSize(640, 480)
        self._image_label.setStyleSheet("background-color: #1a1a1a;")
        self._image_label.setText("No model loaded")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._image_label)

        # Accept mouse events on the image
        self._image_label.setMouseTracking(False)
        self._image_label.installEventFilter(self)

        # Continuous render timer (30 fps)
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(33)
        self._render_timer.timeout.connect(self.render_once)

        # Connect to simulation signals
        self._simulation.frame_rendered.connect(self._on_frame)
        self._simulation.model_loaded.connect(self._on_model_loaded)

    # ------------------------------------------------------------------
    # Camera helpers
    # ------------------------------------------------------------------

    def _reset_camera(self) -> None:
        """Set sensible defaults for the free camera."""
        self._mjv_camera.type = mujoco.mjtCamera.mjCAMERA_FREE
        self._mjv_camera.distance = 4.0
        self._mjv_camera.azimuth = 135.0
        self._mjv_camera.elevation = -25.0
        self._mjv_camera.lookat[:] = [0.0, 0.0, 0.8]

    def set_camera(self, camera_name: Optional[str]) -> None:
        self._camera_name = camera_name
        if camera_name is None:
            self._reset_camera()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_once(self) -> None:
        """Force a single render outside of the simulation loop."""
        engine = self._simulation.engine
        if not engine.is_initialized:
            return
        try:
            if self._camera_name is not None:
                frame = engine.render(camera_name=self._camera_name)
            else:
                frame = engine.render(camera=self._mjv_camera)
            if frame is not None:
                self._display_frame(frame)
        except Exception:
            logger.debug("Render failed", exc_info=True)

    def _on_frame(self, frame: np.ndarray) -> None:
        self._display_frame(frame)

    def _on_model_loaded(self, info: dict) -> None:
        self._reset_camera()
        self._image_label.setText(
            f"Model loaded: {info.get('nbody', '?')} bodies, "
            f"{info.get('njnt', '?')} joints, {info.get('ngeom', '?')} geoms"
        )
        self.render_once()
        self._render_timer.start()

    def _display_frame(self, frame: np.ndarray) -> None:
        """Convert an RGB NumPy array to QPixmap and display it."""
        if frame is None or frame.size == 0:
            return
        h, w = frame.shape[:2]
        bytes_per_line = 3 * w
        qimage = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)
        scaled = pixmap.scaled(
            self._image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._image_label.setPixmap(scaled)

    def reset_view(self) -> None:
        """Clear the display and stop the timer."""
        self._render_timer.stop()
        self._image_label.clear()
        self._image_label.setText("No model loaded")

    # ------------------------------------------------------------------
    # Mouse interaction (via eventFilter on image_label)
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is not self._image_label:
            return super().eventFilter(obj, event)

        etype = event.type()
        if etype == event.Type.MouseButtonPress:
            self._last_mouse = event.position().toPoint()
            return True
        if etype == event.Type.MouseButtonRelease:
            self._last_mouse = None
            return True
        if etype == event.Type.MouseMove:
            self._handle_mouse_move(event)
            return True
        if etype == event.Type.Wheel:
            self._handle_wheel(event)
            return True

        return super().eventFilter(obj, event)

    def _handle_mouse_move(self, event: QMouseEvent) -> None:
        if self._last_mouse is None:
            return
        pos = event.position().toPoint()
        dx = pos.x() - self._last_mouse.x()
        dy = pos.y() - self._last_mouse.y()
        self._last_mouse = pos

        buttons = event.buttons()
        modifiers = event.modifiers()

        if (buttons & Qt.MiddleButton) or (
            buttons & Qt.LeftButton and modifiers & Qt.ShiftModifier
        ):
            # Pan
            self._pan(dx, dy)
        elif buttons & Qt.RightButton:
            # Zoom via vertical drag
            self._mjv_camera.distance = max(
                0.1, self._mjv_camera.distance * (1.0 + dy * _ZOOM_SENSITIVITY * 0.3)
            )
        elif buttons & Qt.LeftButton:
            # Orbit
            self._mjv_camera.azimuth -= dx * _ORBIT_SENSITIVITY
            self._mjv_camera.elevation = max(
                -89.0,
                min(89.0, self._mjv_camera.elevation - dy * _ORBIT_SENSITIVITY),
            )

        self.render_once()

    def _handle_wheel(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y() / 120.0
        self._mjv_camera.distance = max(
            0.1, self._mjv_camera.distance * (1.0 - delta * _ZOOM_SENSITIVITY)
        )
        self.render_once()

    def _pan(self, dx: int, dy: int) -> None:
        """Shift the look-at point in the camera's local frame."""
        az = math.radians(self._mjv_camera.azimuth)
        # Right vector (screen-X)
        right = np.array([-math.sin(az), math.cos(az), 0.0])
        # Up vector (screen-Y) — simplified to world-Z for stability
        up = np.array([0.0, 0.0, 1.0])

        shift = (-dx * right + dy * up) * _PAN_SENSITIVITY * self._mjv_camera.distance
        self._mjv_camera.lookat[:] += shift