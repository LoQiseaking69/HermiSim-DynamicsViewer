"""Render tab — displays the MuJoCo simulation visualization."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import mujoco
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.object_renderer import ObjectRenderer

if TYPE_CHECKING:
    from physics_engine.simulation import Simulation


class RenderTab(QWidget):
    """Tab containing the 3-D scene renderer and camera controls."""

    def __init__(
        self, simulation: Simulation, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._simulation = simulation
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Camera toolbar
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Camera:"))
        self._camera_combo = QComboBox()
        self._camera_combo.addItem("Free Camera", None)
        self._camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        toolbar.addWidget(self._camera_combo)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._refresh)
        toolbar.addWidget(self._refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Renderer
        self._renderer = ObjectRenderer(self._simulation)
        layout.addWidget(self._renderer)

        # Populate cameras when model loads
        self._simulation.model_loaded.connect(self._populate_cameras)

    def _populate_cameras(self, info: dict) -> None:
        self._camera_combo.clear()
        self._camera_combo.addItem("Free Camera", None)
        if self._simulation.engine.is_initialized:
            model = self._simulation.engine.model
            for i in range(model.ncam):
                name = mujoco.mj_id2name(
                    model, mujoco.mjtObj.mjOBJ_CAMERA, i
                )
                if name:
                    self._camera_combo.addItem(name, name)

    def _on_camera_changed(self, index: int) -> None:
        cam_name = self._camera_combo.currentData()
        self._renderer.set_camera(cam_name)
        self._renderer.render_once()

    def _refresh(self) -> None:
        self._renderer.render_once()

    def update_render(self) -> None:
        self._renderer.render_once()