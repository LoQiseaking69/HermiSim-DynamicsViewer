"""Main application window — tab container, menus, and status bar."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtGui import QAction, QKeySequence
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


class MainWindow(QMainWindow):
    """Top-level window hosting all viewer tabs."""

    def __init__(self, parent: Optional[QMainWindow] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("HermiSim — Dynamics Viewer")
        self.setMinimumSize(1280, 800)

        # Core objects
        self._simulation = Simulation()
        self._file_loader = FileLoader(self._simulation)

        # Tabs
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)
        self._build_tabs()

        # Menu bar & status bar
        self._build_menus()
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

        # Signal connections
        self._simulation.state_changed.connect(self._on_state_changed)
        self._simulation.error_occurred.connect(self._on_error)

        # Auto-load last (or default starter) model
        self._auto_load_model()

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _build_tabs(self) -> None:
        self._render_tab = RenderTab(self._simulation)
        self._simulation_tab = SimulationTab(self._simulation)
        self._sensor_tab = SensorTab(self._simulation)
        self._model_builder_tab = ModelBuilderTab(self._simulation)
        self._log_tab = LogTab()

        self._tabs.addTab(self._render_tab, "Render")
        self._tabs.addTab(self._simulation_tab, "Simulation")
        self._tabs.addTab(self._sensor_tab, "Sensors")
        self._tabs.addTab(self._model_builder_tab, "Model Builder")
        self._tabs.addTab(self._log_tab, "Logs")

    # ------------------------------------------------------------------
    # Menus
    # ------------------------------------------------------------------

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        # -- File menu --
        file_menu = menu_bar.addMenu("&File")

        open_act = QAction("&Open Model…", self)
        open_act.setShortcut(QKeySequence("Ctrl+O"))
        open_act.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_act)

        file_menu.addSeparator()

        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence("Ctrl+Q"))
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        # -- Simulation menu --
        sim_menu = menu_bar.addMenu("&Simulation")

        start_act = QAction("&Start", self)
        start_act.setShortcut(QKeySequence("F5"))
        start_act.triggered.connect(self._simulation.start)
        sim_menu.addAction(start_act)

        pause_act = QAction("&Pause", self)
        pause_act.setShortcut(QKeySequence("F6"))
        pause_act.triggered.connect(self._simulation.pause)
        sim_menu.addAction(pause_act)

        stop_act = QAction("S&top", self)
        stop_act.setShortcut(QKeySequence("F7"))
        stop_act.triggered.connect(self._simulation.stop)
        sim_menu.addAction(stop_act)

        reset_act = QAction("&Reset", self)
        reset_act.setShortcut(QKeySequence("F8"))
        reset_act.triggered.connect(self._simulation.reset)
        sim_menu.addAction(reset_act)

        # -- Help menu --
        help_menu = menu_bar.addMenu("&Help")

        about_act = QAction("&About", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _auto_load_model(self) -> None:
        """Load the last-used model, falling back to the bundled starter."""
        path = FileLoader.last_model_path() or FileLoader.default_model_path()
        if path is None:
            return
        try:
            self._file_loader.load_file(str(path))
            self._status_bar.showMessage(f"Loaded: {path}")
            logger.info("Auto-loaded model: %s", path)
            self._restore_last_state()
        except Exception as exc:
            logger.warning("Auto-load failed for %s: %s", path, exc)

    def _restore_last_state(self) -> None:
        """Restore the simulation state saved during the previous session."""
        state = FileLoader.load_last_state()
        if state is None:
            return
        try:
            self._simulation.engine.set_state(state)
            logger.info("Restored previous simulation state")
        except Exception as exc:
            logger.warning("Could not restore simulation state: %s", exc)

    def _open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Model File",
            "",
            "MJCF / URDF (*.xml *.mjcf *.urdf);;All Files (*)",
        )
        if path:
            try:
                self._file_loader.load_file(path)
                self._status_bar.showMessage(f"Loaded: {path}")
                logger.info("Model loaded via dialog: %s", path)
            except Exception as exc:
                logger.error("Failed to load %s: %s", path, exc)
                QMessageBox.critical(self, "Load Error", str(exc))

    def _on_state_changed(self, state_str: str) -> None:
        self._status_bar.showMessage(f"Simulation: {state_str}")

    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self, "Simulation Error", message)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "HermiSim Dynamics Viewer",
            "Institutional-grade robotics simulation viewer.\n\n"
            "Engine: MuJoCo\nUI: PySide6 (LGPL)",
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        logger.info("Application closing — stopping simulation")
        self._save_current_state()
        self._simulation.stop()
        super().closeEvent(event)

    def _save_current_state(self) -> None:
        """Persist the engine state so it can be restored next launch."""
        if not self._simulation.engine.is_initialized:
            return
        try:
            state = self._simulation.engine.get_state()
            FileLoader.save_last_state(state)
        except Exception as exc:
            logger.warning("Could not save simulation state on exit: %s", exc)