"""Locate and invoke the TulpaLang toolchain (``tulpa`` binary + ``std/`` library)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
EXE = "tulpa.exe" if os.name == "nt" else "tulpa"


def _frozen_root() -> Path:
    # PyInstaller one-dir bundles put data next to the executable
    return Path(getattr(sys, "_MEIPASS", ROOT))


def candidates(configured: Optional[str] = None) -> list[Path]:
    out: list[Path] = []
    if configured:
        out.append(Path(configured))
    if os.environ.get("TULPA_BIN"):
        out.append(Path(os.environ["TULPA_BIN"]))
    for base in (_frozen_root(), ROOT):
        out.append(base / "toolchain" / "bin" / EXE)
    found = shutil.which("tulpa")
    if found:
        out.append(Path(found))
    for sib in ("TulpaLang", "tulpalang", "tulpa"):
        out.append(ROOT.parent / sib / "target" / "release" / EXE)
    out.append(Path.home() / ".local" / "bin" / EXE)
    out.append(Path.home() / ".cargo" / "bin" / EXE)
    return out


@dataclass
class Toolchain:
    binary: Path
    version: str
    stdlib: Optional[Path]

    def env(self, extra: Optional[dict] = None) -> dict:
        env = dict(os.environ)
        if self.stdlib is not None:
            prev = env.get("TULPA_PATH")
            env["TULPA_PATH"] = str(self.stdlib) + (os.pathsep + prev if prev else "")
        env.setdefault("PYTHONIOENCODING", "utf-8")
        if extra:
            env.update(extra)
        return env

    def cmd(self, *args: str) -> list[str]:
        return [str(self.binary), *args]

    def run(self, *args: str, cwd: Optional[str] = None, timeout: float = 120,
            extra_env: Optional[dict] = None) -> subprocess.CompletedProcess:
        return subprocess.run(self.cmd(*args), cwd=cwd, capture_output=True, text=True,
                              timeout=timeout, env=self.env(extra_env), encoding="utf-8", errors="replace")


def _stdlib_for(binary: Path) -> Optional[Path]:
    for p in (binary.parent.parent / "lib" / "tulpa",          # installed / bundled layout
              binary.parent / "lib",
              binary.parent.parent.parent / "stdlib",          # cargo target/release
              _frozen_root() / "toolchain" / "lib" / "tulpa"):
        if (p / "rtl.rav").is_file():
            return p.resolve()
    return None


def find(configured: Optional[str] = None) -> Optional[Toolchain]:
    for c in candidates(configured):
        if c.is_file() and os.access(c, os.X_OK):
            try:
                v = subprocess.run([str(c), "-V"], capture_output=True, text=True, timeout=10)
                version = (v.stdout or v.stderr).strip() or "tulpa"
            except Exception:
                continue
            return Toolchain(c.resolve(), version, _stdlib_for(c.resolve()))
    return None


def project_root(script: "str | Path") -> Path:
    """Working directory for running *script*: the nearest folder with a ``hermisim.json``
    (project paths such as ``out/`` and ``weights/`` are relative to it), else the script's folder."""
    p = Path(script).resolve()
    for d in p.parents:
        if (d / "hermisim.json").is_file():
            return d
    return p.parent
