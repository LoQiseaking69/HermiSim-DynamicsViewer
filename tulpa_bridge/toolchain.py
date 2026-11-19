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


def native_targets(tc: Toolchain) -> list[tuple[str, str]]:
    """`tulpa targets` as (name, description) pairs; empty for toolchains older than 3.3."""
    try:
        r = tc.run("targets", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    out = []
    for line in r.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            out.append((parts[0], parts[1]))
    return out


def native_exe_name(source: Path) -> Path:
    """Where Run Natively puts the executable for ``source``."""
    return source.with_name(source.stem + ("-native.exe" if os.name == "nt" else "-native"))


def vm_exe_name(source: Path) -> Path:
    """Where Run on the Firmware VM puts the executable for ``source``."""
    return source.with_name(source.stem + ("-vm.exe" if os.name == "nt" else "-vm"))


def prove(tc: Toolchain, source: "str | Path", strict: bool = False, timeout: float = 120) -> Optional[dict]:
    """`tulpa prove --json FILE` as a dict: {file, proved, refuted, unproved, skipped, obligations}.

    None if the toolchain is older than Tulpa 3.4 or the file does not parse (stderr is in
    ``last_error``).
    """
    global last_error
    args = ["prove", "--json"] + (["--strict"] if strict else []) + [str(source)]
    try:
        r = tc.run(*args, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        last_error = str(e)
        return None
    try:
        import json
        reports = json.loads(r.stdout)
        return reports[0] if reports else None
    except (ValueError, IndexError):
        last_error = (r.stderr or r.stdout).strip()
        return None


last_error = ""


def parse_link_graph(text: str) -> list[dict]:
    """Parses `tulpa link graph` output into [{name, publishes, subscribes, services}]."""
    nodes: list[dict] = []
    keys = {"pub": "publishes", "sub": "subscribes", "srv": "services"}
    for line in text.splitlines():
        if not line.strip() or line.startswith("no nodes found"):
            continue
        if not line.startswith(" "):
            nodes.append({"name": line.strip(), "publishes": [], "subscribes": [], "services": []})
        elif nodes:
            kind, _, topic = line.strip().partition(" ")
            if kind in keys:
                nodes[-1][keys[kind]].append(topic.strip())
    return nodes


def help_mentions(tc: Toolchain, text: str) -> bool:
    """Is ``text`` in `tulpa --help`? (e.g. "tulpa link bridge" and "--dynamic" arrived in Tulpa 3.5)"""
    try:
        r = tc.run("--help", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return text in (r.stdout + r.stderr)


def has_command(tc: Toolchain, name: str) -> bool:
    """Does this toolchain know `tulpa NAME` (prove, bundle, deploy, link: Tulpa 3.4+)?"""
    try:
        r = tc.run("--help", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return f"tulpa {name} " in (r.stdout + r.stderr)
