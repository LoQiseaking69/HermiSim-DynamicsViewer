"""HermiSim visual theme — refined dark palette with accent highlights."""

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtCore import Qt


# -- Colour tokens ----------------------------------------------------------

_BG_DARK      = "#0d1117"
_BG_MID       = "#161b22"
_BG_CARD      = "#1c2128"
_BG_ELEVATED  = "#242a33"
_BORDER       = "#30363d"
_BORDER_LIGHT = "#3d444d"
_TEXT_PRIMARY  = "#e6edf3"
_TEXT_MUTED    = "#8b949e"
_ACCENT       = "#7c3aed"   # violet-600
_ACCENT_HOVER = "#8b5cf6"   # violet-500
_ACCENT_GLOW  = "#a78bfa"   # violet-400
_DANGER       = "#f85149"
_SUCCESS      = "#3fb950"
_WARNING      = "#d29922"


def apply_styles(app) -> None:
    """Apply the HermiSim dark palette and stylesheet to *app*."""

    # -- Font ---------------------------------------------------------------
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # -- QPalette -----------------------------------------------------------
    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor(_BG_DARK))
    palette.setColor(QPalette.WindowText,      QColor(_TEXT_PRIMARY))
    palette.setColor(QPalette.Base,            QColor(_BG_MID))
    palette.setColor(QPalette.AlternateBase,   QColor(_BG_CARD))
    palette.setColor(QPalette.ToolTipBase,     QColor(_BG_ELEVATED))
    palette.setColor(QPalette.ToolTipText,     QColor(_TEXT_PRIMARY))
    palette.setColor(QPalette.Text,            QColor(_TEXT_PRIMARY))
    palette.setColor(QPalette.Button,          QColor(_BG_CARD))
    palette.setColor(QPalette.ButtonText,      QColor(_TEXT_PRIMARY))
    palette.setColor(QPalette.BrightText,      QColor(_DANGER))
    palette.setColor(QPalette.Highlight,       QColor(_ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.Link,            QColor(_ACCENT_GLOW))
    app.setPalette(palette)

    # -- Stylesheet ---------------------------------------------------------
    app.setStyleSheet(f"""

    /* ---- Global ---- */
    QMainWindow {{
        background-color: {_BG_DARK};
    }}

    /* ---- Tab bar ---- */
    QTabWidget::pane {{
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 4px;
        background: {_BG_MID};
    }}
    QTabBar {{
        qproperty-drawBase: 0;
    }}
    QTabBar::tab {{
        background: {_BG_CARD};
        color: {_TEXT_MUTED};
        border: 1px solid {_BORDER};
        padding: 8px 18px;
        margin-right: 2px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        font-weight: 500;
    }}
    QTabBar::tab:hover {{
        background: {_BG_ELEVATED};
        color: {_TEXT_PRIMARY};
    }}
    QTabBar::tab:selected {{
        background: {_BG_MID};
        color: {_ACCENT_GLOW};
        border-bottom: 2px solid {_ACCENT};
    }}

    /* ---- Buttons ---- */
    QPushButton {{
        background-color: {_BG_CARD};
        color: {_TEXT_PRIMARY};
        border: 1px solid {_BORDER};
        padding: 7px 16px;
        border-radius: 6px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {_BG_ELEVATED};
        border-color: {_BORDER_LIGHT};
    }}
    QPushButton:pressed {{
        background-color: {_ACCENT};
        border-color: {_ACCENT};
    }}
    QPushButton:disabled {{
        color: {_TEXT_MUTED};
        background-color: {_BG_DARK};
        border-color: {_BORDER};
    }}

    /* ---- Group boxes ---- */
    QGroupBox {{
        border: 1px solid {_BORDER};
        border-radius: 8px;
        margin-top: 14px;
        padding: 14px 10px 10px 10px;
        font-weight: 600;
        color: {_TEXT_PRIMARY};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 2px 10px;
        color: {_ACCENT_GLOW};
    }}

    /* ---- Labels ---- */
    QLabel {{
        color: {_TEXT_PRIMARY};
    }}

    /* ---- Line edits / spin boxes ---- */
    QLineEdit, QDoubleSpinBox, QSpinBox {{
        background-color: {_BG_DARK};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 6px 10px;
        color: {_TEXT_PRIMARY};
        selection-background-color: {_ACCENT};
    }}
    QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
        border-color: {_ACCENT};
    }}

    /* ---- Combo boxes ---- */
    QComboBox {{
        background-color: {_BG_CARD};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 6px 10px;
        color: {_TEXT_PRIMARY};
        min-width: 80px;
    }}
    QComboBox:hover {{
        border-color: {_BORDER_LIGHT};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {_BG_ELEVATED};
        border: 1px solid {_BORDER};
        selection-background-color: {_ACCENT};
        color: {_TEXT_PRIMARY};
        padding: 4px;
    }}

    /* ---- Sliders ---- */
    QSlider::groove:horizontal {{
        background: {_BORDER};
        height: 6px;
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {_ACCENT};
        border: 2px solid {_ACCENT_HOVER};
        width: 16px;
        margin: -6px 0;
        border-radius: 9px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {_ACCENT_HOVER};
        border-color: {_ACCENT_GLOW};
    }}
    QSlider::sub-page:horizontal {{
        background: {_ACCENT};
        border-radius: 3px;
    }}

    /* ---- Tables ---- */
    QTableWidget, QTableView {{
        background-color: {_BG_DARK};
        alternate-background-color: {_BG_CARD};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        gridline-color: {_BORDER};
        color: {_TEXT_PRIMARY};
    }}
    QHeaderView::section {{
        background-color: {_BG_CARD};
        color: {_ACCENT_GLOW};
        border: none;
        border-bottom: 2px solid {_ACCENT};
        padding: 6px 10px;
        font-weight: 600;
    }}

    /* ---- Text edits (logs) ---- */
    QTextEdit {{
        background-color: {_BG_DARK};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        color: {_TEXT_PRIMARY};
        padding: 6px;
    }}

    /* ---- Scroll bars ---- */
    QScrollBar:vertical {{
        background: {_BG_DARK};
        width: 10px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: {_BORDER_LIGHT};
        min-height: 30px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {_ACCENT};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: {_BG_DARK};
        height: 10px;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal {{
        background: {_BORDER_LIGHT};
        min-width: 30px;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {_ACCENT};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* ---- Menus ---- */
    QMenuBar {{
        background-color: {_BG_DARK};
        border-bottom: 1px solid {_BORDER};
        padding: 2px;
    }}
    QMenuBar::item {{
        background: transparent;
        color: {_TEXT_MUTED};
        padding: 6px 12px;
        border-radius: 4px;
    }}
    QMenuBar::item:selected {{
        background: {_BG_ELEVATED};
        color: {_TEXT_PRIMARY};
    }}
    QMenu {{
        background-color: {_BG_ELEVATED};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 4px 0;
        color: {_TEXT_PRIMARY};
    }}
    QMenu::item {{
        padding: 6px 28px;
    }}
    QMenu::item:selected {{
        background: {_ACCENT};
        border-radius: 4px;
    }}
    QMenu::separator {{
        height: 1px;
        background: {_BORDER};
        margin: 4px 8px;
    }}

    /* ---- Tooltips ---- */
    QToolTip {{
        background-color: {_BG_ELEVATED};
        color: {_TEXT_PRIMARY};
        border: 1px solid {_BORDER};
        border-radius: 4px;
        padding: 4px 8px;
    }}

    /* ---- Status bar ---- */
    QStatusBar {{
        background-color: {_BG_DARK};
        border-top: 1px solid {_BORDER};
        color: {_TEXT_MUTED};
        font-size: 11px;
    }}

    /* ---- Splitters ---- */
    QSplitter::handle {{
        background: {_BORDER};
    }}

    /* ---- Progress bars ---- */
    QProgressBar {{
        background-color: {_BG_DARK};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        text-align: center;
        color: {_TEXT_PRIMARY};
        height: 18px;
    }}
    QProgressBar::chunk {{
        background-color: {_ACCENT};
        border-radius: 5px;
    }}

    /* ---- Wizard-style step indicator ---- */
    QListWidget {{
        background-color: {_BG_DARK};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        color: {_TEXT_PRIMARY};
        outline: none;
    }}
    QListWidget::item {{
        padding: 10px 14px;
        border-radius: 4px;
    }}
    QListWidget::item:selected {{
        background-color: {_ACCENT};
        color: #ffffff;
    }}
    QListWidget::item:hover:!selected {{
        background-color: {_BG_ELEVATED};
    }}
    """)
