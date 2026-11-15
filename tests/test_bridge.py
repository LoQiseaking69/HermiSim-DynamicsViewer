"""Tulpa ↔ HermiSim bridge: telemetry parsing, VCD parsing, and a real co-simulation run."""
import os
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


PROOF_SRC = """fn limit(x: float, lo: float, hi: float) -> float
    require lo <= hi
    ensure lo <= result' and result' <= hi
{ clamp(x, lo, hi) }

fn wrong(x: int) -> int ensure result' > x { x }

struct Joint {
    angle: [deg] = 0[deg]
    limit: [deg] = 90[deg]
    invariant self.angle <= self.limit
    fn move_to(self, a: [deg]) { self.angle = min(a, self.limit) }
}
"""


@needs_tulpa
def test_prove_report_and_panel(tmp_path, qtbot):
    if not toolchain.has_command(TC, "prove"):
        pytest.skip("toolchain older than Tulpa 3.4")
    src = tmp_path / "p.rav"
    src.write_text(PROOF_SRC)
    report = toolchain.prove(TC, src)
    assert report is not None, toolchain.last_error
    by = {(o["context"], o["kind"]): o for o in report["obligations"]}
    assert by[("limit()", "ensure")]["status"] == "proved"
    assert by[("wrong()", "ensure")]["status"] == "refuted"
    assert "counterexample" in by[("wrong()", "ensure")]["detail"]
    assert by[("Joint.move_to()", "invariant")]["status"] == "proved"

    from gui.ide.panels import ProofsPanel
    panel = ProofsPanel()
    qtbot.addWidget(panel)
    panel.set_report(str(src), report)
    groups = {panel.topLevelItem(i).text(0): panel.topLevelItem(i) for i in range(panel.topLevelItemCount())}
    assert "refuted" in groups["wrong()"].text(1) and "proved" in groups["limit()"].text(1)
    assert groups["wrong()"].data(0, 0x0100)[1] == 6            # Qt.UserRole: jumps to `fn wrong`
    assert groups["Joint.move_to()"].data(0, 0x0100)[1] == 12
    assert "1 refuted" in panel.summary()


def test_parse_link_graph():
    text = "rover\n  pub  /rover/speed\n  srv  /rover/stop\nbase\n  sub  /rover/speed\n"
    nodes = toolchain.parse_link_graph(text)
    assert [n["name"] for n in nodes] == ["rover", "base"]
    assert nodes[0]["publishes"] == ["/rover/speed"] and nodes[0]["services"] == ["/rover/stop"]
    assert nodes[1]["subscribes"] == ["/rover/speed"]
    assert toolchain.parse_link_graph("no nodes found on domain 0\n") == []


@needs_tulpa
def test_bundle_and_deploy_kinds(tmp_path, qtbot):
    if not toolchain.has_command(TC, "bundle"):
        pytest.skip("toolchain older than Tulpa 3.4")
    import subprocess
    from gui.ide.run_manager import RunConfig, RunManager
    src = tmp_path / "dyn.rav"
    src.write_text('let d = {robot: "morty"}\nprint(d, [1, 2].map(|x| x * 2))\n')
    rm = RunManager(simulation=None)
    rm.tc = TC
    out: list[str] = []
    rm.stdout.connect(out.append)
    rm.stderr.connect(out.append)
    with qtbot.waitSignal(rm.finished, timeout=60_000) as blocker:
        assert rm.start(RunConfig(name="b", kind="bundle", file=str(src), cwd=str(tmp_path)))
    assert blocker.args[0] == 0, out
    exe = tmp_path / ("dyn-app.exe" if os.name == "nt" else "dyn-app")
    r = subprocess.run([str(exe)], capture_output=True, text=True, cwd="/")
    assert r.stdout == '{"robot": "morty"} [2, 4]\n'

    proj = tmp_path / "rover"
    assert TC.run("new", str(proj), "--board", "rp2040").returncode == 0
    out.clear()
    with qtbot.waitSignal(rm.finished, timeout=120_000) as blocker:
        assert rm.start(RunConfig(name="d", kind="deploy", file=str(proj / "app.rav"), args=["--dry-run"], cwd=str(proj)))
    text = "\n".join(out)
    assert blocker.args[0] == 0, text
    assert "[1/4] prove" in text and "rover.uf2" in text


@needs_tulpa
def test_network_panel_shows_udp_nodes(tmp_path, qtbot):
    if not toolchain.has_command(TC, "link"):
        pytest.skip("toolchain older than Tulpa 3.4")
    import subprocess
    domain = 150 + os.getpid() % 40
    talker = tmp_path / "talker.rav"
    talker.write_text(
        'import "std/link"\n'
        f'let n = link.node("talker", domain: {domain}, transport: "udp")\n'
        'let t = n.advertise("/chat", "str")\n'
        'for i in 0..200 { t.publish("hi"); link.spin_for(20[ms]) }\n')
    proc = subprocess.Popen(TC.cmd(str(talker)), env=TC.env())
    try:
        from gui.ide.panels import NetworkPanel
        panel = NetworkPanel(lambda: TC)
        qtbot.addWidget(panel)
        panel.domain.setValue(domain)
        panel.refresh()
        qtbot.waitUntil(lambda: panel.proc is None, timeout=20_000)
        if "Operation not permitted" in panel.status.text():
            pytest.skip("UDP unavailable")
        names = [panel.tree.topLevelItem(i).text(0) for i in range(panel.tree.topLevelItemCount())]
        assert names == ["talker"], panel.status.text()
        assert panel.tree.topLevelItem(0).child(0).text(0) == "/chat"
    finally:
        proc.kill()
        proc.wait()
