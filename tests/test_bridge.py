"""Tulpa ↔ HermiSim bridge: telemetry parsing, VCD parsing, and a real co-simulation run."""
from pathlib import Path

import pytest

from tulpa_bridge import telemetry, toolchain

ROOT = Path(__file__).resolve().parents[1]
TC = toolchain.find()
needs_tulpa = pytest.mark.skipif(TC is None, reason="tulpa toolchain not found (set TULPA_BIN)")


def test_telemetry_parse():
    rec = telemetry.parse('@@tlm {"k": "plot", "name": "com_z", "v": 0.91, "t": 1.5}')
    assert rec["name"] == "com_z"
    assert telemetry.parse("plain output") is None
    assert telemetry.scalars(rec) == [("com_z", 1.5, 0.91)]


def test_vcd_parse():
    from gui.ide.vcd_view import parse_vcd
    text = """$timescale 1ns $end
$scope module top $end
$var wire 1 ! clk $end
$var reg 8 " data [7:0] $end
$upscope $end
$enddefinitions $end
#0
0!
b00000000 "
#5
1!
b10100101 "
#10
0!
"""
    sigs, end, scale = parse_vcd(text)
    assert end == 10
    names = {s.name for s in sigs.values()}
    assert any("clk" in n for n in names) and any("data" in n for n in names)


@needs_tulpa
def test_morty_unit_tests():
    r = TC.run("test", "tests/morty_test.rav", cwd=str(ROOT / "workspace" / "morty"), timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 failed" in r.stdout


@needs_tulpa
def test_cosim_balance_run():
    pytest.importorskip("mujoco")
    from tulpa_bridge.runner import main
    rc = main(["run", str(ROOT / "workspace" / "morty" / "main.rav"),
               "--model", str(ROOT / "models" / "morty.xml"), "--quiet", "--", "3"])
    assert rc == 0


@needs_tulpa
def test_fpga_governor_bit_exact():
    r = TC.run("fpga/testbench.rav", cwd=str(ROOT / "workspace" / "morty"), timeout=600)
    assert r.returncode == 0, r.stderr
    assert "8/8 responses bit-exact" in r.stdout


@needs_tulpa
def test_cosim_selftest():
    pytest.importorskip("mujoco")
    from tulpa_bridge.runner import selftest_cosim
    ok, detail = selftest_cosim(TC)
    assert ok, detail


def test_render_error_hints():
    from physics_engine.gl_backend import describe_error
    msg = describe_error(ImportError("Failed to load GLFW3 shared library."))
    assert "GLFW library is missing" in msg


@needs_tulpa
def test_native_targets_listed():
    names = [n for n, _ in toolchain.native_targets(TC)]
    if not names:
        pytest.skip("toolchain older than Tulpa 3.3")
    for t in ("sim", "rp2040", "esp32", "esp32c3"):
        assert t in names


@needs_tulpa
def test_run_natively_and_firmware_kinds(tmp_path, qtbot):
    """The IDE's Run Natively kind builds a sim executable and runs it; Build Firmware cross-compiles."""
    import shutil
    if not toolchain.native_targets(TC) or shutil.which("clang") is None:
        pytest.skip("needs Tulpa 3.3+ and clang")
    from gui.ide.run_manager import RunConfig, RunManager
    src = tmp_path / "blink.rav"
    src.write_text(
        "struct Led { pin: GPIO\n  n: int = 0\n  fn blink(self) { self.pin.toggle(); self.n = self.n + 1 } }\n"
        "let led = Led(GPIO::new(25))\n"
        "every!(10[ms], 3, { led.blink() })\n"
        "print(\"blinks\", led.n, led.pin.read())\n"
    )
    rm = RunManager(simulation=None)
    rm.tc = TC
    out: list[str] = []
    rm.stdout.connect(out.append)
    with qtbot.waitSignal(rm.finished, timeout=120_000) as blocker:
        assert rm.start(RunConfig(name="n", kind="native", file=str(src), cwd=str(tmp_path)))
    assert blocker.args[0] == 0, out
    assert "blinks 3 1" in out
    assert toolchain.native_exe_name(src).is_file()

    with qtbot.waitSignal(rm.finished, timeout=120_000) as blocker:
        assert rm.start(RunConfig(name="f", kind="firmware", file=str(src), cwd=str(tmp_path), target="rp2040"))
    assert blocker.args[0] == 0
    obj = tmp_path / "blink-rp2040.o"
    assert obj.read_bytes()[:4] == b"\x7fELF"
