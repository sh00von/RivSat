"""
MapView — QWidget wrapping a QWebEngineView that hosts the Leaflet/Geoman map.

Registers the QWebChannel `MapBridge` so JavaScript drawing events flow into
Python, and exposes a clean Python API that drives the map via runJavaScript.
"""
import os
import json
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebChannel import QWebChannel

from rivsat.app.state import state
from rivsat.app.qt.map.bridge import MapBridge

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_MAP_HTML = os.path.join(_ASSETS, "map.html")


class MapView(QWidget):
    mapReady        = pyqtSignal()
    featuresChanged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ready = False
        self._pending = []   # JS calls queued until the page is ready

        self.web = QWebEngineView()
        s = self.web.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        # QWebChannel bridge
        self.channel = QWebChannel()
        self.bridge  = MapBridge()
        self.channel.registerObject("bridge", self.bridge)
        self.web.page().setWebChannel(self.channel)

        self.bridge.mapReady.connect(self._on_ready)
        self.bridge.featuresChanged.connect(self.featuresChanged)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)

        self.web.load(QUrl.fromLocalFile(_MAP_HTML))

    # ── readiness / JS dispatch ────────────────────────────────────────────────
    def _on_ready(self):
        self._ready = True
        for js in self._pending:
            self.web.page().runJavaScript(js)
        self._pending = []
        self.mapReady.emit()

    def _js(self, code: str):
        if self._ready:
            self.web.page().runJavaScript(code)
        else:
            self._pending.append(code)

    # ── Python → map API ───────────────────────────────────────────────────────
    def set_basemap(self, name: str):
        self._js(f"window.RS.setBasemap({json.dumps(name)});")

    def set_active_role(self, role: str):
        state.active_layer = role
        self._js(f"window.RS.setActiveRole({json.dumps(role)});")

    def set_role_visible(self, role: str, visible: bool):
        self._js(f"window.RS.setRoleVisible({json.dumps(role)}, {str(bool(visible)).lower()});")

    def clear_role(self, role: str):
        self._js(f"window.RS.clearRole({json.dumps(role)});")

    def zoom_to_role(self, role: str):
        self._js(f"window.RS.zoomToRole({json.dumps(role)});")

    def zoom_to_all(self):
        self._js("window.RS.zoomToAll();")

    def load_features(self, features: dict):
        """features dict → draw everything on the map (used by file load)."""
        self.bridge.reset_tracking()
        self._js(f"window.RS.loadFeatures({json.dumps(json.dumps(features))});")

    # ── result overlays ────────────────────────────────────────────────────────
    def add_overlay(self, key, png_url, bounds, opacity, label):
        self._js(
            f"window.RS.addOverlay({json.dumps(key)}, {json.dumps(png_url)}, "
            f"{json.dumps(bounds)}, {float(opacity)}, {json.dumps(label)});"
        )

    def set_overlay_visible(self, key, visible):
        self._js(f"window.RS.setOverlayVisible({json.dumps(key)}, {str(bool(visible)).lower()});")

    def set_overlay_opacity(self, key, opacity):
        self._js(f"window.RS.setOverlayOpacity({json.dumps(key)}, {float(opacity)});")

    def zoom_to_overlay(self, key):
        self._js(f"window.RS.zoomToOverlay({json.dumps(key)});")
