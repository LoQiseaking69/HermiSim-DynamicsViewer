"""HermiSim — Dynamics Viewer entry point."""

from __future__ import annotations

import logging
import os
import sys

# Prevent MuJoCo from auto-loading bundled plugins that may fail on some
# Windows configurations (DLL init errors with MS-Store Python).  We redirect
# the plugin directory to a temp folder *before* the package is first imported
# so that ``_load_all_bundled_plugins`` finds nothing to load.
_mujoco_pkg_dir = None
try:
    import importlib.util as _ilu
    _spec = _ilu.find_spec("mujoco")
    if _spec and _spec.submodule_search_locations:
        _mujoco_pkg_dir = _spec.submodule_search_locations[0]
except Exception:
    pass

if _mujoco_pkg_dir:
    _real_plugin_dir = os.path.join(_mujoco_pkg_dir, "plugin")
    _temp_plugin_dir = os.path.join(_mujoco_pkg_dir, "_plugin_disabled")
    if os.path.isdir(_real_plugin_dir) and not os.path.isdir(_temp_plugin_dir):
        try:
            os.rename(_real_plugin_dir, _temp_plugin_dir)
        except OSError:
            pass

import mujoco  # noqa: E402  — safe now (no plugins to load)

# Restore the plugin directory after import so files stay intact
if _mujoco_pkg_dir:
    if os.path.isdir(_temp_plugin_dir) and not os.path.isdir(_real_plugin_dir):
        try:
            os.rename(_temp_plugin_dir, _real_plugin_dir)
        except OSError:
            pass

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.main_window import MainWindow  # noqa: E402
from gui.styles import apply_styles  # noqa: E402


def _configure_logging() -> None:
    """Set up structured logging for the entire application."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.INFO)
    console.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(console)


def main() -> None:
    _configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting HermiSim — Dynamics Viewer")

    app = QApplication(sys.argv)
    app.setApplicationName("HermiSim")
    app.setOrganizationName("HermiTech Holdings")
    apply_styles(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()