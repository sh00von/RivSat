"""
Map workspace tab — QGIS-style interactive map.

Left: SVG icon toolbar (draw/edit/delete, basemap switch) is provided by
Geoman inside the map, plus a Qt toolbar for basemap + role + file actions.
Center: the live Leaflet map (MapView).
Right: the Layers panel (active-layer drawing, visibility, overlays).
"""
import os
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QToolBar, QComboBox, QLabel, QFileDialog,
    QToolButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction

from rivsat.app.state import state
from rivsat.app.qt.theme import COLORS, pill
from rivsat.app.qt.icons import icon
from rivsat.app.qt.map import MapView
from rivsat.app.qt.layers_panel import LayersPanel
from rivsat import load_geojson_features, validate_spatial_features

_BASEMAPS = ["Esri Satellite", "Google Satellite", "Google Hybrid",
             "OpenStreetMap", "CartoDB Light", "Terrain"]

_ROLE_ACTIVE_ICON = {
    "aoi": "polygon", "centerline": "line", "transects": "line", "stations": "point",
}


class MapTab(QWidget):
    featuresChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._build()
        self._wire()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top toolbar ────────────────────────────────────────────────────────
        tb = QToolBar()
        tb.setIconSize(_qsize(20))
        tb.setStyleSheet(f"QToolBar{{background:{COLORS['grey']};border-bottom:1px solid {COLORS['border']};padding:3px 6px;}}")

        tb.addWidget(QLabel("  Basemap: "))
        self.basemap_cb = QComboBox()
        self.basemap_cb.addItems(_BASEMAPS)
        self.basemap_cb.setFixedWidth(160)
        tb.addWidget(self.basemap_cb)
        tb.addSeparator()

        # Active-role quick buttons (mirror the layers panel radios)
        tb.addWidget(QLabel("  Draw into: "))
        self._role_btns = {}
        for role, label in [("aoi", "AOI"), ("centerline", "Centerline"),
                            ("transects", "Transects"), ("stations", "Stations")]:
            btn = QToolButton()
            btn.setText(label)
            btn.setIcon(icon(_ROLE_ACTIVE_ICON[role], COLORS["text"], 18))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setCheckable(True)
            btn.setAutoRaise(True)
            btn.clicked.connect(lambda _c=False, r=role: self._set_active_role(r))
            self._role_btns[role] = btn
            tb.addWidget(btn)
        self._role_btns["aoi"].setChecked(True)

        tb.addSeparator()
        act_zoom = QAction(icon("target", COLORS["text"], 18), "Zoom to all", self)
        act_zoom.triggered.connect(lambda: self.map_view.zoom_to_all())
        tb.addAction(act_zoom)

        root.addWidget(tb)

        # ── Body: map + layers ─────────────────────────────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.map_view = MapView()
        body.addWidget(self.map_view, 1)

        self.layers = LayersPanel()
        body.addWidget(self.layers)

        body_w = QWidget(); body_w.setLayout(body)
        root.addWidget(body_w, 1)

        # ── Status strip ───────────────────────────────────────────────────────
        self.status = QLabel("")
        self.status.setTextFormat(Qt.TextFormat.RichText)
        self.status.setStyleSheet(
            f"background:{COLORS['grey2']};border-top:1px solid {COLORS['border']};padding:4px 10px;")
        root.addWidget(self.status)
        self._set_status("Draw AOI, centerline, transects, and stations directly on the map.", "grey")

    def _wire(self):
        self.basemap_cb.currentTextChanged.connect(self.map_view.set_basemap)

        # Layers panel ↔ map
        self.layers.activeRoleChanged.connect(self._set_active_role)
        self.layers.visibilityToggled.connect(self.map_view.set_role_visible)
        self.layers.zoomToRequested.connect(self.map_view.zoom_to_role)
        self.layers.clearRequested.connect(self._clear_role)
        self.layers.zoomAllRequested.connect(self.map_view.zoom_to_all)
        self.layers.loadFileRequested.connect(self._load_file)
        self.layers.overlayVisibilityToggled.connect(self.map_view.set_overlay_visible)
        self.layers.overlayOpacityChanged.connect(self.map_view.set_overlay_opacity)
        self.layers.overlayZoomRequested.connect(self.map_view.zoom_to_overlay)

        # Live feature changes from JS bridge
        self.map_view.featuresChanged.connect(self._on_features_changed)
        self.map_view.mapReady.connect(lambda: self._set_status("Map ready.", "green"))

    # ── role activation ────────────────────────────────────────────────────────
    def _set_active_role(self, role):
        state.active_layer = role
        self.map_view.set_active_role(role)
        for r, btn in self._role_btns.items():
            btn.blockSignals(True); btn.setChecked(r == role); btn.blockSignals(False)
        self.layers.set_active(role)

    def _clear_role(self, role):
        self.map_view.clear_role(role)
        if role == "aoi":
            state.aoi_polygon = []
        elif role == "centerline":
            state.centerline = []
        elif role == "transects":
            state.transects = []
            self.map_view.bridge._transect_ids = []
        elif role == "stations":
            state.stations = []
            self.map_view.bridge._station_ids = []
        self._on_features_changed(role)

    def _on_features_changed(self, role):
        self.layers.update_counts()
        self._set_status(
            f"AOI {1 if state.aoi_polygon else 0} · CL {1 if state.centerline else 0} · "
            f"Transects {len(state.transects)} · Stations {len(state.stations)}", "blue")
        self.featuresChanged.emit()

    # ── file load fallback ──────────────────────────────────────────────────────
    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load GeoJSON layers", os.path.abspath("./data"),
            "GeoJSON (*.geojson *.json);;All (*)")
        if not path:
            return
        try:
            base = os.path.dirname(path)
            features = load_geojson_features(
                geojson_path=path,
                stations_path=os.path.join(base, "stations.geojson"),
                centerline_path=os.path.join(base, "centerline.geojson"))
            validate_spatial_features(features)

            state.aoi_polygon = features["aoi_polygon"] or []
            state.centerline  = features["centerline"] or []
            state.stations    = features["stations"] or []

            payload = {
                "aoi": state.aoi_polygon,
                "centerline": [list(p) for p in state.centerline],
                "transects": [[list(p) for p in t] for t in state.transects],
                "stations": [
                    {"name": s["name"], "lon": s["coords"][0], "lat": s["coords"][1],
                     "buffer": s.get("buffer_pixels", 2)}
                    for s in state.stations
                ],
            }
            self.map_view.load_features(payload)
            self.layers.update_counts()
            self._set_status(f"Loaded {os.path.basename(path)}", "green")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Load failed: {exc}", "red")

    # ── result overlays (called by process tab) ────────────────────────────────
    def add_result_overlay(self, key, label, png_url, bounds, opacity=0.8):
        self.layers.add_overlay_row(key, label)
        self.map_view.add_overlay(key, png_url, bounds, opacity, label)

    def clear_result_overlays(self):
        self.layers.clear_overlay_rows()

    def _set_status(self, msg, kind="grey"):
        self.status.setText(pill(msg, kind))


def _qsize(n):
    from PyQt6.QtCore import QSize
    return QSize(n, n)
