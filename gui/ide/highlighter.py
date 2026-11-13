"""TulpaLang syntax highlighting (mirrors editors/vscode/syntaxes/tulpa.tmLanguage.json)."""

from __future__ import annotations

import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

from gui.ide import theme


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Bold)
    if italic:
        f.setFontItalic(True)
    return f


S = theme.SYN
KEYWORDS = r"\b(if|elif|else|while|for|in|loop|break|continue|return|match|try|catch|spawn|await|after|within|enter|exit|on|state)\b"
CONTRACTS = r"\b(require|ensure|invariant|assert|always|when)\b"
STORAGE = r"\b(fn|def|let|const|mut|struct|machine|use|import|from|as)\b"
LOGIC = r"\b(and|or|not)\b"
CONST = r"\b(true|false|nil|self|PI|TAU|E|HIGH|LOW|ARGS)\b"
DEVICES = r"\b(GPIO|I2C|SPI|UART|PWM|Servo|PID|CAN|BLE)\b"
TYPES = r"(?<=[:>]\s)(int|float|num|number|str|bool|list|dict|fn|any|quantity|signal|range|task)\b\??"

RULES: list[tuple[re.Pattern, QTextCharFormat, int]] = [
    (re.compile(r"\b[A-Za-z_]\w*(?=\s*\()"), _fmt(S["function"]), 0),
    (re.compile(KEYWORDS), _fmt(S["keyword"], bold=True), 0),
    (re.compile(CONTRACTS), _fmt(S["contract"], bold=True), 0),
    (re.compile(STORAGE), _fmt(S["storage"], bold=True), 0),
    (re.compile(LOGIC), _fmt(S["keyword"]), 0),
    (re.compile(CONST), _fmt(S["constant"]), 0),
    (re.compile(DEVICES), _fmt(S["device"], bold=True), 0),
    (re.compile(TYPES), _fmt(S["type"]), 0),
    (re.compile(r"\b(fn|def|struct|machine)\s+([A-Za-z_]\w*)"), _fmt(S["function"], bold=True), 2),
    (re.compile(r"=>\s*([A-Z]\w*)"), _fmt(S["state"]), 1),
    (re.compile(r"^\s*state\s+([A-Za-z_]\w*)"), _fmt(S["state"], bold=True), 1),
    (re.compile(r"\b([A-Za-z_]\w*)::([A-Za-z_]\w*)"), _fmt(S["path"]), 0),
    (re.compile(r"\b[A-Za-z_]\w*!(?=\()"), _fmt(S["macro"], bold=True), 0),
    (re.compile(r"\b[A-Za-z_]\w*'"), _fmt(S["primed"], italic=True), 0),
    (re.compile(r"\b0[xX][0-9a-fA-F_]+\b|\b0[bB][01_]+\b|\b\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?\b"), _fmt(S["number"]), 0),
    (re.compile(r"(?<=\d)\[[A-Za-z0-9_*/^.\- ]+\]"), _fmt(S["unit"], bold=True), 0),
    (re.compile(r"(?<=[:>]\s)\[[A-Za-z0-9_*/^.\- ]+\]\??"), _fmt(S["unit"]), 0),
    (re.compile(r"\|>|=>|->|\.\.=?"), _fmt(S["operator"], bold=True), 0),
]
STRING = re.compile(r'f?"(?:[^"\\]|\\.)*"|f?\'(?:[^\'\\]|\\.)*\'')
COMMENT = re.compile(r"#.*$|//.*$")
FSTR_EXPR = re.compile(r"\{[^{}]*\}")


class TulpaHighlighter(QSyntaxHighlighter):
    def __init__(self, doc) -> None:
        super().__init__(doc)
        self.f_string = _fmt(S["string"])
        self.f_interp = _fmt(theme.TEXT)
        self.f_comment = _fmt(S["comment"], italic=True)

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        for rx, fmt, grp in RULES:
            for m in rx.finditer(text):
                s, e = m.span(grp)
                self.setFormat(s, e - s, fmt)
        masked = []
        for m in STRING.finditer(text):
            s, e = m.span()
            self.setFormat(s, e - s, self.f_string)
            if text[s] == "f":
                for im in FSTR_EXPR.finditer(text, s, e):
                    self.setFormat(im.start(), im.end() - im.start(), self.f_interp)
            masked.append((s, e))
        # block comments /* */ across lines
        self.setCurrentBlockState(0)
        start = 0
        if self.previousBlockState() != 1:
            start = text.find("/*")
        while start >= 0:
            end = text.find("*/", start + (0 if self.previousBlockState() == 1 and start == 0 else 2))
            if end < 0:
                self.setCurrentBlockState(1)
                self.setFormat(start, len(text) - start, self.f_comment)
                break
            self.setFormat(start, end + 2 - start, self.f_comment)
            start = text.find("/*", end + 2)
        for m in COMMENT.finditer(text):
            if any(s <= m.start() < e for s, e in masked):
                continue
            self.setFormat(m.start(), len(text) - m.start(), self.f_comment)
            break
