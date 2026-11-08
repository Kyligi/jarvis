"""Nebula : palette et feuille de style uniques (dimensions logiques Qt/HiDPI)."""
BACKGROUND = "#0B1220"
SURFACE = "#15243A"
CYAN = "#22D3EE"
VIOLET = "#A78BFA"
SUCCESS = "#4ADE80"
TEXT = "#E4EDF7"
MUTED = "#9BAEC5"
BORDER = "#2B405A"

STYLE = f"""
QWidget {{ background: {BACKGROUND}; color: {TEXT}; font-family: 'Inter', 'Noto Sans', sans-serif; font-size: 13px; }}
QFrame#card, QWidget#monitorDashboard {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#card QLabel, QWidget#monitorDashboard QLabel, QWidget#monitorDashboard QWidget {{ background: transparent; border: none; }}
QLabel#eyebrow {{ color: {CYAN}; font-size: 11px; font-weight: 700; }}
QLabel#heading {{ font-size: 27px; font-weight: 700; }}
QLabel#subheading {{ font-size: 18px; font-weight: 600; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#status {{ color: {SUCCESS}; }}
QLabel#metricValue {{ font-size: 23px; font-weight: 600; }}
QLineEdit, QTextEdit, QPlainTextEdit, QListWidget, QTableWidget, QTreeWidget, QComboBox, QSpinBox {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px; selection-background-color: #23546A; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus {{ border: 1px solid {CYAN}; }}
QPushButton {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 9px 14px; font-weight: 600; }}
QPushButton:hover {{ background: #203B53; border-color: {CYAN}; }}
QPushButton:focus {{ border: 1px solid {CYAN}; }}
QPushButton#primary {{ background: #126479; border-color: #268BA0; }}
QPushButton:disabled {{ color: #73859B; background: #101D2E; }}
QListWidget#navigation {{ background: transparent; border: none; padding: 0; outline: 0; }}
QListWidget#navigation::item {{ padding: 14px 12px; margin: 3px 0; border-radius: 8px; }}
QListWidget#navigation::item:selected {{ color: {CYAN}; background: {SURFACE}; border-left: 3px solid {CYAN}; }}
QListWidget#navigation::item:hover {{ background: {SURFACE}; }}
QHeaderView::section {{ background: {SURFACE}; color: {MUTED}; border: none; padding: 9px; text-align: left; }}
QTableWidget {{ gridline-color: {BORDER}; }}
QProgressBar {{ background: {BORDER}; border: none; border-radius: 3px; }}
QProgressBar::chunk {{ background: {CYAN}; border-radius: 3px; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ width: 8px; background: {BACKGROUND}; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QCheckBox {{ spacing: 10px; background: transparent; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {MUTED}; border-radius: 4px; background: {BACKGROUND}; }}
QCheckBox::indicator:checked {{ background: {CYAN}; border: 1px solid {CYAN}; }}
QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {CYAN}; }}
"""
