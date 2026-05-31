"""
Dark theme stylesheet for the Fire & Smoke Detection System dashboard.
Professional dark palette with fire-safety accent colors.
"""

# ── Color palette ──────────────────────────────────────────────────────────────
BG_DARK       = "#0d1117"
BG_CARD       = "#161b22"
BG_INPUT      = "#21262d"
BORDER        = "#30363d"
TEXT_PRIMARY   = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
ACCENT_BLUE    = "#58a6ff"
ACCENT_GREEN   = "#3fb950"
ACCENT_YELLOW  = "#d29922"
ACCENT_RED     = "#f85149"
ACCENT_ORANGE  = "#e3803b"

DARK_STYLESHEET = f"""
/* ── Global ────────────────────────────────────────────────────────────── */
QMainWindow, QDialog {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}

QWidget {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
}}

/* ── Cards / Frames ────────────────────────────────────────────────────── */
QFrame[frameShape="4"], .card {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QGroupBox {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding: 14px 10px 10px 10px;
    font-weight: bold;
    font-size: 13px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: {ACCENT_BLUE};
}}

/* ── Labels ────────────────────────────────────────────────────────────── */
QLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
}}
QLabel[class="subtitle"] {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
}}
QLabel[class="title"] {{
    font-size: 18px;
    font-weight: bold;
    color: {ACCENT_ORANGE};
}}

/* ── Buttons ───────────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
    min-height: 28px;
}}
QPushButton:hover {{
    background-color: {BORDER};
    border-color: {ACCENT_BLUE};
}}
QPushButton:pressed {{
    background-color: {ACCENT_BLUE};
    color: {BG_DARK};
}}
QPushButton[class="primary"] {{
    background-color: {ACCENT_BLUE};
    color: {BG_DARK};
    border: none;
}}
QPushButton[class="primary"]:hover {{
    background-color: #79c0ff;
}}
QPushButton[class="danger"] {{
    background-color: {ACCENT_RED};
    color: white;
    border: none;
}}
QPushButton[class="danger"]:hover {{
    background-color: #ff7b72;
}}
QPushButton[class="success"] {{
    background-color: {ACCENT_GREEN};
    color: {BG_DARK};
    border: none;
}}

/* ── Inputs ─────────────────────────────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 24px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT_BLUE};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_BLUE};
    selection-color: {BG_DARK};
}}

/* ── Sliders ───────────────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    height: 6px;
    background: {BG_INPUT};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT_BLUE};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT_BLUE};
    border-radius: 3px;
}}

/* ── Checkboxes ────────────────────────────────────────────────────────── */
QCheckBox {{
    spacing: 8px;
    color: {TEXT_PRIMARY};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {BORDER};
    border-radius: 4px;
    background-color: {BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT_BLUE};
    border-color: {ACCENT_BLUE};
}}

/* ── Tables / TreeViews ────────────────────────────────────────────────── */
QTableWidget, QTableView {{
    background-color: {BG_CARD};
    alternate-background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: {BORDER};
    selection-background-color: rgba(88, 166, 255, 0.2);
    selection-color: {TEXT_PRIMARY};
}}
QHeaderView::section {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: none;
    border-bottom: 2px solid {ACCENT_BLUE};
    padding: 6px 10px;
    font-weight: bold;
    font-size: 12px;
}}

/* ── Scrollbars ────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {BG_DARK};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_BLUE};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {BG_DARK};
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 30px;
}}

/* ── Tab Widget ────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background-color: {BG_CARD};
}}
QTabBar::tab {{
    background-color: {BG_INPUT};
    color: {TEXT_SECONDARY};
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{
    background-color: {BG_CARD};
    color: {ACCENT_BLUE};
    border-bottom: 2px solid {ACCENT_BLUE};
}}

/* ── Status bar ────────────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {BG_INPUT};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER};
    padding: 4px;
    font-size: 11px;
}}

/* ── Tooltips ──────────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    padding: 6px;
    border-radius: 4px;
}}

/* ── Progress Bar ──────────────────────────────────────────────────────── */
QProgressBar {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    text-align: center;
    color: {TEXT_PRIMARY};
    height: 18px;
    font-size: 11px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT_BLUE};
    border-radius: 3px;
}}
"""
