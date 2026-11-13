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
