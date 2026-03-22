"""3-D scene rendering using MuJoCo's offscreen renderer displayed in Qt."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from physics_engine.simulation import Simulation

logger = logging.getLogger(__name__)


class ObjectRenderer(QWidget):
    """Widget that displays the latest rendered frame from the simulation."""

    def __init__(
        self, simulation: Simulation, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._simulation = simulation
        self._camera_name: Optional[str] = None

        self._image_label = QLabel(alignment=Qt.AlignCenter)
        self._image_label.setMinimumSize(640, 480)
        self._image_label.setStyleSheet("background-color: #1a1a1a;")
        self._image_label.setText("No model loaded")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._image_label)

        # Connect to simulation signals
        self._simulation.frame_rendered.connect(self._on_frame)
        self._simulation.model_loaded.connect(self._on_model_loaded)

    def set_camera(self, camera_name: Optional[str]) -> None:
        self._camera_name = camera_name

    def render_once(self) -> None:
        """Force a single render outside of the simulation loop."""
        frame = self._simulation.render_frame(self._camera_name)
        if frame is not None:
            self._display_frame(frame)

    def _on_frame(self, frame: np.ndarray) -> None:
        self._display_frame(frame)

    def _on_model_loaded(self, info: dict) -> None:
        self._image_label.setText(
            f"Model loaded: {info.get('nbody', '?')} bodies, "
            f"{info.get('njnt', '?')} joints, {info.get('ngeom', '?')} geoms"
        )
        self.render_once()

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
        """Clear the display."""
        self._image_label.clear()
        self._image_label.setText("No model loaded")