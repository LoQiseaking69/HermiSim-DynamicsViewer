"""Run a Tulpa program against a MuJoCo model (headless CLI, also used by the IDE).

    python -m tulpa_bridge run workspace/morty/main.rav --model models/morty.xml
    python -m tulpa_bridge run prog.rav --model m.xml --realtime 1 --timeout 120
    python -m tulpa_bridge exec prog.rav            # plain run, no simulator
    (arguments after `--` are passed to the program as ARGS)
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from tulpa_bridge import telemetry, toolchain

logger = logging.getLogger(__name__)


class TulpaProcess:
    """Spawns ``tulpa`` and streams stdout/stderr line by line to callbacks."""

    def __init__(self, tc: toolchain.Toolchain, args: list[str], cwd: str,
                 env: Optional[dict] = None,
                 on_stdout: Optional[Callable[[str], None]] = None,
                 on_stderr: Optional[Callable[[str], None]] = None,
                 on_telemetry: Optional[Callable[[dict], None]] = None) -> None:
        self.tc, self.args, self.cwd = tc, args, cwd
        self.env = tc.env({"TULPA_TELEMETRY": "1", **(env or {})})
        self.on_stdout = on_stdout or (lambda s: print(s, flush=True))
        self.on_stderr = on_stderr or (lambda s: print(s, file=sys.stderr, flush=True))
        self.on_telemetry = on_telemetry
        self.proc: Optional[subprocess.Popen] = None

    def start(self) -> "TulpaProcess":
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.proc = subprocess.Popen(self.tc.cmd(*self.args), cwd=self.cwd, env=self.env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, encoding="utf-8", errors="replace", bufsize=1,
                                     creationflags=flags)
        threading.Thread(target=self._pump, args=(self.proc.stdout, True), daemon=True).start()
        threading.Thread(target=self._pump, args=(self.proc.stderr, False), daemon=True).start()
        return self

    def _pump(self, stream, is_out: bool) -> None:
        for line in iter(stream.readline, ""):
            line = line.rstrip("\n")
            if is_out:
                rec = telemetry.parse(line)
                if rec is not None:
                    if self.on_telemetry:
                        self.on_telemetry(rec)
                    continue
                self.on_stdout(line)
            else:
                self.on_stderr(line)
        stream.close()

    def wait(self, timeout: Optional[float] = None) -> int:
        assert self.proc is not None
        return self.proc.wait(timeout)

    def kill(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.kill()


def run_cosim(script: str, model: str, realtime: float = 0.0, timeout: Optional[float] = None,
              tc: Optional[toolchain.Toolchain] = None, script_args: Optional[list[str]] = None,
              on_telemetry: Optional[Callable[[dict], None]] = None, quiet: bool = False) -> int:
    from physics_engine.engine import PhysicsEngine
    from tulpa_bridge.cosim_server import CoSimServer, CoSimSession

    tc = tc or toolchain.find()
    if tc is None:
        print("error: tulpa toolchain not found (set TULPA_BIN or install tulpa)", file=sys.stderr)
        return 2
    engine = PhysicsEngine()
    engine.load_model_from_path(model)
    session = CoSimSession(engine, realtime=realtime)
    if not quiet:
        session.on_notify = lambda m, p: print(f"[sim:{m}] {p}", file=sys.stderr)
    server = CoSimServer(session).start()
    script_path = Path(script).resolve()
    proc = TulpaProcess(tc, [str(script_path), *(script_args or [])], cwd=str(toolchain.project_root(script_path)),
                        env={"TULPA_COSIM": server.address, "HERMISIM_MODEL": str(Path(model).resolve())},
                        on_telemetry=on_telemetry,
                        on_stdout=(lambda s: None) if quiet else None).start()
    t0 = time.time()
    try:
        code = proc.wait(timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        print(f"error: timed out after {timeout}s", file=sys.stderr)
        code = 124
    finally:
        server.stop()
    if not quiet:
        print(f"[hermisim] exit {code} — {session.steps} physics steps, sim t={engine.simulation_time:.3f}s, "
              f"wall {time.time() - t0:.2f}s", file=sys.stderr)
    return code


def main(argv: Optional[list[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="hermisim", description="HermiSim × TulpaLang runner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a Tulpa program in lock-step with a MuJoCo model")
    r.add_argument("script")
    r.add_argument("--model", required=True)
    r.add_argument("--realtime", type=float, default=0.0, help="0 = as fast as possible, 1 = real time")
    r.add_argument("--timeout", type=float, default=None)
    r.add_argument("--quiet", action="store_true")
    e = sub.add_parser("exec", help="run a Tulpa program without a simulator")
    e.add_argument("script")
    sub.add_parser("doctor", help="show toolchain status")
    a, extra = ap.parse_known_args(argv)
    a.args = [x for x in extra if x != "--"]
    logging.basicConfig(level=logging.WARNING)
    if a.cmd == "doctor":
        tc = toolchain.find()
        print(f"tulpa:   {tc.binary if tc else 'NOT FOUND'}\nversion: {tc.version if tc else '-'}\n"
              f"stdlib:  {tc.stdlib if tc else '-'}")
        try:
            import mujoco
            print(f"mujoco:  {mujoco.__version__}")
        except ImportError:
            print("mujoco:  NOT INSTALLED")
        return 0 if tc else 1
    if a.cmd == "exec":
        tc = toolchain.find()
        if tc is None:
            print("error: tulpa toolchain not found", file=sys.stderr)
            return 2
        p = Path(a.script).resolve()
        return TulpaProcess(tc, [str(p), *a.args], cwd=str(toolchain.project_root(p))).start().wait()
    return run_cosim(a.script, a.model, a.realtime, a.timeout, script_args=a.args, quiet=a.quiet)


if __name__ == "__main__":
    sys.exit(main())
