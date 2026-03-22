"""Log viewer tab with integrated Python logging handler."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class _QtLogHandler(logging.Handler, QObject):
    """Bridges Python *logging* to a Qt signal for thread-safe delivery."""

    log_emitted = Signal(str)

    def __init__(self) -> None:
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.log_emitted.emit(msg)
        except Exception:
            self.handleError(record)


class LogTab(QWidget):
    """Tab that displays application logs in real time."""

    _MAX_LOG_LINES = 5000

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._handler = _QtLogHandler()
        self._init_ui()
        self._handler.log_emitted.connect(self._append_log)

        # Attach to root logger so all app logs show up
        root = logging.getLogger()
        root.addHandler(self._handler)
        if root.level > logging.DEBUG:
            root.setLevel(logging.DEBUG)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self._level_combo = QComboBox()
        self._level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self._level_combo.setCurrentText("INFO")
        self._level_combo.currentTextChanged.connect(self._on_level_changed)
        toolbar.addWidget(self._level_combo)

        self._clear_btn = QPushButton("Clear Logs")
        self._clear_btn.clicked.connect(self._clear_logs)
        toolbar.addWidget(self._clear_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Log viewer
        self._log_viewer = QTextEdit()
        self._log_viewer.setReadOnly(True)
        self._log_viewer.setLineWrapMode(QTextEdit.NoWrap)
        self._log_viewer.setStyleSheet(
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 12px;"
        )
        layout.addWidget(self._log_viewer)

    def _append_log(self, message: str) -> None:
        level = self._level_combo.currentText()
        min_level = getattr(logging, level, logging.INFO)
        # Quick filter based on the level tag in the formatted message
        for lvl_name in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            if f"[{lvl_name}]" in message:
                if getattr(logging, lvl_name) < min_level:
                    return
                break

        self._log_viewer.append(message)

        # Trim if too large
        doc = self._log_viewer.document()
        if doc.blockCount() > self._MAX_LOG_LINES:
            cursor = self._log_viewer.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(
                cursor.Down,
                cursor.KeepAnchor,
                doc.blockCount() - self._MAX_LOG_LINES,
            )
            cursor.removeSelectedText()

    def _on_level_changed(self, level: str) -> None:
        self._handler.setLevel(getattr(logging, level, logging.INFO))

    def _clear_logs(self) -> None:
        self._log_viewer.clear()

    def add_log(self, message: str) -> None:
        """Legacy API for direct log injection."""
        self._log_viewer.append(message)
