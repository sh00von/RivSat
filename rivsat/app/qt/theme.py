"""
RivSat Desktop — HEC-RAS-inspired light theme for PyQt6.

Exposes:
    COLORS      — palette dict
    QSS         — application-wide Qt Style Sheet
    apply_mpl_style()  — configure matplotlib rcParams to match
"""

# ── Palette ───────────────────────────────────────────────────────────────────
COLORS = {
    "navy":    "#1a3a5c",   # header / section labels / table headers
    "navy_dk": "#0d2540",   # header bottom border
    "blue":    "#1976d2",   # primary action
    "blue_dk": "#1558b0",   # primary hover
    "grey":    "#f0f2f5",   # panel / dock background
    "grey2":   "#f8f9fb",   # card background
    "white":   "#ffffff",   # canvas
    "border":  "#d0d5dd",   # dividers / input borders
    "text":    "#1a2332",   # primary text
    "muted":   "#5a6478",   # secondary text
    "green":   "#2e7d32",   # success
    "green_dk":"#1b5e20",
    "orange":  "#e65100",   # warning
    "red":     "#c62828",   # error
    "console_bg":  "#1e2636",
    "console_fg":  "#c9d1d9",
    "status_bg":   "#e8eaf0",
}

# ── Application-wide stylesheet ────────────────────────────────────────────────
QSS = f"""
* {{
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 12px;
    color: {COLORS['text']};
}}

QMainWindow, QWidget {{
    background: {COLORS['grey']};
}}

/* ── Menubar ──────────────────────────────────────────────────── */
QMenuBar {{
    background: {COLORS['navy']};
    color: #ffffff;
    padding: 2px 6px;
    border-bottom: 2px solid {COLORS['navy_dk']};
}}
QMenuBar::item {{
    background: transparent;
    color: #ffffff;
    padding: 5px 12px;
    border-radius: 3px;
}}
QMenuBar::item:selected {{ background: {COLORS['blue']}; }}
QMenu {{
    background: #ffffff;
    border: 1px solid {COLORS['border']};
    padding: 4px;
}}
QMenu::item {{ padding: 6px 24px 6px 20px; border-radius: 3px; }}
QMenu::item:selected {{ background: {COLORS['grey']}; color: {COLORS['navy']}; }}
QMenu::separator {{ height: 1px; background: {COLORS['border']}; margin: 4px 8px; }}

/* ── Toolbar ──────────────────────────────────────────────────── */
QToolBar {{
    background: {COLORS['grey']};
    border-bottom: 1px solid {COLORS['border']};
    spacing: 4px;
    padding: 3px 6px;
}}
QToolButton {{
    background: #ffffff;
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 5px 12px;
    font-weight: 600;
}}
QToolButton:hover {{ background: {COLORS['grey']}; border-color: #aab0bc; }}
QToolButton:pressed {{ background: #e2e6ee; }}
QToolButton:checked {{
    background: {COLORS['blue']}; color: #ffffff; border-color: {COLORS['blue']};
}}
QToolButton[autoRaise="true"] {{ border: none; background: transparent; padding: 4px; }}
QToolButton[autoRaise="true"]:hover {{ background: #e2e6ee; border-radius: 4px; }}
QToolButton[autoRaise="true"]:checked {{ background: {COLORS['blue']}; }}

/* ── Radio buttons (layers active-layer selector) ─────────────── */
QRadioButton {{ spacing: 4px; }}
QRadioButton::indicator {{
    width: 13px; height: 13px; border-radius: 7px;
    border: 2px solid {COLORS['border']}; background: #ffffff;
}}
QRadioButton::indicator:checked {{
    border: 2px solid {COLORS['blue']};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
                fx:0.5, fy:0.5, stop:0 {COLORS['blue']}, stop:0.5 {COLORS['blue']},
                stop:0.6 #ffffff, stop:1 #ffffff);
}}

/* ── Tabs ─────────────────────────────────────────────────────── */
QTabWidget::pane {{
    background: {COLORS['white']};
    border: 1px solid {COLORS['border']};
    border-radius: 0 4px 4px 4px;
}}
QTabBar {{
    background: {COLORS['grey']};
    qproperty-drawBase: 0;
}}
QTabBar::tab {{
    background: {COLORS['grey']};
    color: {COLORS['muted']};
    border: 1px solid {COLORS['border']};
    border-bottom: none;
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-weight: 600;
}}
QTabBar::tab:hover {{ background: #e2e6ee; color: {COLORS['navy']}; }}
QTabBar::tab:selected {{
    background: {COLORS['white']};
    color: {COLORS['navy']};
    border-top: 2px solid {COLORS['blue']};
    font-weight: 700;
}}

/* ── Dock widget ──────────────────────────────────────────────── */
QDockWidget {{
    titlebar-close-icon: none;
    font-weight: 700;
}}
QDockWidget::title {{
    background: {COLORS['navy']};
    color: #ffffff;
    padding: 7px 12px;
    font-weight: 700;
    letter-spacing: 0.4px;
}}
QDockWidget > QWidget {{ background: {COLORS['grey2']}; }}

/* ── Inputs ───────────────────────────────────────────────────── */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background: #ffffff;
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: {COLORS['blue']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus {{
    border: 1px solid {COLORS['blue']};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: #ffffff;
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['grey']};
    selection-color: {COLORS['navy']};
}}

/* ── Checkboxes ───────────────────────────────────────────────── */
QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    background: #ffffff;
}}
QCheckBox::indicator:checked {{
    background: {COLORS['blue']};
    border-color: {COLORS['blue']};
    image: none;
}}

/* ── Buttons ──────────────────────────────────────────────────── */
QPushButton {{
    background: #ffffff;
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 6px 16px;
    font-weight: 600;
}}
QPushButton:hover {{ background: {COLORS['grey']}; border-color: #aab0bc; }}
QPushButton:pressed {{ background: #e2e6ee; }}
QPushButton:disabled {{ background: #eceff2; color: #aab0bc; }}

QPushButton[accent="primary"] {{
    background: {COLORS['blue']}; color: #ffffff; border: none;
}}
QPushButton[accent="primary"]:hover {{ background: {COLORS['blue_dk']}; }}
QPushButton[accent="primary"]:disabled {{ background: #b0bec5; color: #eceff2; }}

QPushButton[accent="success"] {{
    background: {COLORS['green']}; color: #ffffff; border: none;
}}
QPushButton[accent="success"]:hover {{ background: {COLORS['green_dk']}; }}
QPushButton[accent="success"]:disabled {{ background: #b0bec5; color: #eceff2; }}

QPushButton[accent="warning"] {{
    background: {COLORS['orange']}; color: #ffffff; border: none;
}}
QPushButton[accent="warning"]:hover {{ background: #bf360c; }}

/* ── Sliders ──────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    height: 5px; background: #e0e6f0; border-radius: 3px;
}}
QSlider::sub-page:horizontal {{ background: {COLORS['blue']}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: {COLORS['blue']}; width: 15px; height: 15px;
    margin: -6px 0; border-radius: 8px; border: 2px solid #ffffff;
}}

/* ── Progress bar ─────────────────────────────────────────────── */
QProgressBar {{
    background: #e0e6f0; border: none; border-radius: 4px;
    height: 8px; text-align: center; font-size: 10px;
}}
QProgressBar::chunk {{ background: {COLORS['blue']}; border-radius: 4px; }}

/* ── Console / log ────────────────────────────────────────────── */
QPlainTextEdit[role="console"], QTextEdit[role="console"] {{
    background: {COLORS['console_bg']};
    color: {COLORS['console_fg']};
    border: 1px solid #2d3748;
    border-radius: 4px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    padding: 6px 8px;
}}

/* ── Tables ───────────────────────────────────────────────────── */
QTableWidget, QTableView {{
    background: #ffffff;
    border: 1px solid {COLORS['border']};
    gridline-color: #eef0f4;
    selection-background-color: #edf3fb;
    selection-color: {COLORS['text']};
}}
QHeaderView::section {{
    background: {COLORS['navy']};
    color: #ffffff;
    padding: 6px 10px;
    border: none;
    font-weight: 600;
}}
QTableWidget::item {{ padding: 4px 8px; }}

/* ── Scrollbars ───────────────────────────────────────────────── */
QScrollBar:vertical {{ background: {COLORS['grey']}; width: 11px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: #c2c9d6; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #a9b2c2; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: {COLORS['grey']}; height: 11px; }}
QScrollBar::handle:horizontal {{ background: #c2c9d6; border-radius: 5px; min-width: 30px; }}

/* ── Status bar ───────────────────────────────────────────────── */
QStatusBar {{
    background: {COLORS['status_bg']};
    border-top: 1px solid {COLORS['border']};
    font-size: 11px;
}}
QStatusBar::item {{ border: none; }}

/* ── Splitter ─────────────────────────────────────────────────── */
QSplitter::handle {{ background: {COLORS['border']}; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}

/* ── GroupBox / cards ─────────────────────────────────────────── */
QGroupBox {{
    background: {COLORS['grey2']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px 12px 12px 12px;
    font-weight: 700;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: {COLORS['navy']};
    font-size: 11px;
    letter-spacing: 0.4px;
}}
"""


def section_label(text: str) -> str:
    """HTML for an uppercase muted section label (used in QLabel.setText)."""
    return (
        f'<span style="font-size:10px;font-weight:700;letter-spacing:0.8px;'
        f'text-transform:uppercase;color:{COLORS["muted"]};">{text}</span>'
    )


def step_header(num: int, title: str) -> str:
    """HTML for a navy step header banner (used in QLabel.setText)."""
    return (
        f'<div style="background:{COLORS["navy"]};color:#ffffff;padding:8px 14px;'
        f'border-radius:4px;font-size:13px;font-weight:700;">'
        f'<span style="opacity:0.65;font-weight:400;">Step {num}</span>'
        f'&nbsp;&nbsp;{title}</div>'
    )


def pill(text: str, kind: str = "grey") -> str:
    """HTML status pill. kind in {green, red, blue, grey, orange}."""
    palette = {
        "green":  ("#e8f5e9", COLORS["green"],  "#a5d6a7"),
        "red":    ("#ffebee", COLORS["red"],    "#ef9a9a"),
        "blue":   ("#e3f2fd", COLORS["blue"],   "#90caf9"),
        "grey":   ("#f5f5f5", COLORS["muted"],  COLORS["border"]),
        "orange": ("#fff3e0", COLORS["orange"], "#ffcc80"),
    }
    bg, fg, bd = palette.get(kind, palette["grey"])
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {bd};'
        f'border-radius:11px;padding:2px 10px;font-size:11px;font-weight:600;">{text}</span>'
    )


def apply_mpl_style():
    """Configure matplotlib to visually match the app theme."""
    import matplotlib as mpl
    mpl.rcParams.update({
        "figure.facecolor":  "#ffffff",
        "axes.facecolor":    "#ffffff",
        "axes.edgecolor":    COLORS["border"],
        "axes.labelcolor":   COLORS["muted"],
        "axes.titlecolor":   COLORS["text"],
        "axes.titlesize":    10,
        "axes.titleweight":  "bold",
        "xtick.color":       COLORS["muted"],
        "ytick.color":       COLORS["muted"],
        "xtick.labelsize":   8,
        "ytick.labelsize":   8,
        "text.color":        COLORS["text"],
        "font.family":       "sans-serif",
        "font.sans-serif":   ["Segoe UI", "DejaVu Sans", "Arial"],
        "figure.dpi":        100,
    })
