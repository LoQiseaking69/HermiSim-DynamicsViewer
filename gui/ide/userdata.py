"""Where editable content lives.

In a source checkout everything is edited in place. In an installed build (PyInstaller bundle
under Program Files, which is read-only) the bundled ``workspace/`` and ``models/`` are copied
once to ``~/Documents/HermiSim`` so sample projects can write weights, VCDs and netlists.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _writable(p: Path) -> bool:
    try:
        probe = p / ".hermisim-write-test"
        probe.write_text("x")
        probe.unlink()
        return True
    except OSError:
        return False


def _documents() -> Path:
    if os.name == "nt":
        prof = os.environ.get("USERPROFILE")
        if prof and (Path(prof) / "Documents").is_dir():
            return Path(prof) / "Documents"
    docs = Path.home() / "Documents"
    return docs if docs.is_dir() else Path.home()


def base() -> Path:
    """Directory containing ``workspace/`` and ``models/`` that the user may edit."""
    frozen = getattr(sys, "frozen", False)
    if not frozen and _writable(ROOT):
        return ROOT
    dest = Path(os.environ.get("HERMISIM_HOME", "")) if os.environ.get("HERMISIM_HOME") else _documents() / "HermiSim"
    for sub in ("workspace", "models"):
        src, dst = ROOT / sub, dest / sub
        if src.is_dir() and not dst.exists():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif src.is_dir():
            # add newly shipped sample projects/models without touching the user's edits
            for item in src.iterdir():
                if not (dst / item.name).exists():
                    if item.is_dir():
                        shutil.copytree(item, dst / item.name)
                    else:
                        shutil.copy2(item, dst / item.name)
    return dest


_BASE: Path | None = None


def workspace() -> Path:
    global _BASE
    if _BASE is None:
        _BASE = base()
    return _BASE / "workspace"


def models() -> Path:
    global _BASE
    if _BASE is None:
        _BASE = base()
    return _BASE / "models"
