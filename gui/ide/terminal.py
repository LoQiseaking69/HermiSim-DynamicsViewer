"""Tulpa terminal: an interactive `tulpa` REPL docked next to the console.

* Plain input goes to a live REPL process (state persists between lines; multi-line blocks
  continue with a `...` prompt).
* ``$ <args>`` runs a tulpa command, e.g. ``$ check main.rav``, ``$ verify lib/pinn.rav``,
  ``$ graph main.rav`` — in the project folder.
* ``! <command>`` runs a system shell command in the project folder.
* ``:clear`` clears the screen, ``:restart`` restarts the REPL, ``:help`` shows REPL help.
* ↑/↓ walk the history; Ctrl+C interrupts (kills and restarts the REPL or the running command);
  Ctrl+L clears.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QToolButton,
                               QVBoxLayout, QWidget)

from gui.ide import theme

_PROMPT_RE = re.compile(r"(?:tulpa> |  \.\.\.> )")
_BANNER_RE = re.compile(r"^Tulpa [\d.]+ REPL.*$", re.M)


class _Input(QLineEdit):
    """Line edit with shell-style history."""

    def __init__(self, term: "TulpaTerminal") -> None:
        super().__init__()
        self.term = term
        self.history: list[str] = []
        self.pos = 0

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.key() == Qt.Key_Up and self.history:
            self.pos = max(0, self.pos - 1)
            self.setText(self.history[self.pos])
            return
        if e.key() == Qt.Key_Down and self.history:
            self.pos = min(len(self.history), self.pos + 1)
            self.setText(self.history[self.pos] if self.pos < len(self.history) else "")
            return
        if e.key() == Qt.Key_C and e.modifiers() & Qt.ControlModifier and not self.hasSelectedText():
            self.term.interrupt()
            return
        super().keyPressEvent(e)

    def remember(self, line: str) -> None:
        if line and (not self.history or self.history[-1] != line):
            self.history.append(line)
        self.pos = len(self.history)


class TulpaTerminal(QWidget):
    def __init__(self, toolchain_getter, parent=None) -> None:
        super().__init__(parent)
        self._tc = toolchain_getter        # callable → Toolchain | None (changes in Settings)
        self.cwd: str = os.getcwd()
        self.repl: Optional[QProcess] = None
        self.job: Optional[QProcess] = None
        self._continuation = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.view = QPlainTextEdit(readOnly=True)
        self.view.setFont(theme.mono_font(10))
        self.view.setMaximumBlockCount(20000)
        self.view.setStyleSheet(f"QPlainTextEdit {{ background: {theme.BG1}; border: none; padding: 4px; }}")
        lay.addWidget(self.view, 1)

        row = QHBoxLayout()
        row.setContentsMargins(6, 4, 6, 4)
        self.prompt = QLabel("tulpa›")
        self.prompt.setFont(theme.mono_font(10))
        self.prompt.setStyleSheet(f"color: {theme.CYAN};")
        row.addWidget(self.prompt)
        self.input = _Input(self)
        self.input.setFont(theme.mono_font(10))
        self.input.setPlaceholderText("Tulpa expression  ·  $ check main.rav  ·  ! shell command  ·  :help")
        self.input.returnPressed.connect(self._submit)
        row.addWidget(self.input, 1)
        for text, tip, fn in [("⟲", "Restart the REPL", self.restart), ("⌫", "Clear (Ctrl+L)", self.view.clear)]:
            b = QToolButton(text=text)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        QShortcut(QKeySequence("Ctrl+L"), self, self.view.clear)

    # ------------------------------------------------------------------ output

    def _write(self, text: str, kind: str = "out") -> None:
        if not text:
            return
        fmt = QTextCharFormat()
        fmt.setForeground(QColor({"in": theme.CYAN, "err": theme.RED, "sys": theme.MUTED,
                                  "ok": theme.GREEN}.get(kind, theme.TEXT)))
        c = self.view.textCursor()
        c.movePosition(QTextCursor.End)
        c.insertText(text, fmt)
        self.view.setTextCursor(c)
        self.view.ensureCursorVisible()

    def _set_prompt(self) -> None:
        if self.job is not None:
            self.prompt.setText("  run›")
        else:
            self.prompt.setText(" ...›" if self._continuation else "tulpa›")

    # ------------------------------------------------------------------ REPL process

    def _env(self) -> QProcessEnvironment:
        tc = self._tc()
        env = QProcessEnvironment()
        for k, v in (tc.env() if tc else dict(os.environ)).items():
            env.insert(k, v)
        return env

    def start(self, cwd: Optional[str] = None) -> None:
        """(Re)start the REPL, optionally in a new working directory (the project root)."""
        if cwd:
            self.cwd = cwd
        self._kill(self.repl)
        self.repl = None
        self._continuation = False
        tc = self._tc()
        if tc is None:
            self._write("tulpa toolchain not found — Settings ▸ Tulpa Toolchain…\n", "err")
            return
        p = QProcess(self)
        p.setProgram(str(tc.binary))
        p.setArguments([])
        p.setWorkingDirectory(self.cwd)
        p.setProcessEnvironment(self._env())
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.readyReadStandardOutput.connect(lambda: self._repl_output(p))
        p.finished.connect(lambda code, _st: self._repl_finished(p, code))
        p.start()
        self.repl = p
        self._write(f"── Tulpa REPL ({tc.version}) in {self.cwd}\n", "sys")
        self._set_prompt()

    def restart(self) -> None:
        self.start()

    def _repl_output(self, p: QProcess) -> None:
        raw = bytes(p.readAllStandardOutput()).decode("utf-8", "replace")
        self._continuation = raw.endswith("...> ")
        text = _BANNER_RE.sub("", _PROMPT_RE.sub("", raw)).lstrip("\n") if raw else ""
        if text:
            self._write(text, "err" if text.startswith("error") else "out")
        self._set_prompt()

    def _repl_finished(self, p: QProcess, code: int) -> None:
        if p is self.repl:
            self._write(f"── REPL exited ({code}); press ⟲ or type :restart\n", "sys")
            self.repl = None

    # ------------------------------------------------------------------ commands

    def _submit(self) -> None:
        line = self.input.text()
        self.input.clear()
        self.input.remember(line.strip())
        stripped = line.strip()
        if self.job is not None and self.job.state() != QProcess.NotRunning:
            # forward input to a running command (e.g. a program reading stdin)
            self._write(line + "\n", "in")
            self.job.write((line + "\n").encode())
            return
        if stripped in (":clear", "clear", "cls"):
            self.view.clear()
            return
        if stripped in (":restart", ":reset"):
            self.restart()
            return
        if stripped.startswith("$"):
            self._write(f"$ tulpa {stripped[1:].strip()}\n", "in")
            self._run_job(stripped[1:].strip(), tulpa=True)
            return
        if stripped.startswith("!"):
            self._write(f"! {stripped[1:].strip()}\n", "in")
            self._run_job(stripped[1:].strip(), tulpa=False)
            return
        if self.repl is None or self.repl.state() == QProcess.NotRunning:
            self.start()
        self._write(("... " if self._continuation else "› ") + line + "\n", "in")
        if self.repl is not None:
            self.repl.write((line + "\n").encode("utf-8"))

    def _run_job(self, args: str, tulpa: bool) -> None:
        import shlex
        p = QProcess(self)
        p.setWorkingDirectory(self.cwd)
        p.setProcessEnvironment(self._env())
        p.setProcessChannelMode(QProcess.MergedChannels)
        if tulpa:
            tc = self._tc()
            if tc is None:
                self._write("tulpa toolchain not found\n", "err")
                return
            try:
                argv = shlex.split(args, posix=os.name != "nt")
            except ValueError as exc:
                self._write(f"{exc}\n", "err")
                return
            p.setProgram(str(tc.binary))
            p.setArguments(argv)
        elif sys.platform == "win32":
            p.setProgram(os.environ.get("COMSPEC", "cmd.exe"))
            p.setArguments(["/d", "/s", "/c", args])
        else:
            p.setProgram(os.environ.get("SHELL", "/bin/sh"))
            p.setArguments(["-c", args])
        p.readyReadStandardOutput.connect(
            lambda: self._write(bytes(p.readAllStandardOutput()).decode("utf-8", "replace")))
        p.finished.connect(lambda code, _st: self._job_done(p, code))
        p.errorOccurred.connect(lambda err: self._write(f"cannot start: {p.errorString()}\n", "err")
                                if err == QProcess.FailedToStart else None)
        self.job = p
        self._set_prompt()
        p.start()

    def _job_done(self, p: QProcess, code: int) -> None:
        if p is self.job:
            self._write(f"── exit {code}\n", "ok" if code == 0 else "err")
            self.job = None
            self._set_prompt()

    def interrupt(self) -> None:
        if self.job is not None and self.job.state() != QProcess.NotRunning:
            self._write("^C\n", "sys")
            self._kill(self.job)
            return
        self._write("^C — restarting REPL\n", "sys")
        self.restart()

    @staticmethod
    def _kill(p: Optional[QProcess]) -> None:
        if p is not None and p.state() != QProcess.NotRunning:
            p.kill()
            p.waitForFinished(1000)

    def shutdown(self) -> None:
        self._kill(self.job)
        self._kill(self.repl)

    def run_in_terminal(self, text: str) -> None:
        """Send a snippet (e.g. the editor selection) to the REPL line by line."""
        for line in text.splitlines():
            self.input.setText(line)
            self._submit()
