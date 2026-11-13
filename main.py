"""HermiSim — simulation suite and IDE for TulpaLang.

    python main.py                      # IDE (default)
    python main.py workspace/morty      # open a project
    python main.py --classic            # the original tabbed dynamics viewer
    python -m tulpa_bridge run FILE.rav --model MODEL.xml   # headless co-simulation
"""

from __future__ import annotations

import importlib.util
import logging
import os
import pathlib
import sys
from logging.handlers import RotatingFileHandler

# Pick MuJoCo's GL backend before mujoco is imported anywhere.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from physics_engine import gl_backend  # noqa: E402

gl_backend.configure()

# MuJoCo on Windows may fail to load unrelated plugin DLLs at import time; hide them briefly.
_spec = importlib.util.find_spec("mujoco")
if _spec and _spec.origin and os.name == "nt":
    _pkg = pathlib.Path(_spec.origin).resolve().parent
    _plugin, _off = _pkg / "plugin", _pkg / "_plugin_disabled"
    if _plugin.is_dir():
        try:
            _plugin.rename(_off)
        except OSError:
            pass
    import mujoco  # noqa: E402,F401
    if _off.is_dir():
        try:
            _off.rename(_plugin)
        except OSError:
            pass
else:
    import mujoco  # noqa: E402,F401


def _data_dir() -> pathlib.Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME") or str(pathlib.Path.home() / ".local" / "state")
    d = pathlib.Path(base) / "HermiSim"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _configure_logging() -> None:
    fmt = logging.Formatter("%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    try:
        fh = RotatingFileHandler(_data_dir() / "hermisim.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass
    if sys.stdout is not None:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        root.addHandler(ch)


def main() -> None:
    # Headless co-simulation CLI: `HermiSim run prog.rav --model m.xml` / `hermisim-cli exec prog.rav`
    if len(sys.argv) > 1 and sys.argv[1] in ("run", "exec", "doctor"):
        from tulpa_bridge.runner import main as cli_main
        sys.exit(cli_main(sys.argv[1:]))
    _configure_logging()
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    app = QApplication(sys.argv)
    app.setApplicationName("HermiSim")
    app.setOrganizationName("HermiTech")
    icon = pathlib.Path(__file__).resolve().parent / "assets" / "logo" / "hermisim.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    if "--classic" in sys.argv:
        from gui.main_window import MainWindow
        from gui.styles import apply_styles
        apply_styles(app)
        window = MainWindow()
    else:
        from gui.ide import theme
        from gui.ide.window import IdeWindow
        theme.apply(app)
        window = IdeWindow(project=args[0] if args else None)
    window.show()
    logging.getLogger(__name__).info("HermiSim started")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
