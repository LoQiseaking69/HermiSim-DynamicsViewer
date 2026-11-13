"""Headless smoke test / screenshot of the IDE: opens Morty, runs the balance demo, grabs PNGs.

    QT_QPA_PLATFORM=offscreen MUJOCO_GL=egl python tools/ide_smoke.py out_dir
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.ide import theme  # noqa: E402
from gui.ide.window import IdeWindow  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "screens")
out.mkdir(parents=True, exist_ok=True)
app = QApplication(sys.argv)
theme.apply(app)
root = Path(__file__).resolve().parents[1]
w = IdeWindow(project=str(root / "workspace" / "morty"))
w.resize(1680, 1000)
w.show()
steps = []


def shot(name):
    def f():
        app.processEvents()
        w.grab().save(str(out / f"{name}.png"))
        print("saved", name, flush=True)
    return f


def run_cfg(idx):
    def f():
        w.config_combo.setCurrentIndex(idx)
        w.run_selected_config()
    return f


def open_vcd():
    w.open_file(str(root / "workspace" / "morty" / "out" / "governor.vcd"))


def machines():
    w.open_file(str(root / "workspace" / "morty" / "main.rav"))
    w.show_machines()


plan = [(1500, shot("01_editor")), (100, run_cfg(1)), (9000, lambda: w.d_plots.raise_()), (300, shot("02_cosim")),
        (200, w.runs.stop), (1500, run_cfg(4)), (9000, open_vcd), (800, shot("03_vcd")),
        (200, machines), (800, shot("04_machines")), (300, lambda: w.open_file(str(root / "workspace" / "morty" / "out" / "morty_bom.csv"))),
        (500, shot("05_bom")), (200, w.show_welcome), (500, shot("00_welcome")), (300, app.quit)]
t = 0
for dt, fn in plan:
    t += dt
    QTimer.singleShot(t, fn)
app.exec()
print("problems:", w.problems.count(), "series:", len(w.plots.series))
os._exit(0)
