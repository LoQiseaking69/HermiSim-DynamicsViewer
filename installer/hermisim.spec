# PyInstaller spec — HermiSim one-folder bundle (Windows, Linux, macOS).
#
#   pyinstaller installer/hermisim.spec --noconfirm
#
# Expects the Tulpa toolchain staged at build/toolchain/{bin,lib/tulpa,share/doc/tulpa}
# (installer/windows/build.ps1 and installer/stage_toolchain.py do this).
# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
STAGE = ROOT / "build" / "toolchain"
WIN = sys.platform == "win32"

datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "models"), "models"),
    (str(ROOT / "workspace"), "workspace"),
    (str(ROOT / "gui" / "styles.py"), "gui"),
]
if STAGE.is_dir():
    datas.append((str(STAGE), "toolchain"))
else:
    print("WARNING: build/toolchain missing — bundle will rely on a tulpa on PATH", file=sys.stderr)

datas += collect_data_files("mujoco")
datas += collect_data_files("pyqtgraph", includes=["**/*.png", "**/*.svg"])
binaries = collect_dynamic_libs("mujoco")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "gui.ide.window", "gui.ide.editor", "gui.ide.panels", "gui.ide.plots", "gui.ide.vcd_view",
        "gui.ide.machine_view", "gui.ide.run_manager", "gui.ide.theme", "gui.ide.highlighter",
        "gui.ide.userdata", "gui.main_window", "tulpa_bridge.cosim_server", "tulpa_bridge.runner",
        "tulpa_bridge.lsp_client", "pyqtgraph", "numpy",
    ] + collect_submodules("OpenGL.platform") + collect_submodules("OpenGL.arrays")
      + collect_submodules("mujoco.egl") + collect_submodules("mujoco.osmesa") + collect_submodules("mujoco.glfw"),
    excludes=["tkinter", "matplotlib", "pandas", "scipy", "cv2", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

icon = str(ROOT / "assets" / "logo" / "hermisim.ico")
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="HermiSim",
    console=False,
    icon=icon,
    version=(str(ROOT / "build" / "version_info.txt") if (ROOT / "build" / "version_info.txt").is_file()
             else str(ROOT / "installer" / "windows" / "version_info.txt")) if WIN else None,
    disable_windowed_traceback=False,
)
# Console twin for the headless co-sim runner (`hermisim-cli run file.rav --model m.xml`).
cli = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="hermisim-cli",
    console=True,
    icon=icon,
)
coll = COLLECT(exe, cli, a.binaries, a.datas, strip=False, upx=False, name="HermiSim")
