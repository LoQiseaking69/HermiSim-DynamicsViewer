"""OpenGL backend selection and self-test for MuJoCo's offscreen renderer.

MuJoCo picks its GL backend from ``MUJOCO_GL`` when ``mujoco`` is first imported:
Windows/macOS → glfw (a hidden window), Linux → glfw, or ``egl``/``osmesa`` headless.
:func:`configure` must therefore run before the first ``import mujoco``.
"""

from __future__ import annotations

import os
import sys
import traceback


def configure() -> str:
    """Choose a sensible MUJOCO_GL if the user didn't set one. Returns the value in effect."""
    if os.environ.get("MUJOCO_GL"):
        return os.environ["MUJOCO_GL"]
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        os.environ["MUJOCO_GL"] = "egl"          # headless Linux (CI, containers, SSH)
    elif sys.platform == "win32" or sys.platform == "darwin" or sys.platform.startswith("linux"):
        os.environ["MUJOCO_GL"] = "glfw"
    return os.environ.get("MUJOCO_GL", "")


def describe_error(exc: BaseException) -> str:
    """One-paragraph, actionable explanation of a renderer failure."""
    msg = f"{type(exc).__name__}: {exc}"
    low = msg.lower()
    hint = ""
    if "glfw" in low and ("shared library" in low or "no module" in low or "not found" in low):
        hint = "The GLFW library is missing from this install — reinstall HermiSim 2.0.1+ (or `pip install glfw`)."
    elif "glfw" in low or "context" in low or "opengl" in low or "mjr_" in low:
        hint = ("No usable OpenGL 3.3 context. Update the GPU driver; over Remote Desktop/VMs enable GPU "
                "acceleration, or set MUJOCO_GL=egl/osmesa on Linux.")
    elif "pyopengl" in low or "OpenGL" in msg:
        hint = "PyOpenGL could not load the platform GL library."
    return f"{msg}\n{hint}".strip()


def probe(width: int = 64, height: int = 48) -> tuple[bool, str]:
    """Render one frame of a tiny scene. Returns (ok, detail)."""
    try:
        import mujoco
        m = mujoco.MjModel.from_xml_string(
            "<mujoco><worldbody><light pos='0 0 3'/><geom type='plane' size='1 1 .1'/>"
            "<geom type='sphere' size='.2' pos='0 0 .3' rgba='0 .9 1 1'/></worldbody></mujoco>")
        d = mujoco.MjData(m)
        mujoco.mj_forward(m, d)
        with mujoco.Renderer(m, height=height, width=width) as r:
            r.update_scene(d)
            img = r.render()
        lit = int((img.reshape(-1, 3).max(axis=1) > 10).sum())
        if lit == 0:
            return False, "renderer produced an all-black frame (broken GL driver?)"
        return True, f"{os.environ.get('MUJOCO_GL') or 'default'} backend, {width}x{height} frame, {lit} lit px"
    except Exception as exc:  # noqa: BLE001
        return False, describe_error(exc) + "\n" + traceback.format_exc(limit=3)
