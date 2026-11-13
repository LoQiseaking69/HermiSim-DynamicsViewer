"""Dockable panels: console, problems, outline, project explorer, CSV/BOM viewer."""

from __future__ import annotations

import csv
import html
import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDir, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QFileSystemModel, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
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
