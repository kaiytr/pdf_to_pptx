"""Application-wide Qt stylesheet and palette."""

from __future__ import annotations

PRIMARY = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
PRIMARY_SOFT = "#EFF6FF"
TEXT = "#0F172A"
MUTED = "#64748B"
BORDER = "#E2E8F0"
BACKGROUND = "#F6F8FC"
SUCCESS = "#059669"
WARNING = "#B45309"
ERROR = "#DC2626"

APP_STYLE = f"""
QMainWindow, QWidget#appRoot {{
    background: {BACKGROUND};
}}
QWidget {{
    color: {TEXT};
    font-family: "Segoe UI", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
    font-size: 13px;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QLabel {{
    background: transparent;
}}
QLabel#appTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#appSubtitle {{
    font-size: 12px;
    color: {MUTED};
}}
QLabel#sectionTitle {{
    font-size: 15px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#muted {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#fieldLabel {{
    color: #334155;
    font-size: 12px;
    font-weight: 600;
}}
QLabel#fileName {{
    font-size: 15px;
    font-weight: 700;
}}
QLabel#fileNameMeta {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#doneTitle {{
    font-size: 26px;
    font-weight: 700;
}}
QLabel#errorTitle {{
    color: {ERROR};
    font-weight: 700;
}}
QLabel#warningText {{
    color: {WARNING};
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 12px;
}}
QLabel#errorText {{
    color: {ERROR};
    background: #FEF2F2;
    border: 1px solid #FECACA;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 12px;
}}
QFrame#card, QFrame#settingsCard, QFrame#fileCard {{
    background: #FFFFFF;
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#dropZone {{
    background: #FFFFFF;
    border: 2px dashed #BFD3F5;
    border-radius: 14px;
}}
QFrame#dropZone[dragActive="true"] {{
    background: {PRIMARY_SOFT};
    border: 2px dashed {PRIMARY};
}}
QFrame#modeCard {{
    background: #FFFFFF;
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QFrame#modeCard[selected="true"] {{
    background: {PRIMARY_SOFT};
    border: 1px solid {PRIMARY};
}}
QFrame#modeCard:hover {{
    border: 1px solid #93B4F8;
}}
QFrame#progressPanel {{
    background: #FFFFFF;
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#progressPanel[state="error"] {{
    background: #FEF2F2;
    border: 1px solid #FECACA;
}}
QFrame#progressPanel[state="done"] {{
    background: #ECFDF5;
    border: 1px solid #A7F3D0;
}}
QPushButton {{
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
    color: #334155;
}}
QPushButton:hover {{
    background: #F8FAFC;
    border-color: #94A3B8;
}}
QPushButton:pressed {{
    background: #F1F5F9;
}}
QPushButton:disabled {{
    color: #94A3B8;
    background: #F1F5F9;
    border-color: #E2E8F0;
}}
QPushButton#primary {{
    background: {PRIMARY};
    color: #FFFFFF;
    border: none;
    border-radius: 9px;
    padding: 11px 22px;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton#primary:hover {{
    background: {PRIMARY_HOVER};
}}
QPushButton#primary:pressed {{
    background: #1E40AF;
}}
QPushButton#primary:disabled {{
    background: #93B4F8;
    color: #EFF6FF;
}}
QPushButton#subtle {{
    background: transparent;
    border: 1px solid transparent;
    color: {MUTED};
    padding: 6px 10px;
    font-weight: 500;
}}
QPushButton#subtle:hover {{
    background: #EFF6FF;
    color: {PRIMARY};
}}
QPushButton#danger {{
    color: {ERROR};
    border-color: #FECACA;
    background: #FFFFFF;
}}
QPushButton#danger:hover {{
    background: #FEF2F2;
}}
QLineEdit, QComboBox, QSpinBox {{
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 8px 10px;
    min-height: 18px;
    selection-background-color: {PRIMARY};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {PRIMARY};
}}
QLineEdit:disabled, QComboBox:disabled {{
    background: #F1F5F9;
    color: #94A3B8;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: #FFFFFF;
    border: 1px solid {BORDER};
    selection-background-color: {PRIMARY_SOFT};
    selection-color: {TEXT};
    outline: none;
}}
QRadioButton {{
    spacing: 8px;
    font-weight: 700;
}}
QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 1.5px solid #94A3B8;
    border-radius: 10px;
    background: #FFFFFF;
}}
QRadioButton::indicator:checked {{
    border: 5px solid {PRIMARY};
    background: #FFFFFF;
    border-radius: 10px;
}}
QProgressBar {{
    background: #E8EEF9;
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {PRIMARY};
    border-radius: 5px;
}}
QProgressBar[state="error"]::chunk {{
    background: {ERROR};
}}
QProgressBar[state="done"]::chunk {{
    background: {SUCCESS};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #CBD5E1;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 6px 10px;
    color: {MUTED};
}}
QToolButton:hover {{
    background: #EFF6FF;
    color: {PRIMARY};
}}
QToolButton::menu-indicator {{
    image: none;
    width: 0;
}}
QMenu {{
    background: #FFFFFF;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 16px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {PRIMARY_SOFT};
    color: {PRIMARY};
}}
QDialog {{
    background: {BACKGROUND};
}}
QMessageBox {{
    background: #FFFFFF;
}}
"""
