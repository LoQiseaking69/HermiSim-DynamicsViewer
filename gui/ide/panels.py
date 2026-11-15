"""Dockable panels: console, problems, outline, project explorer, CSV/BOM viewer."""

from __future__ import annotations

import csv
import html
import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDir, QProcess, QSortFilterProxyModel, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QCheckBox, QFileSystemModel, QHBoxLayout, QSpinBox, QHeaderView, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QTreeView, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from gui.ide import theme

# "file.rav:12:5: syntax error" · "line 12:" · "(line 12)" · "file.rav: runtime error: line 3"
LOC_PATTERNS = [
    re.compile(r"(?P<file>[\w./\\:-]+\.(?:rav|tlp)):(?P<line>\d+):(?P<col>\d+)"),
    re.compile(r"(?P<file>[\w./\\:-]+\.(?:rav|tlp)): runtime error: line (?P<line>\d+)"),
    re.compile(r"\bline (?P<line>\d+)"),
]


class Console(QWidget):
    """Program output with clickable source locations."""

    location_clicked = Signal(str, int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 4, 8, 4)
        self.title = QLabel("")
        self.title.setStyleSheet(f"color:{theme.MUTED};")
        bar.addWidget(self.title)
        bar.addStretch()
        self.filter = QLineEdit(placeholderText="filter…")
        self.filter.setMaximumWidth(220)
        bar.addWidget(self.filter)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear)
        bar.addWidget(clear)
        lay.addLayout(bar)
        self.view = QPlainTextEdit(readOnly=True)
        self.view.setFont(theme.mono_font(10))
        self.view.setMaximumBlockCount(20000)
        self.view.mouseDoubleClickEvent = self._dbl
        lay.addWidget(self.view)
        self.base_dir = "."
        self.current_file: Optional[str] = None
        self._lines: list[tuple[str, str]] = []
        self.filter.textChanged.connect(self._refilter)

    def clear(self) -> None:
        self.view.clear()
        self._lines.clear()

    def _fmt(self, kind: str) -> QTextCharFormat:
        f = QTextCharFormat()
        f.setForeground(QColor({"err": theme.RED, "sys": theme.CYAN, "ok": theme.GREEN, "warn": theme.AMBER}.get(kind, theme.TEXT)))
        return f

    def append(self, text: str, kind: str = "out") -> None:
        self._lines.append((text, kind))
        flt = self.filter.text()
        if flt and flt.lower() not in text.lower():
            return
        c = self.view.textCursor()
        c.movePosition(QTextCursor.End)
        c.insertText(text + "\n", self._fmt(kind))
        sb = self.view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _refilter(self) -> None:
        self.view.clear()
        lines, self._lines = self._lines, []
        for t, k in lines:
            self.append(t, k)

    def _dbl(self, e) -> None:
        c = self.view.cursorForPosition(e.position().toPoint())
        line = c.block().text()
        loc = parse_location(line, self.current_file, self.base_dir)
        if loc:
            self.location_clicked.emit(*loc)


def parse_location(text: str, default_file: Optional[str], base: str):
    for rx in LOC_PATTERNS:
        m = rx.search(text)
        if m:
            f = m.groupdict().get("file") or default_file
            if not f:
                return None
            p = Path(f)
            if not p.is_absolute():
                p = Path(base) / p
            return str(p.resolve()), int(m.group("line")), int(m.groupdict().get("col") or 1)
    return None


class ProblemsPanel(QTreeWidget):
    location_clicked = Signal(str, int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderLabels(["", "Message", "File", "Line"])
        self.setRootIsDecorated(False)
        self.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setColumnWidth(0, 28)
        self.itemDoubleClicked.connect(lambda it, _: self.location_clicked.emit(it.data(0, Qt.UserRole), int(it.text(3)), it.data(1, Qt.UserRole)))
        self._by_file: dict[str, list] = {}

    def set_diagnostics(self, path: str, diags: list) -> None:
        self._by_file[path] = diags
        self.clear()
        for f, ds in self._by_file.items():
            for d in ds:
                st = d["range"]["start"]
                sev = d.get("severity", 1)
                it = QTreeWidgetItem(["●", d["message"], Path(f).name, str(st["line"] + 1)])
                it.setForeground(0, QColor({1: theme.RED, 2: theme.AMBER}.get(sev, theme.CYAN)))
                it.setData(0, Qt.UserRole, f)
                it.setData(1, Qt.UserRole, st["character"] + 1)
                self.addTopLevelItem(it)

    def count(self) -> int:
        return sum(len(v) for v in self._by_file.values())


class ProofsPanel(QTreeWidget):
    """Results of `tulpa prove`: one row per obligation, grouped by function."""

    location_clicked = Signal(str, int, int)
    COLORS = {"proved": theme.GREEN, "refuted": theme.RED, "unproved": theme.AMBER, "skipped": theme.CYAN}
    MARKS = {"proved": "✓", "refuted": "✗", "unproved": "?", "skipped": "–"}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderLabels(["Obligation", "Status", "Detail"])
        self.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.setColumnWidth(1, 90)
        self.setColumnWidth(2, 380)
        self.itemDoubleClicked.connect(self._open)
        self.report: Optional[dict] = None

    @staticmethod
    def _line_of(source: str, ctx: str) -> int:
        """Line where the function/method/machine named by an obligation's context starts."""
        name = ctx.removeprefix("machine ").removesuffix("()")
        owner, _, method = name.rpartition(".")
        lines = source.splitlines()
        start = 0
        if owner:
            for i, text in enumerate(lines):
                if re.match(rf"\s*struct\s+{re.escape(owner)}\b", text):
                    start = i
                    break
        pat = re.compile(rf"\s*(fn|def|struct|machine)\s+{re.escape(method)}\b")
        for i in range(start, len(lines)):
            if pat.match(lines[i]):
                return i + 1
        return 1

    def set_report(self, path: str, report: dict) -> None:
        self.report = report
        self.clear()
        try:
            source = Path(path).read_text(encoding="utf-8")
        except OSError:
            source = ""
        groups: dict[str, QTreeWidgetItem] = {}
        order = {"refuted": 0, "unproved": 1, "skipped": 2, "proved": 3}
        for ob in report.get("obligations", []):
            ctx = ob["context"]
            if ctx not in groups:
                g = QTreeWidgetItem([ctx, "", ""])
                g.setData(0, Qt.UserRole, (path, self._line_of(source, ctx)))
                groups[ctx] = g
                self.addTopLevelItem(g)
            status = ob["status"]
            it = QTreeWidgetItem([ob["text"], f"{self.MARKS.get(status, '')} {status}", ob.get("detail", "")])
            it.setForeground(1, QColor(self.COLORS.get(status, theme.CYAN)))
            line = ob.get("line") or groups[ctx].data(0, Qt.UserRole)[1]
            it.setData(0, Qt.UserRole, (path, line))
            groups[ctx].addChild(it)
            worst = groups[ctx].data(1, Qt.UserRole) or "proved"
            if order.get(status, 3) < order.get(worst, 3):
                worst = status
            groups[ctx].setData(1, Qt.UserRole, worst)
        for g in groups.values():
            worst = g.data(1, Qt.UserRole) or "proved"
            g.setText(1, f"{self.MARKS[worst]} {worst}")
            g.setForeground(1, QColor(self.COLORS[worst]))
            g.setExpanded(worst != "proved")

    def summary(self) -> str:
        r = self.report or {}
        return (f"{r.get('proved', 0)} proved, {r.get('refuted', 0)} refuted, "
                f"{r.get('unproved', 0)} unproved, {r.get('skipped', 0)} skipped")

    def _open(self, it, _col) -> None:
        loc = it.data(0, Qt.UserRole)
        if loc:
            self.location_clicked.emit(loc[0], int(loc[1]), 1)


class NetworkPanel(QWidget):
    """Live view of a Tulpa Link network (UDP): nodes with their topics and services."""

    def __init__(self, toolchain_getter, parent=None) -> None:
        super().__init__(parent)
        self._tc = toolchain_getter
        self.domain = QSpinBox()
        self.domain.setRange(0, 200)
        self.domain.setPrefix("domain ")
        self.auto = QCheckBox("auto-refresh")
        self.refresh_btn = QPushButton("Refresh")
        self.status = QLabel("Tulpa Link nodes on this network appear here")
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Node / endpoint", "Kind"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        top = QHBoxLayout()
        for w in (self.domain, self.refresh_btn, self.auto, self.status):
            top.addWidget(w)
        top.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(top)
        lay.addWidget(self.tree)
        self.proc: Optional[QProcess] = None
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh)
        self.refresh_btn.clicked.connect(self.refresh)
        self.auto.toggled.connect(lambda on: self.timer.start() if on else self.timer.stop())

    def refresh(self) -> None:
        if self.proc is not None:
            return
        tc = self._tc()
        if tc is None:
            self.status.setText("no Tulpa toolchain")
            return
        cmd = tc.cmd("link", "graph", "--domain", str(self.domain.value()), "--for", "0.8")
        self.proc = QProcess(self)
        self.proc.finished.connect(self._done)
        self.proc.start(cmd[0], cmd[1:])

    def _done(self, *_a) -> None:
        proc, self.proc = self.proc, None
        if proc is None:
            return
        text = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        err = bytes(proc.readAllStandardError()).decode("utf-8", "replace").strip()
        proc.deleteLater()
        from tulpa_bridge import toolchain
        if err and not text.strip():
            self.status.setText(err.splitlines()[-1][:120])
            return
        self.show_nodes(toolchain.parse_link_graph(text))

    def show_nodes(self, nodes: list) -> None:
        self.tree.clear()
        for n in nodes:
            top = QTreeWidgetItem([n["name"], "node"])
            for key, kind in (("publishes", "publishes"), ("subscribes", "subscribes"), ("services", "service")):
                for t in n[key]:
                    top.addChild(QTreeWidgetItem([t, kind]))
            self.tree.addTopLevelItem(top)
            top.setExpanded(True)
        topics = {t for n in nodes for t in n["publishes"] + n["subscribes"]}
        self.status.setText(f"{len(nodes)} node(s), {len(topics)} topic(s)" if nodes else "no nodes found")


class OutlinePanel(QTreeWidget):
    """Document symbols from the language server."""

    symbol_clicked = Signal(int)
    KINDS = {12: ("ƒ", theme.SYN["function"]), 23: ("S", theme.SYN["type"]), 5: ("M", theme.SYN["state"]),
             14: ("c", theme.SYN["constant"]), 13: ("v", theme.TEXT), 6: ("m", theme.SYN["function"])}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.itemClicked.connect(lambda it, _: self.symbol_clicked.emit(it.data(0, Qt.UserRole)))

    def set_symbols(self, syms: list) -> None:
        self.clear()
        for s in syms or []:
            icon, color = self.KINDS.get(s.get("kind"), ("•", theme.MUTED))
            it = QTreeWidgetItem([f"{icon}  {s.get('name', '?')}"])
            it.setForeground(0, QColor(color))
            it.setToolTip(0, s.get("detail", ""))
            it.setData(0, Qt.UserRole, s["range"]["start"]["line"] + 1)
            self.addTopLevelItem(it)


class _Filter(QSortFilterProxyModel):
    HIDE = {"__pycache__", ".git", "target", "node_modules", ".state"}

    def filterAcceptsRow(self, row, parent) -> bool:  # noqa: N802
        idx = self.sourceModel().index(row, 0, parent)
        return self.sourceModel().fileName(idx) not in self.HIDE


class ProjectTree(QWidget):
    file_activated = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.header = QLabel("")
        self.header.setStyleSheet(f"color:{theme.CYAN}; font-weight:700; padding:6px 10px;")
        lay.addWidget(self.header)
        self.model = QFileSystemModel(self)
        self.model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
        self.proxy = _Filter(self)
        self.proxy.setSourceModel(self.model)
        self.view = QTreeView()
        self.view.setModel(self.proxy)
        for c in (1, 2, 3):
            self.view.hideColumn(c)
        self.view.setHeaderHidden(True)
        self.view.setAnimated(True)
        self.view.doubleClicked.connect(self._open)
        lay.addWidget(self.view)
        self.root: Optional[str] = None

    def set_root(self, path: str, title: Optional[str] = None) -> None:
        self.root = path
        idx = self.model.setRootPath(path)
        self.view.setRootIndex(self.proxy.mapFromSource(idx))
        self.header.setText((title or Path(path).name).upper())

    def _open(self, pidx) -> None:
        idx = self.proxy.mapToSource(pidx)
        if not self.model.isDir(idx):
            self.file_activated.emit(self.model.filePath(idx))


class CsvView(QWidget):
    """Read-only table for CSV artefacts such as the generated BOM."""

    def __init__(self, path: str, parent=None) -> None:
        super().__init__(parent)
        self.path = path
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        lay.addWidget(self.table)
        self.reload()

    @property
    def title(self) -> str:
        return Path(self.path).name

    def reload(self) -> None:
        with open(self.path, newline="", encoding="utf-8", errors="replace") as f:
            rows = list(csv.reader(f))
        if not rows:
            return
        self.table.setColumnCount(len(rows[0]))
        self.table.setHorizontalHeaderLabels(rows[0])
        self.table.setRowCount(len(rows) - 1)
        for r, row in enumerate(rows[1:]):
            for c, v in enumerate(row):
                it = QTableWidgetItem(v)
                if v.replace(".", "", 1).isdigit():
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, it)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
