"""Runs Tulpa programs from the IDE: plain runs, tests, verify, build, and co-simulation."""

from __future__ import annotations

import os

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from tulpa_bridge import toolchain
from tulpa_bridge.cosim_server import CoSimServer, CoSimSession
from tulpa_bridge.runner import TulpaProcess

logger = logging.getLogger(__name__)

KINDS = {
    "run": "Run",
    "cosim": "Run in Simulator",
    "test": "Run Tests",
    "verify": "Verify Contracts",
    "check": "Check Syntax",
    "build": "Build Native (LLVM)",
    "native": "Run Natively (LLVM executable)",
    "firmware": "Build Firmware",
    "vm": "Run on the Firmware VM",
    "bridge": "Link Bridge to Board",
    "prove": "Prove Contracts",
    "bundle": "Bundle Standalone Executable",
    "deploy": "Deploy to Board",
    "bytecode": "Show Bytecode",
}


@dataclass
class RunConfig:
    name: str
    kind: str
    file: str
    args: list = field(default_factory=list)
    realtime: float = 1.0
    model: Optional[str] = None
    cwd: Optional[str] = None
    target: Optional[str] = None      # native target for kind "firmware" (rp2040, esp32c3, ...)


class RunManager(QObject):
    """Owns at most one running Tulpa process (+ co-sim server). Signals are thread-safe."""

    stdout = Signal(str)
    stderr = Signal(str)
    telemetry = Signal(dict)
    notify = Signal(str, dict)
    started = Signal(str)
    finished = Signal(int, float)
    sim_frame = Signal(dict)

    def __init__(self, simulation, parent=None) -> None:
        super().__init__(parent)
        self.simulation = simulation
        self.tc: Optional[toolchain.Toolchain] = None
        self.proc: Optional[TulpaProcess] = None
        self.server: Optional[CoSimServer] = None
        self.session: Optional[CoSimSession] = None
        self._t0 = 0.0
        self.last_config: Optional[RunConfig] = None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.proc is not None and self.proc.proc.poll() is None

    def ensure_toolchain(self, configured: Optional[str] = None) -> Optional[toolchain.Toolchain]:
        if self.tc is None or (configured and Path(configured) != self.tc.binary):
            self.tc = toolchain.find(configured)
        return self.tc

    def start(self, cfg: RunConfig) -> bool:
        if self.running:
            self.stderr.emit("a program is already running — stop it first")
            return False
        tc = self.ensure_toolchain()
        if tc is None:
            self.stderr.emit("tulpa toolchain not found. Set it in Settings ▸ Toolchain, or put `tulpa` on PATH.")
            return False
        path = Path(cfg.file).resolve()
        argv: list[str]
        env: dict = {}
        if cfg.kind == "run":
            argv = [str(path), *cfg.args]
        elif cfg.kind == "test":
            argv = ["test", str(path)]
        elif cfg.kind == "verify":
            argv = ["verify", str(path)]
        elif cfg.kind == "check":
            argv = ["check", str(path)]
        elif cfg.kind == "bytecode":
            argv = ["bytecode", str(path)]
        elif cfg.kind == "build":
            out = path.with_suffix(".o")
            argv = ["build", str(path), "-o", str(out)]
        elif cfg.kind == "native":
            # compile the whole program to a host executable on the simulated bus, then run it
            exe = toolchain.native_exe_name(path)
            argv = ["build", str(path), "--target", "sim", "--exe", "-o", str(exe)]
        elif cfg.kind == "vm":
            # the Tulpa VM for firmware (tulpa_dyn.c), built for the simulated board: exactly
            # what a microcontroller runs when the program is outside the static native subset
            exe = toolchain.vm_exe_name(path)
            argv = ["build", str(path), "--target", "sim", "--exe", "--dynamic", "-o", str(exe)]
        elif cfg.kind == "bridge":
            # `file` is the serial port; runs until stopped
            argv = ["link", "bridge", cfg.file, *cfg.args]
        elif cfg.kind == "firmware":
            target = cfg.target or "rp2040"
            out = path.with_name(f"{path.stem}-{target}.o")
            argv = ["build", str(path), "--target", target, "-o", str(out)]
        elif cfg.kind == "prove":
            argv = ["prove", *cfg.args, str(path)]
        elif cfg.kind == "bundle":
            out = path.with_name(path.stem + ("-app.exe" if os.name == "nt" else "-app"))
            argv = ["bundle", str(path), "-o", str(out), *cfg.args]
        elif cfg.kind == "deploy":
            # `file` is the project's app.rav; tulpa deploy takes the project folder
            argv = ["deploy", str(path.parent), *cfg.args]
        elif cfg.kind == "cosim":
            if cfg.model:
                try:
                    current = getattr(self.simulation, "model_path", None)
                    if current is None or Path(current).resolve() != Path(cfg.model).resolve():
                        self.simulation.load_model(cfg.model)
                        self.simulation.model_path = cfg.model
                except Exception as exc:
                    self.stderr.emit(f"could not load model {cfg.model}: {exc}")
                    return False
            if not self.simulation.engine.is_initialized:
                self.stderr.emit("no simulation model loaded (File ▸ Open Model…)")
                return False
            self.simulation.stop()             # the Tulpa program owns time now
            self.session = CoSimSession(self.simulation.engine, realtime=cfg.realtime,
                                        on_frame=self.sim_frame.emit,
                                        on_notify=lambda m, p: self.notify.emit(m, p))
            self.server = CoSimServer(self.session).start()
            env = {"TULPA_COSIM": self.server.address}
            argv = [str(path), *cfg.args]
        else:
            self.stderr.emit(f"unknown run kind {cfg.kind}")
            return False
        self.last_config = cfg
        self.proc = TulpaProcess(tc, argv, cwd=cfg.cwd or str(toolchain.project_root(path)), env=env,
                                 on_stdout=self.stdout.emit, on_stderr=self.stderr.emit,
                                 on_telemetry=self.telemetry.emit)
        self._t0 = time.time()
        self.proc.start()
        label = KINDS.get(cfg.kind, cfg.kind) + (f" ({cfg.target})" if cfg.kind == "firmware" and cfg.target else "")
        self.started.emit(f"{label}: {path.name} {' '.join(cfg.args)}".strip())
        import threading
        threading.Thread(target=self._wait, daemon=True).start()
        return True

    def _wait(self) -> None:
        proc = self.proc
        code = proc.wait() if proc else -1
        time.sleep(0.05)                       # let stdout pumps drain
        cfg = self.last_config
        if code == 0 and cfg is not None and cfg.kind in ("native", "vm") and proc is not None and proc.program is None:
            name = toolchain.native_exe_name if cfg.kind == "native" else toolchain.vm_exe_name
            exe = name(Path(cfg.file).resolve())
            self.stdout.emit(f"── running {exe.name}")
            self.proc = TulpaProcess(proc.tc, list(cfg.args), cwd=proc.cwd, program=str(exe),
                                     on_stdout=self.stdout.emit, on_stderr=self.stderr.emit,
                                     on_telemetry=self.telemetry.emit)
            self.proc.start()
            code = self.proc.wait()
            time.sleep(0.05)
        if self.server is not None:
            try:
                self.server.stop()
            except Exception:
                pass
            self.server = None
        self.finished.emit(code, time.time() - self._t0)

    def stop(self) -> None:
        if self.proc:
            self.proc.kill()

    def set_pause(self, paused: bool) -> None:
        if self.session:
            (self.session.paused.clear if paused else self.session.paused.set)()

    def set_speed(self, realtime: float) -> None:
        if self.session:
            self.session.realtime = realtime
            self.session._wall0 = None

    def push(self, body: str, force, duration: float = 0.2) -> None:
        if self.session:
            self.session.push(body, force, duration)
