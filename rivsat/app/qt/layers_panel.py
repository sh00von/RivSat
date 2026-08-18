"""
QGIS-style Layers panel (dockable).

Top section: the four editable role layers (AOI, Centerline, Transects,
Stations) with an active-radio, a visibility checkbox, a live feature count,
and a zoom-to button. Clicking a layer's radio makes it the *active* drawing
target.

Bottom section: result raster overlays with visibility + opacity sliders.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QRadioButton, QButtonGroup, QToolButton, QSlider, QFrame, QScrollArea,
    QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal

from rivsat.app.state import state
from rivsat.app.qt.theme import COLORS
from rivsat.app.qt.icons import icon

_ROLES = [
    ("aoi",        "AOI",        "#e65100"),
    ("centerline", "Centerline", "#1565c0"),
    ("transects",  "Transects",  "#8e24aa"),
    ("stations",   "Stations",   "#43a047"),
]


class _RoleRow(QWidget):
    def __init__(self, role, label, colour, group: QButtonGroup, parent_panel):
        super().__init__()
        self.role = role
        self._panel = parent_panel
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(6)

        self.radio = QRadioButton()
        self.radio.setToolTip("Set as active drawing layer")
        group.addButton(self.radio)
        self.radio.toggled.connect(self._on_active)

        swatch = QLabel()
        swatch.setFixedSize(12, 12)
        swatch.setStyleSheet(f"background:{colour};border-radius:2px;border:1px solid #00000022;")

        self.vis = QCheckBox()
        self.vis.setChecked(True)
        self.vis.setToolTip("Toggle visibility")
        self.vis.stateChanged.connect(
            lambda _s: self._panel.visibilityToggled.emit(self.role, self.vis.isChecked()))

        self.name = QLabel(label)
        self.name.setStyleSheet("font-size:12px;")

        self.count = QLabel("")
        self.count.setStyleSheet(f"color:{COLORS['muted']};font-size:11px;")

        self.zoom = QToolButton()
        self.zoom.setIcon(icon("zoom", COLORS["muted"], 18))
        self.zoom.setToolTip("Zoom to layer")
        self.zoom.setAutoRaise(True)
        self.zoom.clicked.connect(lambda: self._panel.zoomToRequested.emit(self.role))

        self.clear = QToolButton()
        self.clear.setIcon(icon("clear", COLORS["muted"], 18))
        self.clear.setToolTip("Clear layer")
        self.clear.setAutoRaise(True)
        self.clear.clicked.connect(lambda: self._panel.clearRequested.emit(self.role))

        lay.addWidget(self.radio)
        lay.addWidget(swatch)
        lay.addWidget(self.vis)
        lay.addWidget(self.name, 1)
        lay.addWidget(self.count)
        lay.addWidget(self.zoom)
        lay.addWidget(self.clear)

    def _on_active(self, checked):
        if checked:
            self.name.setStyleSheet(f"font-size:12px;font-weight:700;color:{COLORS['navy']};")
            self._panel.activeRoleChanged.emit(self.role)
        else:
            self.name.setStyleSheet("font-size:12px;")

    def set_count(self, n):
        self.count.setText(f"({n})" if n else "")


class _OverlayRow(QWidget):
    def __init__(self, key, label, panel):
        super().__init__()
        self.key = key
        self._panel = panel
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(2)
        top = QHBoxLayout(); top.setSpacing(6)
        self.vis = QCheckBox(); self.vis.setChecked(True)
        self.vis.stateChanged.connect(
            lambda _s: self._panel.overlayVisibilityToggled.emit(self.key, self.vis.isChecked()))
        name = QLabel(label); name.setStyleSheet("font-size:12px;")
        zoom = QToolButton(); zoom.setIcon(icon("zoom", COLORS["muted"], 16)); zoom.setAutoRaise(True)
        zoom.clicked.connect(lambda: self._panel.overlayZoomRequested.emit(self.key))
        top.addWidget(self.vis); top.addWidget(name, 1); top.addWidget(zoom)
        lay.addLayout(top)
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(0, 100); self.opacity.setValue(80)
        self.opacity.valueChanged.connect(
            lambda v: self._panel.overlayOpacityChanged.emit(self.key, v / 100.0))
        lay.addWidget(self.opacity)


class LayersPanel(QWidget):
    activeRoleChanged        = pyqtSignal(str)
    visibilityToggled        = pyqtSignal(str, bool)
    zoomToRequested          = pyqtSignal(str)
    clearRequested           = pyqtSignal(str)
    loadFileRequested        = pyqtSignal()
    zoomAllRequested         = pyqtSignal()
    overlayVisibilityToggled = pyqtSignal(str, bool)
    overlayOpacityChanged    = pyqtSignal(str, float)
    overlayZoomRequested     = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(268)
        self._rows = {}
        self._overlay_rows = {}
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QLabel("  LAYERS")
        header.setStyleSheet(
            f"background:{COLORS['navy']};color:#fff;font-weight:700;"
            f"font-size:12px;letter-spacing:0.4px;padding:7px 10px;")
        outer.addWidget(header)

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(4)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for role, label, colour in _ROLES:
            row = _RoleRow(role, label, colour, self._group, self)
            self._rows[role] = row
            root.addWidget(row)
        # activate AOI by default
        self._rows["aoi"].radio.setChecked(True)

        root.addWidget(self._hline())

        # Results header
        res_hdr = QLabel("RESULTS")
        res_hdr.setStyleSheet(
            f"font-size:10px;font-weight:700;letter-spacing:0.8px;color:{COLORS['muted']};padding:2px 4px;")
        root.addWidget(res_hdr)

        self._overlay_box = QVBoxLayout()
        self._overlay_box.setSpacing(2)
        self._empty_lbl = QLabel("No result overlays yet.\nRun Processing to populate.")
        self._empty_lbl.setStyleSheet(f"color:#b0bec5;font-size:11px;font-style:italic;padding:4px;")
        self._overlay_box.addWidget(self._empty_lbl)
        root.addLayout(self._overlay_box)

        root.addStretch(1)
        root.addWidget(self._hline())

        btns = QHBoxLayout()
        load_btn = QPushButton("  Load file…")
        load_btn.setIcon(icon("load", COLORS["text"], 18))
        load_btn.clicked.connect(self.loadFileRequested)
        zoom_all = QPushButton("  Zoom all")
        zoom_all.setIcon(icon("target", COLORS["text"], 18))
        zoom_all.clicked.connect(self.zoomAllRequested)
        btns.addWidget(load_btn); btns.addWidget(zoom_all)
        root.addLayout(btns)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(container)
        outer.addWidget(scroll)

    def _hline(self):
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{COLORS['border']};")
        return line

    # ── public updates ─────────────────────────────────────────────────────────
    def update_counts(self):
        self._rows["aoi"].set_count(1 if state.aoi_polygon else 0)
        self._rows["centerline"].set_count(1 if state.centerline else 0)
        self._rows["transects"].set_count(len(state.transects))
        self._rows["stations"].set_count(len(state.stations))

    def set_active(self, role):
        if role in self._rows:
            self._rows[role].radio.setChecked(True)

    def add_overlay_row(self, key, label):
        if key in self._overlay_rows:
            return
        if self._empty_lbl is not None:
            self._empty_lbl.hide()
        row = _OverlayRow(key, label, self)
        self._overlay_rows[key] = row
        self._overlay_box.addWidget(row)

    def clear_overlay_rows(self):
        for row in self._overlay_rows.values():
            row.setParent(None)
        self._overlay_rows = {}
        if self._empty_lbl is not None:
            self._empty_lbl.show()
