"""Monokai colour scheme and Qt stylesheet."""
from __future__ import annotations

BG = "#272822"
BG_DARK = "#1e1f1c"
BG_LIGHT = "#3e3d32"
BORDER = "#49483e"
FG = "#f8f8f2"
FG_DIM = "#75715e"
GREEN = "#a6e22e"
PINK = "#f92672"
CYAN = "#66d9ef"
YELLOW = "#e6db74"
ORANGE = "#fd971f"
PURPLE = "#ae81ff"

QSS = f"""
QWidget {{
    background: {BG};
    color: {FG};
    font-size: 10pt;
    selection-background-color: {BG_LIGHT};
    selection-color: {FG};
}}
QMainWindow, QDialog {{ background: {BG}; }}
QMenuBar {{ background: {BG_DARK}; border-bottom: 1px solid {BORDER}; }}
QMenuBar::item:selected {{ background: {BG_LIGHT}; }}
QMenu {{ background: {BG_DARK}; border: 1px solid {BORDER}; }}
QMenu::item:selected {{ background: {BG_LIGHT}; color: {GREEN}; }}
QToolBar {{ background: {BG_DARK}; border-bottom: 1px solid {BORDER}; spacing: 4px; padding: 3px; }}
QToolButton {{
    background: transparent; color: {FG}; border: 1px solid transparent;
    border-radius: 3px; padding: 4px 8px;
}}
QToolButton:hover {{ background: {BG_LIGHT}; border-color: {BORDER}; }}
QToolButton:checked {{ background: {BG_LIGHT}; border-color: {GREEN}; color: {GREEN}; }}
QStatusBar {{ background: {BG_DARK}; border-top: 1px solid {BORDER}; color: {FG_DIM}; }}
QStatusBar QLabel {{ color: {FG}; padding: 0 6px; }}
QGroupBox {{
    border: 1px solid {BORDER}; border-radius: 4px; margin-top: 10px; padding: 8px 6px 6px 6px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 0 4px;
    color: {CYAN};
}}
QLabel {{ background: transparent; font-weight: normal; }}
QLabel[role="dim"] {{ color: {FG_DIM}; }}
QLabel[role="value"] {{ color: {GREEN}; }}
QLabel[role="error"] {{ color: {PINK}; font-weight: bold; }}
QLabel[role="warn"] {{ color: {YELLOW}; }}
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
    background: {BG_DARK}; border: 1px solid {BORDER}; border-radius: 3px;
    padding: 3px 4px; color: {FG}; min-height: 20px; font-weight: normal;
}}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {CYAN}; }}
QDoubleSpinBox::up-button, QSpinBox::up-button, QDoubleSpinBox::down-button, QSpinBox::down-button {{
    width: 14px; background: {BG_LIGHT}; border: none;
}}
QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
    width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-bottom: 5px solid {FG};
}}
QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
    width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {FG};
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox::down-arrow {{
    width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {FG}; margin-right: 4px;
}}
QComboBox QAbstractItemView {{
    background: {BG_DARK}; border: 1px solid {BORDER}; selection-background-color: {BG_LIGHT};
}}
QPushButton {{
    background: {BG_LIGHT}; border: 1px solid {BORDER}; border-radius: 3px; padding: 5px 10px;
    color: {FG}; font-weight: normal;
}}
QPushButton:hover {{ border-color: {GREEN}; color: {GREEN}; }}
QPushButton:pressed {{ background: {BG_DARK}; }}
QPushButton:disabled {{ color: {FG_DIM}; border-color: {BG_LIGHT}; }}
QPushButton[role="primary"] {{ background: {GREEN}; color: {BG_DARK}; font-weight: bold; border: none; }}
QPushButton[role="primary"]:hover {{ background: #b8f24a; color: {BG_DARK}; }}
QPushButton[role="primary"]:disabled {{ background: {BG_LIGHT}; color: {FG_DIM}; }}
QCheckBox {{ spacing: 6px; font-weight: normal; }}
QCheckBox::indicator {{
    width: 14px; height: 14px; border: 1px solid {BORDER}; border-radius: 2px; background: {BG_DARK};
}}
QCheckBox::indicator:checked {{ background: {GREEN}; border-color: {GREEN}; }}
QTableWidget, QListWidget {{
    background: {BG_DARK}; border: 1px solid {BORDER}; gridline-color: {BORDER};
    alternate-background-color: {BG}; font-weight: normal;
}}
QTableWidget::item:selected, QListWidget::item:selected {{ background: {BG_LIGHT}; color: {GREEN}; }}
QHeaderView::section {{
    background: {BG_LIGHT}; color: {FG}; border: none; border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER}; padding: 3px; font-weight: normal;
}}
QTableCornerButton::section {{ background: {BG_LIGHT}; border: none; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: {BG_DARK}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {BG_LIGHT}; min-height: 24px; border-radius: 4px; margin: 2px; }}
QScrollBar::handle:vertical:hover {{ background: {FG_DIM}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: {BG_DARK}; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {BG_LIGHT}; min-width: 24px; border-radius: 4px; margin: 2px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 3px; top: -1px; }}
QTabBar::tab {{
    background: {BG_DARK}; color: {FG_DIM}; border: 1px solid {BORDER}; border-bottom: none;
    padding: 5px 14px; margin-right: 2px; border-top-left-radius: 3px; border-top-right-radius: 3px;
}}
QTabBar::tab:selected {{ background: {BG}; color: {GREEN}; }}
QTabBar::tab:hover {{ color: {FG}; }}
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 3px; }}
QToolTip {{ background: {BG_DARK}; color: {FG}; border: 1px solid {BORDER}; padding: 3px; }}
QMessageBox {{ background: {BG}; }}
QMessageBox QLabel {{ color: {FG}; }}
"""
