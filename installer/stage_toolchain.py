"""Stage a built TulpaLang toolchain into build/toolchain for bundling.

    python installer/stage_toolchain.py ../TulpaLang            # uses target/release
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent / "TulpaLang").resolve()
exe = "tulpa.exe" if os.name == "nt" else "tulpa"
binary = src / "target" / "release" / exe
if not binary.is_file():
    sys.exit(f"tulpa binary not found at {binary} — run `cargo build --release` in {src}")
out = ROOT / "build" / "toolchain"
shutil.rmtree(out, ignore_errors=True)
(out / "bin").mkdir(parents=True)
shutil.copy2(binary, out / "bin" / exe)
shutil.copytree(src / "stdlib", out / "lib" / "tulpa")
doc = out / "share" / "doc" / "tulpa"
doc.mkdir(parents=True)
for f in ("README.md", "LICENSE"):
    if (src / f).is_file():
        shutil.copy2(src / f, doc / f)
for f in (src / "docs").glob("*.md"):
    shutil.copy2(f, doc / f.name)
vsix = sorted((src / "dist").glob("*.vsix")) if (src / "dist").is_dir() else []
if vsix:
    shutil.copy2(vsix[-1], out / "share" / "tulpa-lang.vsix")
print("staged", binary, "->", out)
