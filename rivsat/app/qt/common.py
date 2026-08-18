"""
Reusable Qt widgets shared across tabs:
    - ConsoleLog     : dark timestamped log console
    - MplCanvas      : matplotlib FigureCanvas + optional toolbar
    - StepHeader     : navy step banner label
    - make_button    : QPushButton with accent property applied
"""
import datetime
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg, NavigationToolbar2QT
)

from PyQt6.QtWidgets import QPlainTextEdit, QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt

from rivsat.app.qt.theme import COLORS, step_header


# ── Console log ────────────────────────────────────────────────────────────────
class ConsoleLog(QPlainTextEdit):
    """Read-only dark console. Call .line(msg) to append a timestamped row."""

    def __init__(self, height=None, placeholder="Log output will appear here …"):
        super().__init__()
        self.setReadOnly(True)
        self.setProperty("role", "console")
        self.setPlaceholderText(placeholder)
        self.setMaximumBlockCount(5000)
        if height is not None:
            self.setFixedHeight(height)

    def line(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.appendPlainText(f"[{ts}]  {msg}")
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_log(self):
        self.clear()


# ── Matplotlib canvas ──────────────────────────────────────────────────────────
class MplCanvas(QWidget):
    """A matplotlib Figure embedded in a Qt widget, with optional nav toolbar."""

    def __init__(self, figsize=(9, 5), toolbar=True):
        super().__init__()
        self.figure = Figure(figsize=figsize, facecolor="#ffffff")
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        if toolbar:
            tb = NavigationToolbar2QT(self.canvas, self)
            tb.setStyleSheet(f"background:{COLORS['grey']};border:none;")
            layout.addWidget(tb)
        layout.addWidget(self.canvas)
        self._show_placeholder()

    def _show_placeholder(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, "Run this step to render results",
                ha="center", va="center", color="#8a93a6", fontsize=11,
                transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        self.canvas.draw_idle()

    def set_figure(self, fig: Figure):
        """Replace the displayed figure with a pre-built one."""
        self.figure.clear()
        # copy axes content by re-drawing: simplest is to swap the canvas figure
        self.canvas.figure = fig
        fig.set_canvas(self.canvas)
        self.figure = fig
        self.canvas.draw_idle()

    def clear_canvas(self):
        self._show_placeholder()


# ── Step header label ──────────────────────────────────────────────────────────
class StepHeader(QLabel):
    def __init__(self, num: int, title: str):
        super().__init__(step_header(num, title))
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setWordWrap(True)


# ── Accent button helper ───────────────────────────────────────────────────────
def make_button(label: str, accent: str = None, width: int = None) -> QPushButton:
    btn = QPushButton(label)
    if accent:
        btn.setProperty("accent", accent)
    if width:
        btn.setFixedWidth(width)
    return btn
