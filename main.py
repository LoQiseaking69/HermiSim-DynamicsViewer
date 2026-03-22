"""HermiSim Dynamics Viewer — application entry point.

Applies a MuJoCo Windows DLL workaround, configures logging, and launches
the main window.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import pathlib
import sys
from logging.handlers import RotatingFileHandler


# ---------------------------------------------------------------------------
# MuJoCo Windows plugin-directory workaround
# ---------------------------------------------------------------------------
# On Windows MuJoCo may fail to load unrelated plugin DLLs at import time.
# Temporarily renaming the directory sidesteps the issue.

_mujoco_spec = importlib.util.find_spec("mujoco")
_plugin_dir: pathlib.Path | None = None
_plugin_disabled: pathlib.Path | None = None

if _mujoco_spec and _mujoco_spec.origin:
    _pkg_dir = pathlib.Path(_mujoco_spec.origin).resolve().parent
    _plugin_dir = _pkg_dir / "plugin"
    _plugin_disabled = _pkg_dir / "_plugin_disabled"
    if _plugin_dir.is_dir():
        try:
            _plugin_dir.rename(_plugin_disabled)
        except OSError:
            pass  # Already renamed or permissions issue

import mujoco  # noqa: E402  (must come after the rename)

if _plugin_disabled is not None and _plugin_disabled.is_dir():
    try:
        _plugin_disabled.rename(_plugin_dir)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    """Set up root logger with console + rotating file handlers."""
    log_dir = pathlib.Path(__file__).resolve().parent
    log_path = log_dir / "hermisim.log"

    fmt = logging.Formatter(
        "%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------

def main() -> None:
    _configure_logging()
    logger = logging.getLogger(__name__)

    # PySide6 must be imported after mujoco on Windows
    from PySide6.QtWidgets import QApplication

    from gui.main_window import MainWindow
    from gui.styles import apply_styles

    app = QApplication(sys.argv)
    apply_styles(app)

    window = MainWindow()
    window.show()
    logger.info("HermiSim Dynamics Viewer started")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()