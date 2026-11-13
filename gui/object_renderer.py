"""3-D scene rendering using MuJoCo's offscreen renderer displayed in Qt.

With no model loaded the viewport shows an empty *stage* — the same floor grid, sky and lights
the bundled models use, plus an axis triad at the origin — so the camera can be orbited and
the scene inspected before anything is loaded or simulated. When a model loads, the free camera
frames it automatically (:meth:`ObjectRenderer.frame_model`); double-click or *Frame* re-frames.
"""

from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING, Optional

import mujoco
import numpy as np
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QMouseEvent, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from physics_engine.simulation import Simulation

logger = logging.getLogger(__name__)

# Sensitivity factors
_ORBIT_SENSITIVITY = 0.3  # degrees per pixel
_PAN_SENSITIVITY = 0.0015  # fraction of camera distance per pixel
_ZOOM_SENSITIVITY = 0.08  # distance factor per wheel step

# Empty stage: matches the look of models/morty.xml (dark sky, cyan-edged grid floor).
STAGE_XML = """
<mujoco model="stage">
  <visual>
    <headlight ambient="0.35 0.35 0.4" diffuse="0.6 0.6 0.6"/>
    <quality shadowsize="2048"/>
    <global offwidth="1600" offheight="1000"/>
    <map znear="0.01" zfar="200"/>
  </visual>
  <asset>
    <texture type="skybox" builtin="gradient" rgb1="0.04 0.06 0.10" rgb2="0.0 0.0 0.02" width="512" height="512"/>
    <texture name="grid" type="2d" builtin="checker" rgb1="0.07 0.09 0.12" rgb2="0.05 0.06 0.08"
             mark="edge" markrgb="0.0 0.75 0.85" width="512" height="512"/>
    <material name="floor" texture="grid" texrepeat="10 10" reflectance="0.04"/>
  </asset>
  <worldbody>
    <light directional="true" diffuse="0.7 0.7 0.75" pos="0 0 6" dir="-0.3 -0.2 -1" castshadow="true"/>
    <light diffuse="0.3 0.35 0.5" pos="3 -3 4" dir="-1 1 -1"/>
    <geom name="ground" type="plane" size="20 20 0.1" material="floor" contype="0" conaffinity="0"/>
    <geom name="x_axis" type="capsule" fromto="0 0 0.002 0.5 0 0.002" size="0.008" rgba="0.95 0.25 0.3 1" contype="0" conaffinity="0"/>
    <geom name="y_axis" type="capsule" fromto="0 0 0.002 0 0.5 0.002" size="0.008" rgba="0.3 0.9 0.4 1" contype="0" conaffinity="0"/>
    <geom name="z_axis" type="capsule" fromto="0 0 0.002 0 0 0.5" size="0.008" rgba="0.3 0.55 1 1" contype="0" conaffinity="0"/>
    <geom name="origin" type="sphere" size="0.025" rgba="0.9 0.92 0.95 1" contype="0" conaffinity="0"/>
  </worldbody>
</mujoco>
"""

# Default 3/4 view of a 1.5 m tall robot standing at the origin.
_DEFAULT_VIEW = dict(azimuth=135.0, elevation=-18.0, distance=3.2, lookat=(0.0, 0.0, 0.75))


class ObjectRenderer(QWidget):
    """Viewport for the simulation: free camera with orbit (left-drag), pan (middle-drag or
    Shift+left), zoom (wheel / right-drag), double-click to frame the model.
    """

    def __init__(self, simulation: Simulation, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._simulation = simulation
        self._camera_name: Optional[str] = None

        self._mjv_camera = mujoco.MjvCamera()
        self._mjv_camera.type = mujoco.mjtCamera.mjCAMERA_FREE
        self._apply_view(**_DEFAULT_VIEW)

        self._last_mouse: Optional[QPoint] = None
        self._render_error: Optional[str] = None
        self._fail_count = 0
        self._overlay = "No model loaded  ·  File ▸ Open Model…  or open a project"

        # Empty stage scene (own renderer; rebuilt when the viewport size changes)
        self._stage_model: Optional[mujoco.MjModel] = None
        self._stage_data: Optional[mujoco.MjData] = None
        self._stage_renderer: Optional[mujoco.Renderer] = None

        self._image_label = QLabel(alignment=Qt.AlignCenter)
        self._image_label.setMinimumSize(320, 240)
        self._image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._image_label.setStyleSheet("background-color: #05070c; color: #8a93a6;")
        self._image_label.setMouseTracking(False)
        self._image_label.installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._image_label)

        # Continuous render while a model is loaded (adaptive interval, see render_once)
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(33)
        self._render_timer.timeout.connect(self.render_once)

        # Frames come from our own timer; the per-step signal is not used for drawing.
        self._simulation.model_loaded.connect(self._on_model_loaded)

    # ------------------------------------------------------------------ camera

    def _apply_view(self, azimuth: float, elevation: float, distance: float, lookat) -> None:
        self._mjv_camera.azimuth = azimuth
        self._mjv_camera.elevation = elevation
        self._mjv_camera.distance = distance
        self._mjv_camera.lookat[:] = lookat

    def _reset_camera(self) -> None:
        self._apply_view(**_DEFAULT_VIEW)

    def frame_model(self) -> None:
        """Point the free camera at the loaded model and back off until all of it fits."""
        engine = self._simulation.engine
        bounds = engine.scene_bounds() if engine.is_initialized else None
        if bounds is None:
            self._reset_camera()
        else:
            centre, radius = bounds
            m = engine.model
            fovy = math.radians(float(m.vis.global_.fovy) if m is not None else 45.0)
            w, h = max(1, self._image_label.width()), max(1, self._image_label.height())
            # the tighter of the vertical and horizontal fields of view decides the distance
            half = min(fovy / 2, math.atan(math.tan(fovy / 2) * w / h))
            dist = radius / math.sin(half) * 1.3      # ~15 % margin around the model
            self._apply_view(azimuth=135.0, elevation=-18.0, distance=max(0.3, dist),
                             lookat=(float(centre[0]), float(centre[1]), float(centre[2])))
        self._camera_name = None
        self.render_once()

    def set_camera(self, camera_name: Optional[str]) -> None:
        self._camera_name = camera_name
        if camera_name is None:
            self.frame_model()
        else:
            self.render_once()

    # ------------------------------------------------------------------ rendering

    def _render_size(self) -> tuple[int, int]:
        """Offscreen buffer size: the viewport's size, capped by the model's offscreen buffer."""
        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        w = max(160, int(self._image_label.width() * dpr))
        h = max(120, int(self._image_label.height() * dpr))
        return w, h

    def _render_stage(self) -> Optional[np.ndarray]:
        if self._stage_model is None:
            self._stage_model = mujoco.MjModel.from_xml_string(STAGE_XML)
            self._stage_data = mujoco.MjData(self._stage_model)
            mujoco.mj_forward(self._stage_model, self._stage_data)
        w, h = self._render_size()
        w = min(w, self._stage_model.vis.global_.offwidth)
        h = min(h, self._stage_model.vis.global_.offheight)
        r = self._stage_renderer
        if r is None or r.width != w or r.height != h:
            if r is not None:
                r.close()
            self._stage_renderer = r = mujoco.Renderer(self._stage_model, height=h, width=w)
        r.update_scene(self._stage_data, camera=self._mjv_camera)
        return r.render().copy()

    def render_once(self) -> None:
        """Draw one frame: the model when one is loaded, otherwise the empty stage."""
        if not self.isVisible():
            return
        engine = self._simulation.engine
        t0 = time.perf_counter()
        try:
            if engine.is_initialized:
                engine.set_render_size(*self._render_size())
                if self._camera_name is not None:
                    frame = engine.render(camera_name=self._camera_name)
                else:
                    frame = engine.render(camera=self._mjv_camera)
                overlay = None
            else:
                frame = self._render_stage()
                overlay = self._overlay
            if frame is not None:
                self._display_frame(frame, overlay)
                self._fail_count = 0
                self._render_error = None
        except Exception as exc:  # noqa: BLE001
            self._fail_count += 1
            if self._render_error is None:
                from physics_engine.gl_backend import describe_error
                self._render_error = describe_error(exc)
                logger.error("3-D renderer failed: %s", self._render_error, exc_info=True)
                self._image_label.setPixmap(QPixmap())
                self._image_label.setWordWrap(True)
                self._image_label.setText("3-D view unavailable\n\n" + self._render_error +
                                          "\n\nThe simulation and co-simulation still run; "
                                          "Help ▸ Diagnostics re-tests rendering.")
            if self._fail_count >= 3:
                self._render_timer.stop()   # don't burn the engine lock retrying every 33 ms
            return
        # Adaptive frame rate: rendering holds the engine lock, so on slow (software) GL back
        # off to keep at most ~1/4 of wall time for drawing and the rest for physics.
        cost_ms = (time.perf_counter() - t0) * 1000
        self._render_timer.setInterval(int(min(500, max(33, 4 * cost_ms))))

    @property
    def render_error(self) -> Optional[str]:
        return self._render_error

    def retry(self) -> None:
        """Forget a previous failure and try again (after a driver/config change)."""
        self._render_error, self._fail_count = None, 0
        self.render_once()
        if self._simulation.engine.is_initialized:
            self._render_timer.start()

    def _on_model_loaded(self, info: dict) -> None:
        self._camera_name = None
        self.frame_model()
        self._render_timer.start()

    def _display_frame(self, frame: np.ndarray, overlay: Optional[str] = None) -> None:
        """Convert an RGB NumPy array to a pixmap (optionally with a caption) and show it."""
        if frame is None or frame.size == 0:
            return
        frame = np.ascontiguousarray(frame)
        h, w = frame.shape[:2]
        qimage = QImage(frame.data, w, h, 3 * w, QImage.Format_RGB888).copy()
        if overlay:
            p = QPainter(qimage)
            p.setRenderHint(QPainter.Antialiasing)
            f = QFont()
            f.setPointSizeF(max(9.0, h / 55))
            p.setFont(f)
            p.setPen(QColor(150, 165, 190))
            p.drawText(qimage.rect().adjusted(0, int(h * 0.04), 0, 0), Qt.AlignHCenter | Qt.AlignTop, overlay)
            p.end()
        pixmap = QPixmap.fromImage(qimage)
        pixmap.setDevicePixelRatio(self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0)
        size = self._image_label.size() * pixmap.devicePixelRatio()
        if pixmap.width() != size.width() or pixmap.height() != size.height():
            pixmap = pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._image_label.setPixmap(pixmap)

    def reset_view(self) -> None:
        """Model unloaded: stop continuous rendering and show the empty stage again."""
        self._render_timer.stop()
        self._reset_camera()
        self.render_once()

    # ------------------------------------------------------------------ Qt events

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, self.render_once)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # debounce: the GL buffer is reallocated at the new size, so don't do it per drag pixel
        if not hasattr(self, "_resize_timer"):
            self._resize_timer = QTimer(self, singleShot=True, interval=120)
            self._resize_timer.timeout.connect(self.render_once)
        self._resize_timer.start()

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is not self._image_label:
            return super().eventFilter(obj, event)
        etype = event.type()
        if etype == event.Type.MouseButtonDblClick:
            self.frame_model()
            return True
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
        if self._camera_name is not None:      # interacting switches back to the free camera
            self._camera_name = None
        buttons, modifiers = event.buttons(), event.modifiers()
        if (buttons & Qt.MiddleButton) or (buttons & Qt.LeftButton and modifiers & Qt.ShiftModifier):
            self._pan(dx, dy)
        elif buttons & Qt.RightButton:
            self._mjv_camera.distance = max(0.1, self._mjv_camera.distance * (1.0 + dy * _ZOOM_SENSITIVITY * 0.1))
        elif buttons & Qt.LeftButton:
            self._mjv_camera.azimuth -= dx * _ORBIT_SENSITIVITY
            self._mjv_camera.elevation = max(-89.0, min(89.0, self._mjv_camera.elevation - dy * _ORBIT_SENSITIVITY))
        self.render_once()

    def _handle_wheel(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y() / 120.0
        self._mjv_camera.distance = max(0.1, self._mjv_camera.distance * (1.0 - delta * _ZOOM_SENSITIVITY))
        self.render_once()

    def _pan(self, dx: int, dy: int) -> None:
        """Shift the look-at point in the camera's screen plane."""
        az = math.radians(self._mjv_camera.azimuth)
        el = math.radians(self._mjv_camera.elevation)
        right = np.array([math.sin(az), -math.cos(az), 0.0])
        up = np.array([-math.cos(az) * math.sin(el), -math.sin(az) * math.sin(el), math.cos(el)])
        k = _PAN_SENSITIVITY * self._mjv_camera.distance
        self._mjv_camera.lookat[:] += (-dx * right + dy * up) * k
