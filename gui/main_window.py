"""Main application window — assembles all tabs and menus."""

from __future__ import annotations

import logging

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
)

from gui.file_loader import FileLoader
from gui.tabs.log_tab import LogTab
from gui.tabs.model_builder_tab import ModelBuilderTab
from gui.tabs.render_tab import RenderTab
from gui.tabs.sensor_tab import SensorTab
from gui.tabs.simulation_tab import SimulationTab
from physics_engine.simulation import Simulation

logger = logging.getLogger(__name__)

_FILE_FILTER = (
    "Model Files (*.xml *.mjcf *.urdf);;"
    "MJCF Files (*.xml *.mjcf);;"
    "URDF Files (*.urdf);;"
    "All Files (*)"
)


class MainWindow(QMainWindow):
    """Top-level application window for HermiSim."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("HermiSim — Dynamics Viewer")
        self.setMinimumSize(1024, 768)
        self.resize(1400, 900)

        self._simulation = Simulation(parent=self)
        self._file_loader = FileLoader(self._simulation)

        self._tab_widget = QTabWidget()
        self.setCentralWidget(self._tab_widget)

        self._build_tabs()
        self._build_menus()
        self._build_status_bar()

        # Wire simulation signals to status bar
        self._simulation.state_changed.connect(self._on_state_changed)
        self._simulation.error_occurred.connect(self._on_error)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_tabs(self) -> None:
        self._render_tab = RenderTab(self._simulation)
        self._simulation_tab = SimulationTab(self._simulation)
        self._sensor_tab = SensorTab(self._simulation)
        self._model_builder_tab = ModelBuilderTab(self._simulation)
        self._log_tab = LogTab()

        self._tab_widget.addTab(self._render_tab, "Render")
        self._tab_widget.addTab(self._simulation_tab, "Simulation")
        self._tab_widget.addTab(self._sensor_tab, "Sensors")
        self._tab_widget.addTab(self._model_builder_tab, "Model Builder")
        self._tab_widget.addTab(self._log_tab, "Logs")

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        # -- File menu --
        file_menu = menu_bar.addMenu("&File")

        load_action = QAction("&Load Model\u2026", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self._on_load_file)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # -- Simulation menu --
        sim_menu = menu_bar.addMenu("&Simulation")

        start_action = QAction("&Start", self)
        start_action.setShortcut("F5")
        start_action.triggered.connect(self._simulation.start)
        sim_menu.addAction(start_action)

        pause_action = QAction("&Pause", self)
        pause_action.setShortcut("F6")
        pause_action.triggered.connect(self._simulation.pause)
        sim_menu.addAction(pause_action)

        stop_action = QAction("S&top", self)
        stop_action.setShortcut("F7")
        stop_action.triggered.connect(self._simulation.stop)
        sim_menu.addAction(stop_action)

        reset_action = QAction("&Reset", self)
        reset_action.setShortcut("F8")
        reset_action.triggered.connect(self._simulation.reset)
        sim_menu.addAction(reset_action)

        # -- Help menu --
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _build_status_bar(self) -> None:
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_load_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Model File", "", _FILE_FILTER
        )
        if not file_path:
            return
        try:
            self._file_loader.load_file(file_path)
            logger.info("Loaded model: %s", file_path)
            self._status_bar.showMessage(f"Loaded: {file_path}", 5000)
        except Exception as exc:
            logger.error("Load failed: %s", exc)
            QMessageBox.critical(self, "Load Error", str(exc))

    def _on_state_changed(self, state: str) -> None:
        self._status_bar.showMessage(f"Simulation: {state.capitalize()}")

    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self, "Simulation Error", message)
        self._status_bar.showMessage(f"Error: {message}", 10000)

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "About HermiSim",
            "HermiSim \u2014 Dynamics Viewer\n\n"
            "MuJoCo-powered robotics simulation suite.\n"
            "\u00a9 2024 HermiTech Holdings\n"
            "BSD 3-Clause License",
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._simulation.stop()
        self._simulation.engine.close()
        super().closeEvent(event)