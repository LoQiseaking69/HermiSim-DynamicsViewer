"""HermiSim "Ghost Raven" theme — near-black surfaces, cyan signal, violet accent."""

from PySide6.QtGui import QColor, QFont, QPalette

BG0 = "#07090d"      # window
BG1 = "#0c1016"      # panels / editor
BG2 = "#121821"      # cards, tabs
BG3 = "#1a2230"      # hover / selection base
LINE = "#1f2a38"
LINE2 = "#2b394b"
TEXT = "#d7e3f0"
MUTED = "#7d8ea3"
CYAN = "#00e5ff"
CYAN_DIM = "#0aa3b8"
VIOLET = "#9b5cff"
MAGENTA = "#ff3dbb"
GREEN = "#36e39a"
AMBER = "#ffb547"
RED = "#ff4d6d"

# syntax colours
SYN = {
    "keyword": "#9b5cff", "contract": "#ff3dbb", "storage": "#59a8ff", "control": "#9b5cff",
    "string": "#7ee0a8", "number": "#ffb547", "unit": "#00e5ff", "comment": "#55657a",
    "function": "#7fd4ff", "type": "#4fe0c8", "constant": "#ff8f6b", "macro": "#ffd166",
    "device": "#4fe0c8", "operator": "#a7b6c9", "primed": "#ff3dbb", "path": "#4fe0c8",
    "state": "#ffd166",
}

MONO = "JetBrains Mono, Cascadia Code, Fira Code, Consolas, DejaVu Sans Mono, monospace"


def mono_font(size: int = 11) -> QFont:
    f = QFont()
    f.setFamilies(["JetBrains Mono", "Cascadia Code", "Fira Code", "Consolas", "DejaVu Sans Mono", "Monospace"])
    f.setStyleHint(QFont.Monospace)
    f.setPointSize(size)
    return f


def apply(app) -> None:
    f = QFont()
    f.setFamilies(["Inter", "Segoe UI", "Noto Sans", "DejaVu Sans"])
    f.setPointSize(10)
    app.setFont(f)
    p = QPalette()
    for role, c in [(QPalette.Window, BG0), (QPalette.WindowText, TEXT), (QPalette.Base, BG1),
                    (QPalette.AlternateBase, BG2), (QPalette.ToolTipBase, BG2), (QPalette.ToolTipText, TEXT),
                    (QPalette.Text, TEXT), (QPalette.Button, BG2), (QPalette.ButtonText, TEXT),
                    (QPalette.Highlight, "#1d3b55"), (QPalette.HighlightedText, "#ffffff"),
                    (QPalette.Link, CYAN), (QPalette.PlaceholderText, MUTED)]:
        p.setColor(role, QColor(c))
    app.setPalette(p)
    app.setStyleSheet(f"""
    QMainWindow, QDialog {{ background: {BG0}; }}
    QWidget {{ color: {TEXT}; }}
    QToolTip {{ background: {BG2}; color: {TEXT}; border: 1px solid {CYAN_DIM}; padding: 6px; }}
    QMenuBar {{ background: {BG0}; border-bottom: 1px solid {LINE}; padding: 2px; }}
    QMenuBar::item {{ padding: 5px 10px; background: transparent; }}
    QMenuBar::item:selected {{ background: {BG3}; color: {CYAN}; border-radius: 4px; }}
    QMenu {{ background: {BG1}; border: 1px solid {LINE2}; padding: 4px; }}
    QMenu::item {{ padding: 6px 26px 6px 18px; border-radius: 4px; }}
    QMenu::item:selected {{ background: {BG3}; color: {CYAN}; }}
    QMenu::separator {{ height: 1px; background: {LINE}; margin: 4px 8px; }}
    QToolBar {{ background: {BG0}; border: none; border-bottom: 1px solid {LINE}; spacing: 4px; padding: 4px 6px; }}
    QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 5px 9px; color: {TEXT}; }}
    QToolButton:hover {{ background: {BG3}; border-color: {LINE2}; color: {CYAN}; }}
    QToolButton:pressed {{ background: {LINE2}; }}
    QToolButton#runButton {{ color: {GREEN}; font-weight: 600; }}
    QToolButton#simButton {{ color: {CYAN}; font-weight: 600; border: 1px solid {CYAN_DIM}; }}
    QToolButton#stopButton {{ color: {RED}; font-weight: 600; }}
    QDockWidget {{ color: {MUTED}; font-weight: 600; titlebar-close-icon: none; }}
    QDockWidget::title {{ background: {BG0}; padding: 6px 10px; border-bottom: 1px solid {LINE}; text-transform: uppercase; }}
    QTabWidget::pane {{ border: none; border-top: 1px solid {LINE}; background: {BG1}; }}
    QTabBar {{ qproperty-drawBase: 0; background: {BG0}; }}
    QTabBar::tab {{ background: {BG0}; color: {MUTED}; padding: 7px 16px; border: none; border-bottom: 2px solid transparent; }}
    QTabBar::tab:hover {{ color: {TEXT}; background: {BG2}; }}
    QTabBar::tab:selected {{ color: {TEXT}; background: {BG1}; border-bottom: 2px solid {CYAN}; }}
    QTabBar::close-button {{ subcontrol-position: right; }}
    QPlainTextEdit, QTextEdit {{ background: {BG1}; border: none; selection-background-color: #1d3b55; }}
    QTreeView, QListView, QTableView, QTableWidget, QTreeWidget, QListWidget {{
        background: {BG1}; border: none; alternate-background-color: {BG2}; outline: 0;
        selection-background-color: {BG3}; selection-color: {CYAN}; gridline-color: {LINE}; }}
    QTreeView::item, QListView::item {{ padding: 3px 2px; }}
    QTreeView::item:hover, QListView::item:hover {{ background: {BG2}; }}
    QHeaderView::section {{ background: {BG0}; color: {MUTED}; border: none; border-bottom: 1px solid {LINE}; padding: 5px 8px; font-weight: 600; }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {BG2}; border: 1px solid {LINE2}; border-radius: 6px; padding: 5px 8px; selection-background-color: #1d3b55; }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {CYAN_DIM}; }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView {{ background: {BG1}; border: 1px solid {LINE2}; selection-background-color: {BG3}; }}
    QPushButton {{ background: {BG2}; border: 1px solid {LINE2}; border-radius: 6px; padding: 6px 14px; }}
    QPushButton:hover {{ border-color: {CYAN_DIM}; color: {CYAN}; }}
    QPushButton#primary {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0b6f80, stop:1 #5b2bb5); border: none; color: white; font-weight: 600; }}
    QPushButton#primary:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0e8aa0, stop:1 #6f3bd6); }}
    QStatusBar {{ background: {BG0}; border-top: 1px solid {LINE}; color: {MUTED}; }}
    QStatusBar QLabel {{ color: {MUTED}; padding: 0 8px; }}
    QScrollBar:vertical {{ background: transparent; width: 11px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {LINE2}; border-radius: 5px; min-height: 30px; margin: 2px; }}
    QScrollBar::handle:vertical:hover {{ background: {CYAN_DIM}; }}
    QScrollBar:horizontal {{ background: transparent; height: 11px; }}
    QScrollBar::handle:horizontal {{ background: {LINE2}; border-radius: 5px; min-width: 30px; margin: 2px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QSplitter::handle {{ background: {LINE}; }}
    QSlider::groove:horizontal {{ height: 4px; background: {LINE2}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {CYAN}; width: 14px; margin: -6px 0; border-radius: 7px; }}
    QSlider::sub-page:horizontal {{ background: {CYAN_DIM}; border-radius: 2px; }}
    QGroupBox {{ border: 1px solid {LINE}; border-radius: 8px; margin-top: 14px; padding-top: 8px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {MUTED}; }}
    QLabel#heroTitle {{ font-size: 30px; font-weight: 700; color: {TEXT}; }}
    QLabel#heroSub {{ color: {MUTED}; font-size: 13px; }}
    QLabel#sectionTitle {{ color: {CYAN}; font-weight: 700; letter-spacing: 2px; }}
    QFrame#card {{ background: {BG2}; border: 1px solid {LINE}; border-radius: 10px; }}
    QFrame#card:hover {{ border-color: {CYAN_DIM}; }}
    """)
