"""Code editor for TulpaLang: gutter, diagnostics, completion, hover, go-to-definition."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRect, QSize, QStringListModel, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QKeySequence, QPainter, QShortcut, QTextCharFormat,
                           QTextCursor, QTextFormat)
from PySide6.QtWidgets import (QCompleter, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QTextEdit, QToolTip, QVBoxLayout, QWidget)

from gui.ide import theme
from gui.ide.highlighter import TulpaHighlighter

PAIRS = {"(": ")", "[": "]", "{": "}", '"': '"'}


class _Invoker(QWidget):
    """Runs callables on the GUI thread (LSP replies arrive on a reader thread)."""
    call = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.call.connect(lambda fn: fn())


_INVOKER: Optional[_Invoker] = None


def gui_call(fn) -> None:
    global _INVOKER
    if _INVOKER is None:
        _INVOKER = _Invoker()
    _INVOKER.call.emit(fn)
SEVERITY_COLOR = {1: theme.RED, 2: theme.AMBER, 3: theme.CYAN, 4: theme.MUTED}


class _Gutter(QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802
        self.editor.paint_gutter(event)


class CodeEditor(QPlainTextEdit):
    """A single open file."""

    modified_changed = Signal(bool)
    cursor_moved = Signal(int, int)
    text_edited = Signal()
    goto_requested = Signal(str, int, int)

    def __init__(self, path: Optional[str] = None, parent=None) -> None:
        super().__init__(parent)
        self.path = path
        self.lsp = None
        self.diagnostics: list[dict] = []
        self.run_marker: Optional[int] = None      # line highlighted from a runtime error
        self.setFont(theme.mono_font(11))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setCursorWidth(2)
        self.setMouseTracking(True)
        self.setStyleSheet(f"QPlainTextEdit {{ background: {theme.BG1}; color: {theme.TEXT}; }}")
        self.highlighter = TulpaHighlighter(self.document()) if self._is_tulpa() else None
        self.gutter = _Gutter(self)
        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._on_cursor)
        self.document().modificationChanged.connect(self.modified_changed)
        self.textChanged.connect(self._on_text_changed)
        self._update_gutter_width()
        self._on_cursor()

        self._change_timer = QTimer(self, singleShot=True, interval=350)
        self._change_timer.timeout.connect(self._push_change)
        self._hover_timer = QTimer(self, singleShot=True, interval=550)
        self._hover_timer.timeout.connect(self._do_hover)
        self._hover_pos = None

        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchStartsWith)
        self.completer.activated.connect(self._insert_completion)
        self.completer.popup().setStyleSheet(
            f"background:{theme.BG2}; border:1px solid {theme.CYAN_DIM}; font-family:{theme.MONO};")
        self._completion_model = QStringListModel(self)
        self.completer.setModel(self._completion_model)

        QShortcut(QKeySequence("Ctrl+/"), self, self.toggle_comment)
        QShortcut(QKeySequence("Ctrl+Space"), self, self.request_completion)
        QShortcut(QKeySequence("F12"), self, self.goto_definition)
        QShortcut(QKeySequence("Ctrl+D"), self, self.duplicate_line)

    # ------------------------------------------------------------------ file
    def _is_tulpa(self) -> bool:
        return self.path is None or Path(self.path).suffix in (".rav", ".tlp")

    def load(self, path: str) -> None:
        self.path = path
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            self.setPlainText(f.read())
        self.document().setModified(False)
        if self.highlighter is None and self._is_tulpa():
            self.highlighter = TulpaHighlighter(self.document())

    def save(self, path: Optional[str] = None) -> None:
        if path:
            self.path = path
        assert self.path
        with open(self.path, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.toPlainText())
        self.document().setModified(False)

    @property
    def title(self) -> str:
        return os.path.basename(self.path) if self.path else "untitled.rav"

    # ------------------------------------------------------------------ gutter
    def gutter_width(self) -> int:
        digits = max(3, len(str(self.blockCount())))
        return 22 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_gutter_width(self, *_):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event) -> None:
        p = QPainter(self.gutter)
        p.fillRect(event.rect(), QColor(theme.BG1))
        block = self.firstVisibleBlock()
        n = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        h = round(self.blockBoundingRect(block).height())
        cur = self.textCursor().blockNumber()
        sev_by_line: dict[int, int] = {}
        for d in self.diagnostics:
            ln = d["range"]["start"]["line"]
            sev_by_line[ln] = min(sev_by_line.get(ln, 9), d.get("severity", 1))
        w = self.gutter.width()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible():
                if n in sev_by_line:
                    p.setBrush(QColor(SEVERITY_COLOR.get(sev_by_line[n], theme.RED)))
                    p.setPen(Qt.NoPen)
                    p.drawEllipse(5, top + h // 2 - 3, 7, 7)
                if self.run_marker == n:
                    p.fillRect(0, top, 3, h, QColor(theme.RED))
                p.setPen(QColor(theme.CYAN if n == cur else "#3c4a5c"))
                p.drawText(0, top, w - 8, h, Qt.AlignRight | Qt.AlignVCenter, str(n + 1))
            block = block.next()
            top += h
            n += 1

    # ------------------------------------------------------------------ highlights
    def _on_cursor(self) -> None:
        sels = []
        line = QTextEdit.ExtraSelection()
        line.format.setBackground(QColor("#0f1620"))
        line.format.setProperty(QTextFormat.FullWidthSelection, True)
        line.cursor = self.textCursor()
        line.cursor.clearSelection()
        sels.append(line)
        if self.run_marker is not None:
            blk = self.document().findBlockByNumber(self.run_marker)
            if blk.isValid():
                s = QTextEdit.ExtraSelection()
                s.format.setBackground(QColor("#2a1018"))
                s.format.setProperty(QTextFormat.FullWidthSelection, True)
                s.cursor = QTextCursor(blk)
                sels.append(s)
        for d in self.diagnostics:
            s = QTextEdit.ExtraSelection()
            s.format.setUnderlineStyle(QTextCharFormat.WaveUnderline)
            s.format.setUnderlineColor(QColor(SEVERITY_COLOR.get(d.get("severity", 1), theme.RED)))
            st, en = d["range"]["start"], d["range"]["end"]
            c = QTextCursor(self.document())
            c.setPosition(self._offset(st["line"], st["character"]))
            end = self._offset(en["line"], en["character"])
            if end <= c.position():
                end = c.position() + 1
            c.setPosition(end, QTextCursor.KeepAnchor)
            s.cursor = c
            sels.append(s)
        sels.extend(self._bracket_match())
        self.setExtraSelections(sels)
        tc = self.textCursor()
        self.cursor_moved.emit(tc.blockNumber() + 1, tc.positionInBlock() + 1)
        self.gutter.update()

    def _bracket_match(self) -> list:
        doc = self.toPlainText()
        pos = self.textCursor().position()
        opens, closes = "([{", ")]}"
        for p in (pos, pos - 1):
            if 0 <= p < len(doc) and doc[p] in opens + closes:
                ch = doc[p]
                if ch in opens:
                    target, step, a, b = closes[opens.index(ch)], 1, ch, closes[opens.index(ch)]
                else:
                    target, step, a, b = opens[closes.index(ch)], -1, ch, opens[closes.index(ch)]
                depth, q = 0, p
                while 0 <= q < len(doc):
                    if doc[q] == a:
                        depth += 1
                    elif doc[q] == b:
                        depth -= 1
                        if depth == 0:
                            out = []
                            for x in (p, q):
                                s = QTextEdit.ExtraSelection()
                                s.format.setBackground(QColor("#123a44"))
                                s.format.setForeground(QColor(theme.CYAN))
                                c = QTextCursor(self.document())
                                c.setPosition(x)
                                c.setPosition(x + 1, QTextCursor.KeepAnchor)
                                s.cursor = c
                                out.append(s)
                            return out
                    q += step
                return []
        return []

    def _offset(self, line: int, col: int) -> int:
        blk = self.document().findBlockByNumber(max(0, line))
        if not blk.isValid():
            return max(0, self.document().characterCount() - 1)
        return blk.position() + min(col, max(0, blk.length() - 1))

    def set_diagnostics(self, diags: list) -> None:
        self.diagnostics = diags
        self._on_cursor()

    def mark_error_line(self, line: Optional[int]) -> None:
        self.run_marker = None if line is None else line - 1
        self._on_cursor()

    def goto(self, line: int, col: int = 1) -> None:
        c = QTextCursor(self.document().findBlockByNumber(max(0, line - 1)))
        c.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, max(0, col - 1))
        self.setTextCursor(c)
        self.centerCursor()
        self.setFocus()

    # ------------------------------------------------------------------ LSP glue
    def attach_lsp(self, lsp) -> None:
        self.lsp = lsp
        if lsp and self.path and self._is_tulpa():
            lsp.open(self.path, self.toPlainText())

    def _on_text_changed(self) -> None:
        self.text_edited.emit()
        self._change_timer.start()
        if self.run_marker is not None:
            self.run_marker = None

    def _push_change(self) -> None:
        if self.lsp and self.path and self._is_tulpa():
            self.lsp.change(self.path, self.toPlainText())

    def request_completion(self) -> None:
        if not (self.lsp and self.path):
            return
        c = self.textCursor()
        self._push_change()
        self.lsp.completion(self.path, c.blockNumber(), c.positionInBlock(), self._completion_ready)

    def _completion_ready(self, result) -> None:
        items = result.get("items", result) if isinstance(result, dict) else (result or [])
        labels = sorted({i.get("label", "") for i in items if i.get("label")}, key=str.lower)
        gui_call(lambda: self._show_completions(labels))

    def _word_prefix(self) -> str:
        c = self.textCursor()
        line = c.block().text()[: c.positionInBlock()]
        m = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", line)
        return m.group(0) if m else ""

    def _show_completions(self, labels: list[str]) -> None:
        if not labels:
            return
        self._completion_model.setStringList(labels)
        self.completer.setCompletionPrefix(self._word_prefix())
        r = self.cursorRect()
        r.setWidth(self.completer.popup().sizeHintForColumn(0) + 40)
        self.completer.complete(r)

    def _insert_completion(self, text: str) -> None:
        c = self.textCursor()
        prefix = self._word_prefix()
        c.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len(prefix))
        c.insertText(text)
        self.setTextCursor(c)

    def goto_definition(self) -> None:
        if not (self.lsp and self.path):
            return
        c = self.textCursor()
        self.lsp.definition(self.path, c.blockNumber(), c.positionInBlock(), self._definition_ready)

    def _definition_ready(self, result) -> None:
        if not result:
            return
        loc = result[0] if isinstance(result, list) else result
        from tulpa_bridge.lsp_client import path_of
        st = loc["range"]["start"]
        gui_call(lambda: self.goto_requested.emit(path_of(loc["uri"]), st["line"] + 1, st["character"] + 1))

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        super().mouseMoveEvent(e)
        self._hover_pos = e.position().toPoint()
        self._hover_timer.start()

    def _do_hover(self) -> None:
        if not (self.lsp and self.path and self._hover_pos):
            return
        pos = self._hover_pos
        # diagnostics first
        c = self.cursorForPosition(pos)
        ln, col = c.blockNumber(), c.positionInBlock()
        for d in self.diagnostics:
            st, en = d["range"]["start"], d["range"]["end"]
            if st["line"] <= ln <= en["line"] and (st["line"] != ln or st["character"] <= col + 1):
                QToolTip.showText(self.mapToGlobal(pos), f"<b style='color:{theme.RED}'>error</b> {d['message']}", self)
                return
        gpos = self.mapToGlobal(pos)

        def done(result):
            if not result:
                return
            cont = result.get("contents", "")
            text = cont.get("value", "") if isinstance(cont, dict) else str(cont)
            if text:
                html = "<pre style='font-family:monospace'>" + text.replace("```tulpa", "").replace("```", "").strip() + "</pre>"
                gui_call(lambda: QToolTip.showText(gpos, html, self))
        self.lsp.hover(self.path, ln, col, done)

    # ------------------------------------------------------------------ editing behaviour
    def keyPressEvent(self, e) -> None:  # noqa: N802
        if self.completer.popup().isVisible() and e.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab, Qt.Key_Escape):
            e.ignore()
            return
        c = self.textCursor()
        k, t = e.key(), e.text()
        if k in (Qt.Key_Return, Qt.Key_Enter):
            line = c.block().text()[: c.positionInBlock()]
            indent = re.match(r"\s*", line).group(0)
            after = c.block().text()[c.positionInBlock():]
            if line.rstrip().endswith("{"):
                if after.strip().startswith("}"):
                    c.insertText("\n" + indent + "    " + "\n" + indent)
                    c.movePosition(QTextCursor.Up)
                    c.movePosition(QTextCursor.EndOfLine)
                    self.setTextCursor(c)
                else:
                    c.insertText("\n" + indent + "    ")
            else:
                c.insertText("\n" + indent)
            return
        if k == Qt.Key_Tab and not c.hasSelection():
            c.insertText("    ")
            return
        if k == Qt.Key_Backtab or (k == Qt.Key_Tab and c.hasSelection()):
            self._indent_selection(-1 if k == Qt.Key_Backtab else 1)
            return
        if t == "}":
            line = c.block().text()[: c.positionInBlock()]
            if line.strip() == "" and len(line) >= 4:
                c.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, 4)
                c.removeSelectedText()
        if t in PAIRS and not c.hasSelection():
            nxt = self.toPlainText()[c.position(): c.position() + 1]
            if t == '"' and nxt == '"':
                c.movePosition(QTextCursor.Right)
                self.setTextCursor(c)
                return
            if nxt in ("", " ", ")", "]", "}", ",", "\n"):
                c.insertText(t + PAIRS[t])
                c.movePosition(QTextCursor.Left)
                self.setTextCursor(c)
                return
        if t in (")", "]", "}") and self.toPlainText()[c.position(): c.position() + 1] == t:
            c.movePosition(QTextCursor.Right)
            self.setTextCursor(c)
            return
        super().keyPressEvent(e)
        if t == "." or t == ":" and c.block().text()[: self.textCursor().positionInBlock()].endswith("::"):
            self.request_completion()
        elif self.completer.popup().isVisible():
            self.completer.setCompletionPrefix(self._word_prefix())

    def _indent_selection(self, d: int) -> None:
        c = self.textCursor()
        start, end = c.selectionStart(), c.selectionEnd()
        c.setPosition(start)
        first = c.blockNumber()
        c.setPosition(end)
        last = c.blockNumber()
        c.beginEditBlock()
        for n in range(first, last + 1):
            b = self.document().findBlockByNumber(n)
            bc = QTextCursor(b)
            if d > 0:
                bc.insertText("    ")
            else:
                txt = b.text()
                k = len(txt) - len(txt.lstrip(" "))
                bc.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, min(4, k))
                bc.removeSelectedText()
        c.endEditBlock()

    def toggle_comment(self) -> None:
        c = self.textCursor()
        start, end = c.selectionStart(), c.selectionEnd()
        c.setPosition(start)
        first = c.blockNumber()
        c.setPosition(end)
        last = c.blockNumber()
        blocks = [self.document().findBlockByNumber(n) for n in range(first, last + 1)]
        uncomment = all(b.text().lstrip().startswith("#") or not b.text().strip() for b in blocks)
        c.beginEditBlock()
        for b in blocks:
            txt = b.text()
            if not txt.strip():
                continue
            k = len(txt) - len(txt.lstrip())
            bc = QTextCursor(b)
            bc.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, k)
            if uncomment:
                n = 2 if txt[k:k + 2] == "# " else 1
                bc.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, n)
                bc.removeSelectedText()
            else:
                bc.insertText("# ")
        c.endEditBlock()

    def duplicate_line(self) -> None:
        c = self.textCursor()
        txt = c.block().text()
        c.movePosition(QTextCursor.EndOfBlock)
        c.insertText("\n" + txt)


class FindBar(QWidget):
    """Find / replace strip shown under the editor tabs (Ctrl+F / Ctrl+H)."""

    def __init__(self, get_editor, parent=None) -> None:
        super().__init__(parent)
        self.get_editor = get_editor
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        self.find = QLineEdit(placeholderText="Find")
        self.repl = QLineEdit(placeholderText="Replace")
        self.status = QLabel("")
        lay.addWidget(QLabel("🔎"))
        lay.addWidget(self.find, 2)
        lay.addWidget(self.repl, 2)
        for label, fn in [("Next", self.next), ("Prev", self.prev), ("Replace", self.replace_one), ("All", self.replace_all), ("✕", self.hide)]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            lay.addWidget(b)
        lay.addWidget(self.status)
        self.find.returnPressed.connect(self.next)
        self.setStyleSheet(f"background:{theme.BG0}; border-bottom:1px solid {theme.LINE};")
        self.hide()

    def open(self, replace: bool = False) -> None:
        ed = self.get_editor()
        if ed and ed.textCursor().hasSelection():
            self.find.setText(ed.textCursor().selectedText())
        self.repl.setVisible(replace)
        self.show()
        self.find.setFocus()
        self.find.selectAll()

    def next(self, backward: bool = False) -> None:
        ed = self.get_editor()
        if not ed or not self.find.text():
            return
        from PySide6.QtGui import QTextDocument
        flags = QTextDocument.FindBackward if backward else QTextDocument.FindFlag(0)
        if not ed.find(self.find.text(), flags):
            c = ed.textCursor()
            c.movePosition(QTextCursor.End if backward else QTextCursor.Start)
            ed.setTextCursor(c)
            ok = ed.find(self.find.text(), flags)
            self.status.setText("" if ok else "no match")
        else:
            self.status.setText("")

    def prev(self) -> None:
        self.next(True)

    def replace_one(self) -> None:
        ed = self.get_editor()
        if ed and ed.textCursor().selectedText() == self.find.text():
            ed.textCursor().insertText(self.repl.text())
        self.next()

    def replace_all(self) -> None:
        ed = self.get_editor()
        if not ed or not self.find.text():
            return
        txt = ed.toPlainText()
        n = txt.count(self.find.text())
        c = ed.textCursor()
        c.select(QTextCursor.Document)
        c.insertText(txt.replace(self.find.text(), self.repl.text()))
        self.status.setText(f"{n} replaced")
