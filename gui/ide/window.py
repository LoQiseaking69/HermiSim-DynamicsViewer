"""HermiSim IDE main window — TulpaLang editor + MuJoCo simulator in one workspace."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QDockWidget, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QInputDialog, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QScrollArea, QSlider, QTabWidget,
                               QToolButton, QVBoxLayout, QWidget)

from gui.ide import theme
from gui.ide.editor import CodeEditor, FindBar
from gui.ide.machine_view import MachinesView
from gui.ide.panels import Console, CsvView, OutlinePanel, ProblemsPanel, ProjectTree, parse_location
from gui.ide.plots import TelemetryPanel
from gui.ide.run_manager import KINDS, RunConfig, RunManager
from gui.ide.vcd_view import VcdViewer
from tulpa_bridge import telemetry as tlm
from tulpa_bridge import toolchain

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
from gui.ide import userdata  # noqa: E402
NEW_FILE = '''# New TulpaLang program
#   Run ▸ Run (F5)  ·  Run ▸ Run in Simulator (Shift+F5) connects cosim::connect() to the model

fn main() {
    let sim = cosim::connect()
    let o = sim.reset()
    print(f"model has {sim.info().nu} actuators")
    for k in 0..200 {
        o = sim.step([0.0; len(o.ctrl)], 5)
        tlm::plot("com_z", o.com[2], o.time)
    }
}

main()
'''


class _Bridge(QWidget):
    """Re-emits LSP callbacks (reader thread) on the GUI thread."""
    diagnostics = Signal(str, list)
    symbols = Signal(str, list)


class WelcomePage(QScrollArea):
    open_project = Signal(str)
    action = Signal(str)

    def __init__(self, projects: list[dict], recent: list[str], tc_text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("welcomeBody")
        body.setStyleSheet(f"QWidget#welcomeBody {{ background:{theme.BG1}; }}")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(60, 40, 60, 40)
        lay.setSpacing(18)
        hero = QHBoxLayout()
        logo = QLabel()
        pm = QPixmap(str(ASSETS / "logo" / "hermisim-mark-256.png"))
        if not pm.isNull():
            logo.setPixmap(pm.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        hero.addWidget(logo)
        txt = QVBoxLayout()
        t = QLabel("HermiSim")
        t.setObjectName("heroTitle")
        s = QLabel("Simulation suite & IDE for TulpaLang — write robot software with units, contracts and "
                   "state machines, then fly it against MuJoCo physics, RTL models and real hardware.")
        s.setObjectName("heroSub")
        s.setWordWrap(True)
        tcl = QLabel(tc_text)
        tcl.setStyleSheet(f"color:{theme.CYAN_DIM}; font-family:monospace;")
        txt.addWidget(t)
        txt.addWidget(s)
        txt.addWidget(tcl)
        hero.addLayout(txt, 1)
        lay.addLayout(hero)
        acts = QHBoxLayout()
        for label, key, primary in [("Open Morty project", "morty", True), ("New Tulpa file", "new", False),
                                    ("Open folder…", "folder", False), ("Open model…", "model", False),
                                    ("Language guide", "guide", False)]:
            b = QPushButton(label)
            if primary:
                b.setObjectName("primary")
            b.clicked.connect(lambda _=False, k=key: self.action.emit(k))
            acts.addWidget(b)
        acts.addStretch()
        lay.addLayout(acts)
        h = QLabel("PROJECTS")
        h.setObjectName("sectionTitle")
        lay.addWidget(h)
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, p in enumerate(projects):
            card = QFrame()
            card.setObjectName("card")
            cl = QVBoxLayout(card)
            name = QLabel(p.get("name", "?"))
            name.setStyleSheet("font-size:16px; font-weight:700;")
            desc = QLabel(p.get("description", ""))
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color:{theme.MUTED};")
            btn = QPushButton("Open")
            btn.clicked.connect(lambda _=False, d=p["dir"]: self.open_project.emit(d))
            cl.addWidget(name)
            cl.addWidget(desc)
            cl.addWidget(btn, alignment=Qt.AlignLeft)
            grid.addWidget(card, i // 2, i % 2)
        lay.addLayout(grid)
        if recent:
            h2 = QLabel("RECENT")
            h2.setObjectName("sectionTitle")
            lay.addWidget(h2)
            for r in recent[:8]:
                b = QPushButton(r)
                b.setStyleSheet("text-align:left; border:none; color:%s;" % theme.CYAN_DIM)
                b.clicked.connect(lambda _=False, f=r: self.action.emit("file:" + f))
                lay.addWidget(b)
        lay.addStretch()
        self.setWidget(body)

    @property
    def title(self) -> str:
        return "Welcome"


class SimPanel(QWidget):
    """3-D viewport + live sim readouts + disturbance buttons."""

    def __init__(self, simulation, runs: RunManager, parent=None) -> None:
        super().__init__(parent)
        from gui.object_renderer import ObjectRenderer
        self.simulation, self.runs = simulation, runs
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.view = ObjectRenderer(simulation)
        self.view.setMinimumSize(360, 300)
        lay.addWidget(self.view, 1)
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 6)
        self.status = QLabel("idle")
        self.status.setStyleSheet(f"color:{theme.MUTED}; font-family:monospace;")
        bar.addWidget(self.status, 1)
        self.cam = QComboBox()
        self.cam.addItem("Free camera", None)
        self.cam.currentIndexChanged.connect(lambda _: self.view.set_camera(self.cam.currentData()))
        bar.addWidget(self.cam)
        lay.addLayout(bar)
        push = QHBoxLayout()
        push.setContentsMargins(8, 0, 8, 8)
        push.addWidget(QLabel("Shove pelvis:"))
        for label, f in [("◀ back", (-120, 0, 0)), ("fwd ▶", (120, 0, 0)), ("▲ left", (0, 130, 0)), ("right ▼", (0, -130, 0))]:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, f=f: self._push(f))
            push.addWidget(b)
        push.addStretch()
        lay.addLayout(push)
        simulation.model_loaded.connect(self._cams)
        runs.sim_frame.connect(self._frame)

    def _cams(self, _info) -> None:
        import mujoco
        self.cam.blockSignals(True)
        self.cam.clear()
        self.cam.addItem("Free camera", None)
        m = self.simulation.engine.model
        for i in range(m.ncam):
            n = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_CAMERA, i)
            if n:
                self.cam.addItem(n, n)
        self.cam.blockSignals(False)

    def _push(self, f) -> None:
        if self.runs.session is None:
            self.status.setText("shoves apply while a program runs in the simulator")
            return
        body = "pelvis" if "pelvis" in self.runs.session._info()["bodies"] else self.runs.session._info()["bodies"][1]
        self.runs.push(body, f, 0.2)
        self.status.setText(f"shove {f} N → {body}")

    def _frame(self, fr: dict) -> None:
        self.status.setText(f"co-sim  t = {fr['time']:8.3f} s   steps {fr['steps']}")


class IdeWindow(QMainWindow):
    def __init__(self, project: Optional[str] = None) -> None:
        super().__init__()
        from physics_engine.simulation import Simulation
        self.settings = QSettings("HermiTech", "HermiSim")
        self.setWindowTitle("HermiSim IDE — TulpaLang")
        icon = ASSETS / "logo" / "hermisim.ico"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.resize(1600, 980)
        self.simulation = Simulation()
        self.runs = RunManager(self.simulation, self)
        self.runs.ensure_toolchain(self.settings.value("toolchain/path", "") or None)
        self.project_dir: Optional[str] = None
        self.project: dict = {}
        self.lsp = None
        self._bridge = _Bridge()
        self._bridge.diagnostics.connect(self._on_diagnostics)
        self._bridge.symbols.connect(self._on_symbols)

        # centre: editor tabs
        centre = QWidget()
        cl = QVBoxLayout(centre)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.findbar = FindBar(self.editor)
        cl.addWidget(self.findbar)
        cl.addWidget(self.tabs)
        self.setCentralWidget(centre)

        # docks
        self.tree = ProjectTree()
        self.tree.file_activated.connect(self.open_file)
        self.outline = OutlinePanel()
        self.outline.symbol_clicked.connect(lambda ln: self.editor() and self.editor().goto(ln))
        self.console = Console()
        self.console.location_clicked.connect(self.goto_location)
        self.problems = ProblemsPanel()
        self.problems.location_clicked.connect(self.goto_location)
        self.plots = TelemetryPanel()
        from gui.tabs.log_tab import LogTab
        from gui.tabs.sensor_tab import SensorTab
        self.logs = LogTab()
        self.simpanel = SimPanel(self.simulation, self.runs)
        self.sensors = SensorTab(self.simulation)

        self.d_explorer = self._dock("Explorer", self.tree, Qt.LeftDockWidgetArea)
        self.d_outline = self._dock("Outline", self.outline, Qt.LeftDockWidgetArea)
        self.splitDockWidget(self.d_explorer, self.d_outline, Qt.Vertical)
        self.d_sim = self._dock("Simulator", self.simpanel, Qt.RightDockWidgetArea)
        self.d_sensors = self._dock("Sensors", self.sensors, Qt.RightDockWidgetArea)
        self.tabifyDockWidget(self.d_sim, self.d_sensors)
        self.d_sim.raise_()
        self.d_console = self._dock("Console", self.console, Qt.BottomDockWidgetArea)
        self.d_problems = self._dock("Problems", self.problems, Qt.BottomDockWidgetArea)
        self.d_plots = self._dock("Telemetry", self.plots, Qt.BottomDockWidgetArea)
        self.d_logs = self._dock("Logs", self.logs, Qt.BottomDockWidgetArea)
        for d in (self.d_problems, self.d_plots, self.d_logs):
            self.tabifyDockWidget(self.d_console, d)
        self.d_console.raise_()
        self.resizeDocks([self.d_explorer, self.d_sim], [260, 520], Qt.Horizontal)
        self.resizeDocks([self.d_console], [260], Qt.Vertical)

        self._build_actions()
        self._build_status()
        self.runs.stdout.connect(lambda s: self.console.append(s))
        self.runs.stderr.connect(self._on_stderr)
        self.runs.telemetry.connect(self._on_telemetry)
        self.runs.notify.connect(self._on_notify)
        self.runs.started.connect(self._on_started)
        self.runs.finished.connect(self._on_finished)
        self.simulation.time_updated.connect(lambda t: self.sb_sim.setText(f"sim {t:.3f}s"))

        self._start_lsp()
        self._load_default_model()
        if project == "morty":
            project = str(userdata.workspace() / "morty")
        if project and Path(project).is_file():
            # launched by double-clicking a .rav/.tlp file: open its project (nearest
            # hermisim.json up the tree, else its folder), then the file itself
            f = Path(project).resolve()
            root = next((d for d in f.parents if (d / "hermisim.json").is_file()), f.parent)
            self.open_project(str(root), show_welcome=False)
            self.open_file(str(f))
        elif project:
            self.open_project(project)
        else:
            last = self.settings.value("project/last", "")
            self.show_welcome()
            if last and Path(last).is_dir():
                self.open_project(last, show_welcome=False)

    # ------------------------------------------------------------------ construction
    def _dock(self, title: str, w: QWidget, area) -> QDockWidget:
        d = QDockWidget(title, self)
        d.setObjectName(title)
        d.setWidget(w)
        d.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        self.addDockWidget(area, d)
        return d

    def _act(self, menu, text, fn, shortcut=None, tip=None) -> QAction:
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip:
            a.setToolTip(tip)
        a.triggered.connect(fn)
        if menu is not None:
            menu.addAction(a)
        return a

    def _build_actions(self) -> None:
        mb = self.menuBar()
        f = mb.addMenu("&File")
        self._act(f, "New Tulpa File", self.new_file, "Ctrl+N")
        self._act(f, "Open File…", self.open_file_dialog, "Ctrl+O")
        self._act(f, "Open Folder / Project…", self.open_folder_dialog, "Ctrl+Shift+O")
        self._act(f, "Open Model (MJCF/URDF)…", self.open_model_dialog, "Ctrl+M")
        f.addSeparator()
        self._act(f, "Save", self.save, "Ctrl+S")
        self._act(f, "Save As…", self.save_as, "Ctrl+Shift+S")
        self._act(f, "Save All", self.save_all, "Ctrl+Alt+S")
        f.addSeparator()
        self._act(f, "Welcome", self.show_welcome)
        self._act(f, "Quit", self.close, "Ctrl+Q")

        e = mb.addMenu("&Edit")
        self._act(e, "Find", lambda: self.findbar.open(False), "Ctrl+F")
        self._act(e, "Replace", lambda: self.findbar.open(True), "Ctrl+H")
        self._act(e, "Toggle Comment", lambda: self.editor() and self.editor().toggle_comment())
        self._act(e, "Go to Line…", self.goto_line_dialog, "Ctrl+G")
        self._act(e, "Go to Definition", lambda: self.editor() and self.editor().goto_definition())

        r = mb.addMenu("&Run")
        self.a_run = self._act(r, "▶  Run", lambda: self.run_kind("run"), "F5")
        self.a_sim = self._act(r, "⧉  Run in Simulator", lambda: self.run_kind("cosim"), "Shift+F5")
        self.a_stop = self._act(r, "■  Stop", self.runs.stop, "Ctrl+F2")
        r.addSeparator()
        self._act(r, "Run Tests", lambda: self.run_kind("test"), "Ctrl+F5")
        self._act(r, "Verify Contracts (fuzz)", lambda: self.run_kind("verify"), "Ctrl+Shift+V")
        self._act(r, "Check Syntax", lambda: self.run_kind("check"))
        self._act(r, "Build Native (LLVM .o + .h)", lambda: self.run_kind("build"), "Ctrl+B")
        self._act(r, "Show Bytecode", lambda: self.run_kind("bytecode"))
        self._act(r, "State Machine Diagrams", self.show_machines, "Ctrl+Shift+G")
        r.addSeparator()
        self.configs_menu = r.addMenu("Run Configurations")
        self._act(r, "Re-run Last", self.rerun, "Ctrl+R")

        s = mb.addMenu("&Simulator")
        self._act(s, "Free-run Physics (no program)", self._free_run, "F6")
        self._act(s, "Pause / Resume", self._toggle_pause, "F7")
        self._act(s, "Reset Model", self._reset_model, "F8")
        self._act(s, "Single Step", lambda: self.simulation.single_step())

        v = mb.addMenu("&View")
        for d in (self.d_explorer, self.d_outline, self.d_sim, self.d_sensors, self.d_console,
                  self.d_problems, self.d_plots, self.d_logs):
            v.addAction(d.toggleViewAction())
        v.addSeparator()
        self._act(v, "Model Builder", self.show_model_builder)

        st = mb.addMenu("&Settings")
        self._act(st, "Tulpa Toolchain…", self.choose_toolchain)
        self._act(st, "Restart Language Server", self._start_lsp)

        h = mb.addMenu("&Help")
        self._act(h, "Tulpa Language Guide", lambda: self._open_doc("language_guide.md"))
        self._act(h, "Tulpa Libraries (nn, rl, rtl, eda, …)", lambda: self._open_doc("libraries.md"))
        self._act(h, "Diagnostics (toolchain, 3-D, co-sim)…", self.doctor)
        self._act(h, "About HermiSim", self.about)

        tb = self.addToolBar("Run")
        tb.setObjectName("runbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        self.config_combo = QComboBox()
        self.config_combo.setMinimumWidth(260)
        self.config_combo.setToolTip("Run configuration")
        tb.addWidget(self.config_combo)
        for act, name in [(self.a_run, "runButton"), (self.a_sim, "simButton"), (self.a_stop, "stopButton")]:
            tb.addAction(act)
            tb.widgetForAction(act).setObjectName(name)
        go = QToolButton(text="▶ Config")
        go.setToolTip("Run the selected configuration")
        go.clicked.connect(self.run_selected_config)
        tb.addWidget(go)
        tb.addSeparator()
        for label, kind in [("Test", "test"), ("Verify", "verify"), ("Build", "build")]:
            b = QToolButton(text=label)
            b.clicked.connect(lambda _=False, k=kind: self.run_kind(k))
            tb.addWidget(b)
        g = QToolButton(text="Diagram")
        g.clicked.connect(self.show_machines)
        tb.addWidget(g)
        tb.addSeparator()
        tb.addWidget(QLabel("  speed "))
        self.speed = QSlider(Qt.Horizontal)
        self.speed.setRange(0, 40)
        self.speed.setValue(10)
        self.speed.setFixedWidth(130)
        self.speed.setToolTip("Co-sim pacing: 0 = as fast as possible, 10 = real time, 40 = 4×")
        self.speed_lbl = QLabel("1.0×")
        self.speed.valueChanged.connect(self._speed_changed)
        tb.addWidget(self.speed)
        tb.addWidget(self.speed_lbl)
        self.pause_btn = QToolButton(text="⏸")
        self.pause_btn.setCheckable(True)
        self.pause_btn.toggled.connect(lambda on: self.runs.set_pause(on))
        tb.addWidget(self.pause_btn)

    def _build_status(self) -> None:
        sb = self.statusBar()
        self.sb_run = QLabel("ready")
        self.sb_tc = QLabel(self.runs.tc.version if self.runs.tc else "tulpa: not found")
        self.sb_sim = QLabel("sim —")
        self.sb_pos = QLabel("")
        self.sb_tlm = QLabel("")
        for w in (self.sb_run, self.sb_tlm):
            sb.addWidget(w)
        for w in (self.sb_sim, self.sb_pos, self.sb_tc):
            sb.addPermanentWidget(w)

    # ------------------------------------------------------------------ language server
    def _start_lsp(self) -> None:
        from tulpa_bridge.lsp_client import LspClient
        if self.lsp:
            self.lsp.stop()
        tc = self.runs.tc
        if tc is None:
            self.lsp = None
            return
        self.lsp = LspClient(tc.cmd("lsp"), tc.env(), on_diagnostics=lambda p, d: self._bridge.diagnostics.emit(p, d))
        try:
            self.lsp.start(self.project_dir or str(ROOT))
        except OSError as exc:
            logger.warning("could not start tulpa lsp: %s", exc)
            self.lsp = None
            return
        for ed in self.editors():
            ed.attach_lsp(self.lsp)

    def _on_diagnostics(self, path: str, diags: list) -> None:
        for ed in self.editors():
            if ed.path and Path(ed.path).resolve() == Path(path).resolve():
                ed.set_diagnostics(diags)
        self.problems.set_diagnostics(path, diags)
        n = self.problems.count()
        self.d_problems.setWindowTitle(f"Problems ({n})" if n else "Problems")

    def _refresh_outline(self) -> None:
        ed = self.editor()
        if ed and self.lsp and ed.path:
            p = ed.path
            self.lsp.symbols(p, lambda r: self._bridge.symbols.emit(p, r or []))
        else:
            self.outline.clear()

    def _on_symbols(self, path: str, syms: list) -> None:
        ed = self.editor()
        if ed and ed.path == path:
            self.outline.set_symbols(syms)

    # ------------------------------------------------------------------ projects & files
    def discover_projects(self) -> list[dict]:
        out = []
        for base in (userdata.workspace(), Path(self.settings.value("project/last", "") or ROOT).parent):
            if not base.is_dir():
                continue
            for p in sorted(base.iterdir()):
                f = p / "hermisim.json"
                if f.is_file():
                    try:
                        d = json.loads(f.read_text())
                        d["dir"] = str(p)
                        if all(x["dir"] != d["dir"] for x in out):
                            out.append(d)
                    except json.JSONDecodeError:
                        pass
        return out

    def show_welcome(self) -> None:
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), WelcomePage):
                self.tabs.setCurrentIndex(i)
                return
        tc = self.runs.tc
        tc_text = f"{tc.version} · {tc.binary}" if tc else "⚠ tulpa toolchain not found — Settings ▸ Tulpa Toolchain"
        w = WelcomePage(self.discover_projects(), self.settings.value("files/recent", []) or [], tc_text)
        w.open_project.connect(self.open_project)
        w.action.connect(self._welcome_action)
        self.tabs.insertTab(0, w, "⌂ Welcome")
        self.tabs.setCurrentIndex(0)

    def _welcome_action(self, key: str) -> None:
        if key == "morty":
            self.open_project(str(userdata.workspace() / "morty"))
        elif key == "new":
            self.new_file()
        elif key == "folder":
            self.open_folder_dialog()
        elif key == "model":
            self.open_model_dialog()
        elif key == "guide":
            self._open_doc("language_guide.md")
        elif key.startswith("file:"):
            self.open_file(key[5:])

    def open_project(self, path: str, show_welcome: bool = True) -> None:
        p = Path(path)
        cfg = p / "hermisim.json"
        self.project_dir = str(p)
        self.project = json.loads(cfg.read_text()) if cfg.is_file() else {"name": p.name}
        self.tree.set_root(str(p), self.project.get("name"))
        self.console.base_dir = str(p)
        self.settings.setValue("project/last", str(p))
        self.setWindowTitle(f"{self.project.get('name', p.name)} — HermiSim IDE")
        model = self.project.get("model")
        if model:
            mp = (p / model).resolve()
            if mp.is_file() and getattr(self.simulation, "model_path", None) != str(mp):
                self._load_model(str(mp))
        self._populate_configs()
        entry = self.project.get("entry")
        if entry and (p / entry).is_file():
            self.open_file(str(p / entry))
        self._start_lsp()

    def _populate_configs(self) -> None:
        self.config_combo.clear()
        self.configs_menu.clear()
        base = Path(self.project_dir or ".")
        for c in self.project.get("run_configurations", []):
            cfg = RunConfig(name=c["name"], kind=c.get("kind", "run"), file=str(base / c["file"]),
                            args=c.get("args", []), realtime=c.get("realtime", 1.0),
                            model=str((base / self.project["model"]).resolve()) if self.project.get("model") else None,
                            cwd=str(base))
            self.config_combo.addItem(cfg.name, cfg)
            self._act(self.configs_menu, cfg.name, lambda _=False, cfg=cfg: self.start(cfg))

    def editors(self) -> list[CodeEditor]:
        return [self.tabs.widget(i) for i in range(self.tabs.count()) if isinstance(self.tabs.widget(i), CodeEditor)]

    def editor(self) -> Optional[CodeEditor]:
        w = self.tabs.currentWidget()
        return w if isinstance(w, CodeEditor) else None

    def open_file(self, path: str, line: Optional[int] = None, col: int = 1):
        path = str(Path(path).resolve())
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if getattr(w, "path", None) and str(Path(w.path).resolve()) == path:
                self.tabs.setCurrentIndex(i)
                if isinstance(w, CodeEditor) and line:
                    w.goto(line, col)
                elif hasattr(w, "reload"):
                    w.reload()
                return w
        suffix = Path(path).suffix.lower()
        if suffix == ".vcd":
            w = VcdViewer(path)
        elif suffix == ".csv":
            w = CsvView(path)
        elif suffix in (".png", ".jpg", ".jpeg"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            return None
        else:
            w = CodeEditor(path)
            try:
                w.load(path)
            except OSError as exc:
                QMessageBox.warning(self, "Open", str(exc))
                return None
            w.modified_changed.connect(lambda _m, w=w: self._retitle(w))
            w.cursor_moved.connect(lambda l, c: self.sb_pos.setText(f"Ln {l}, Col {c}"))
            w.goto_requested.connect(self.goto_location)
            w.attach_lsp(self.lsp)
            if suffix in (".xml", ".mjcf", ".urdf"):
                w.setToolTip("MJCF/URDF model — File ▸ Open Model to load it into the simulator")
        idx = self.tabs.addTab(w, w.title)
        self.tabs.setTabToolTip(idx, path)
        self.tabs.setCurrentIndex(idx)
        if isinstance(w, CodeEditor) and line:
            w.goto(line, col)
        rec = [path] + [r for r in (self.settings.value("files/recent", []) or []) if r != path]
        self.settings.setValue("files/recent", rec[:12])
        return w

    def _retitle(self, w) -> None:
        i = self.tabs.indexOf(w)
        if i >= 0:
            self.tabs.setTabText(i, ("● " if w.document().isModified() else "") + w.title)

    def _tab_changed(self, _i) -> None:
        ed = self.editor()
        self.console.current_file = ed.path if ed else None
        self._refresh_outline()

    def close_tab(self, i: int) -> None:
        w = self.tabs.widget(i)
        if isinstance(w, CodeEditor) and w.document().isModified():
            r = QMessageBox.question(self, "Unsaved changes", f"Save {w.title}?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Cancel:
                return
            if r == QMessageBox.Save and not self._save_editor(w):
                return
        if isinstance(w, CodeEditor) and self.lsp and w.path:
            self.lsp.close(w.path)
        self.tabs.removeTab(i)
        w.deleteLater()

    def new_file(self) -> None:
        w = CodeEditor(None)
        w.setPlainText(NEW_FILE)
        w.modified_changed.connect(lambda _m, w=w: self._retitle(w))
        self.tabs.setCurrentIndex(self.tabs.addTab(w, w.title))

    def open_file_dialog(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Open", self.project_dir or str(ROOT),
                                           "Tulpa (*.rav *.tlp);;Waveforms (*.vcd);;CSV (*.csv);;Models (*.xml *.urdf);;All (*)")
        if p:
            self.open_file(p)

    def open_folder_dialog(self) -> None:
        p = QFileDialog.getExistingDirectory(self, "Open folder", self.project_dir or str(ROOT))
        if p:
            self.open_project(p)

    def _save_editor(self, w: CodeEditor) -> bool:
        if not w.path:
            p, _ = QFileDialog.getSaveFileName(self, "Save", self.project_dir or str(ROOT), "Tulpa (*.rav)")
            if not p:
                return False
            w.path = p
            w.attach_lsp(self.lsp)
        w.save()
        self._retitle(w)
        return True

    def save(self) -> None:
        ed = self.editor()
        if ed:
            self._save_editor(ed)

    def save_as(self) -> None:
        ed = self.editor()
        if ed:
            p, _ = QFileDialog.getSaveFileName(self, "Save As", ed.path or "", "Tulpa (*.rav)")
            if p:
                ed.save(p)
                self._retitle(ed)

    def save_all(self) -> None:
        for ed in self.editors():
            if ed.document().isModified():
                self._save_editor(ed)

    def goto_location(self, path: str, line: int, col: int = 1) -> None:
        w = self.open_file(path, line, col)
        if isinstance(w, CodeEditor):
            w.mark_error_line(line)

    def goto_line_dialog(self) -> None:
        ed = self.editor()
        if ed:
            n, ok = QInputDialog.getInt(self, "Go to line", "Line:", 1, 1, ed.blockCount())
            if ok:
                ed.goto(n)

    # ------------------------------------------------------------------ models
    def _load_default_model(self) -> None:
        last = self.settings.value("model/last", "")
        for p in (last, str(userdata.models() / "morty.xml"), str(userdata.models() / "starter_model.xml")):
            if p and Path(p).is_file():
                self._load_model(p)
                return

    def _load_model(self, path: str) -> None:
        try:
            self.simulation.load_model(path)
            self.settings.setValue("model/last", path)
            self.console.append(f"model loaded: {path}", "sys")
            self.d_sim.setWindowTitle(f"Simulator — {Path(path).stem}")
        except Exception as exc:
            self.console.append(f"model load failed: {exc}", "err")

    def open_model_dialog(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Open model", str(userdata.models()), "MJCF / URDF (*.xml *.mjcf *.urdf)")
        if p:
            self._load_model(p)

    def _free_run(self) -> None:
        if self.runs.running:
            return
        try:
            self.simulation.start()
        except Exception as exc:
            self.console.append(str(exc), "err")

    def _toggle_pause(self) -> None:
        if self.runs.running:
            self.pause_btn.toggle()
        elif self.simulation.is_running:
            self.simulation.pause()
        else:
            self._free_run()

    def _reset_model(self) -> None:
        if not self.runs.running:
            self.simulation.reset()

    def show_model_builder(self) -> None:
        from gui.tabs.model_builder_tab import ModelBuilderTab
        w = ModelBuilderTab(self.simulation)
        self.tabs.setCurrentIndex(self.tabs.addTab(w, "Model Builder"))

    # ------------------------------------------------------------------ running
    def _speed_changed(self, v: int) -> None:
        rt = v / 10.0
        self.speed_lbl.setText("max" if v == 0 else f"{rt:.1f}×")
        self.runs.set_speed(rt)

    def run_kind(self, kind: str) -> None:
        ed = self.editor()
        if ed is None:
            self.console.append("open a .rav file first", "warn")
            return
        if ed.document().isModified() or not ed.path:
            if not self._save_editor(ed):
                return
        args = []
        if kind in ("run", "cosim"):
            # reuse the args of a matching run configuration, if any
            for i in range(self.config_combo.count()):
                c: RunConfig = self.config_combo.itemData(i)
                if Path(c.file).resolve() == Path(ed.path).resolve() and c.kind in ("run", "cosim"):
                    args = c.args
                    break
        model = getattr(self.simulation, "model_path", None)
        cwd = None
        if self.project_dir and Path(ed.path).resolve().is_relative_to(Path(self.project_dir).resolve()):
            cwd = self.project_dir          # project programs run from the project root (out/, weights/)
        self.start(RunConfig(name=kind, kind=kind, file=ed.path, args=args, realtime=self.speed.value() / 10.0,
                             model=model, cwd=cwd))

    def run_selected_config(self) -> None:
        cfg = self.config_combo.currentData()
        if cfg:
            self.save_all()
            self.start(cfg)

    def rerun(self) -> None:
        if self.runs.last_config:
            self.save_all()
            self.start(self.runs.last_config)

    def start(self, cfg: RunConfig) -> None:
        if cfg.kind == "cosim":
            self.speed.blockSignals(True)
            self.speed.setValue(int(cfg.realtime * 10))
            self.speed_lbl.setText("max" if cfg.realtime == 0 else f"{cfg.realtime:.1f}×")
            self.speed.blockSignals(False)
            self.plots.clear()
            self.d_sim.raise_()
        for ed in self.editors():
            ed.mark_error_line(None)
        self.console.current_file = cfg.file
        self.console.base_dir = cfg.cwd or str(Path(cfg.file).parent)
        self.d_console.raise_()
        self.runs.start(cfg)

    def _on_started(self, text: str) -> None:
        self.console.append(f"━━ {text}", "sys")
        self.sb_run.setText("● " + text)
        self.sb_run.setStyleSheet(f"color:{theme.GREEN};")
        self.pause_btn.setChecked(False)

    def _on_finished(self, code: int, secs: float) -> None:
        ok = code == 0
        self.console.append(f"━━ exited with code {code} after {secs:.2f}s", "ok" if ok else "err")
        self.sb_run.setText("ready" if ok else f"exit {code}")
        self.sb_run.setStyleSheet(f"color:{theme.MUTED if ok else theme.RED};")
        self.tree.model.setRootPath(self.tree.root or "")

    def _on_stderr(self, line: str) -> None:
        self.console.append(line, "err")
        loc = parse_location(line, self.console.current_file, self.console.base_dir)
        if loc and Path(loc[0]).is_file():
            for ed in self.editors():
                if ed.path and Path(ed.path).resolve() == Path(loc[0]).resolve():
                    ed.mark_error_line(loc[1])

    def _on_telemetry(self, rec: dict) -> None:
        k = rec.get("k")
        if k == "plot":
            for name, t, v in tlm.scalars(rec):
                self.plots.add(name, t, v, rec.get("unit"))
        elif k == "status":
            self.sb_tlm.setText(rec.get("text", ""))
        elif k == "event":
            self.console.append(f"⚑ {rec.get('name')} {rec.get('data') if rec.get('data') is not None else ''}", "warn")
        elif k == "artifact":
            p = rec.get("path", "")
            self.console.append(f"⇲ artifact: {p}  (double-click in Explorer to open)", "sys")
            if p.endswith(".vcd") and Path(p).is_file():
                QTimer.singleShot(0, lambda: self.open_file(p))

    def _on_notify(self, method: str, params: dict) -> None:
        if method == "log":
            self.console.append("[sim] " + str(params.get("text", "")), "sys")
        elif method == "plot":
            v = params.get("v")
            if isinstance(v, (int, float)):
                self.plots.add(params.get("name", "?"), self.simulation.engine.simulation_time, float(v))

    def show_machines(self) -> None:
        ed = self.editor()
        if not ed or not ed.path or self.runs.tc is None:
            return
        if ed.document().isModified():
            self._save_editor(ed)
        r = self.runs.tc.run("graph", ed.path)
        if r.returncode != 0:
            self.console.append(r.stderr.strip(), "err")
            return
        w = MachinesView(Path(ed.path).name, r.stdout)
        self.tabs.setCurrentIndex(self.tabs.addTab(w, w.title))

    # ------------------------------------------------------------------ settings / help
    def choose_toolchain(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Locate the tulpa binary", str(Path.home()),
                                           "tulpa (tulpa tulpa.exe);;All (*)")
        if p:
            self.settings.setValue("toolchain/path", p)
            self.runs.tc = None
            tc = self.runs.ensure_toolchain(p)
            self.sb_tc.setText(tc.version if tc else "tulpa: not found")
            self._start_lsp()

    def doctor(self) -> None:
        """Help ▸ Diagnostics: toolchain, OpenGL render probe and a loopback co-sim test."""
        import os
        import platform
        from PySide6.QtGui import QGuiApplication
        from physics_engine import gl_backend
        from tulpa_bridge.runner import selftest_cosim
        tc = self.runs.tc
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            try:
                import mujoco
                mj = mujoco.__version__
            except ImportError:
                mj = "not installed"
            render_ok, render = gl_backend.probe()
            cosim_ok, cosim = selftest_cosim(tc) if tc else (False, "tulpa not found")
        finally:
            QApplication.restoreOverrideCursor()
        mark = lambda ok: "OK  " if ok else "FAIL"  # noqa: E731
        report = (
            f"HermiSim diagnostics\n"
            f"platform: {platform.platform()}  python {platform.python_version()}\n"
            f"tulpa:    {tc.binary if tc else 'NOT FOUND'}  ({tc.version if tc else '-'})\n"
            f"stdlib:   {tc.stdlib if tc else '-'}\n"
            f"MuJoCo:   {mj}   MUJOCO_GL={os.environ.get('MUJOCO_GL', '(default)')}\n"
            f"LSP:      {'running' if self.lsp and self.lsp.alive else 'stopped'}\n\n"
            f"[{mark(render_ok)}] 3-D rendering: {render.strip()}\n\n"
            f"[{mark(cosim_ok)}] Co-simulation: {cosim.strip()}\n"
        )
        if render_ok:
            self.simpanel.view.retry()
        box = QMessageBox(self)
        box.setWindowTitle("Diagnostics")
        box.setIcon(QMessageBox.Information if render_ok and cosim_ok else QMessageBox.Warning)
        box.setText("All checks passed." if render_ok and cosim_ok else "Some checks failed. Copy the report when asking for help.")
        box.setDetailedText(report)
        copy = box.addButton("Copy report", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Close)
        box.exec()
        if box.clickedButton() is copy:
            QGuiApplication.clipboard().setText(report)
        self.console.append(report, "sys")

    def _open_doc(self, name: str) -> None:
        tc = self.runs.tc
        cands = []
        if tc:
            cands += [tc.binary.parent.parent / "share" / "doc" / "tulpa" / name,
                      tc.binary.parent.parent.parent / "docs" / name]
        cands.append(ROOT / "toolchain" / "share" / "doc" / "tulpa" / name)
        for c in cands:
            if c.is_file():
                self.open_file(str(c))
                return
        QDesktopServices.openUrl(QUrl("https://github.com/LoQiseaking69/TulpaLang/tree/main/docs"))

    def about(self) -> None:
        QMessageBox.about(self, "About HermiSim",
                          "<h3>HermiSim IDE</h3><p>Simulation suite and development environment for TulpaLang.</p>"
                          f"<p>{self.runs.tc.version if self.runs.tc else 'tulpa not found'} · MuJoCo physics · PySide6</p>"
                          "<p>© HermiTech — BSD 3-Clause</p>")

    def closeEvent(self, e) -> None:  # noqa: N802
        dirty = [ed for ed in self.editors() if ed.document().isModified()]
        if dirty:
            r = QMessageBox.question(self, "Unsaved changes", f"Save {len(dirty)} modified file(s)?",
                                     QMessageBox.SaveAll | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Cancel:
                e.ignore()
                return
            if r == QMessageBox.SaveAll:
                self.save_all()
        self.runs.stop()
        if self.lsp:
            self.lsp.stop()
        self.simulation.stop()
        super().closeEvent(e)
