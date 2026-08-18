"""
QWebChannel bridge — receives live drawing events from the Leaflet/Geoman map
(JavaScript) and updates the shared `state`, re-emitting Qt signals so the
Layers panel, status bar, and other widgets update immediately.

The JS side calls (see map.html):
    bridge.onFeatureDrawn(role, geomType, coordsJson, layerId)
    bridge.onFeatureEdited(role, geomType, coordsJson, layerId)
    bridge.onFeatureDeleted(role, layerId)
    bridge.onStationAttr(layerId, name, buffer)
    bridge.ready()
"""
import json
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from rivsat.app.state import state


class MapBridge(QObject):
    # role name after any change → let widgets refresh counts / status
    featuresChanged = pyqtSignal(str)
    mapReady        = pyqtSignal()

    def __init__(self):
        super().__init__()
        # track layerId → index for edit/delete reconciliation
        self._aoi_id        = None
        self._centerline_id = None
        self._transect_ids  = []   # ordered list of layerIds
        self._station_ids   = []   # ordered list of layerIds

    # ── JS → Python slots ──────────────────────────────────────────────────────
    @pyqtSlot()
    def ready(self):
        self.mapReady.emit()

    @pyqtSlot(str, str, str, str)
    def onFeatureDrawn(self, role, geom_type, coords_json, layer_id):
        coords = json.loads(coords_json)
        self._apply(role, coords, layer_id, edited=False)

    @pyqtSlot(str, str, str, str)
    def onFeatureEdited(self, role, geom_type, coords_json, layer_id):
        coords = json.loads(coords_json)
        self._apply(role, coords, layer_id, edited=True)

    @pyqtSlot(str, str)
    def onFeatureDeleted(self, role, layer_id):
        if role == "aoi":
            state.aoi_polygon = []
            self._aoi_id = None
        elif role == "centerline":
            state.centerline = []
            self._centerline_id = None
        elif role == "transects":
            if layer_id in self._transect_ids:
                idx = self._transect_ids.index(layer_id)
                self._transect_ids.pop(idx)
                tr = list(state.transects)
                if idx < len(tr):
                    tr.pop(idx)
                state.transects = tr
        elif role == "stations":
            if layer_id in self._station_ids:
                idx = self._station_ids.index(layer_id)
                self._station_ids.pop(idx)
                st = list(state.stations)
                if idx < len(st):
                    st.pop(idx)
                state.stations = st
        self.featuresChanged.emit(role)

    @pyqtSlot(str, str, int)
    def onStationAttr(self, layer_id, name, buffer):
        if layer_id in self._station_ids:
            idx = self._station_ids.index(layer_id)
            st = list(state.stations)
            if idx < len(st):
                st[idx] = {**st[idx], "name": name, "buffer_pixels": int(buffer)}
                state.stations = st
                self.featuresChanged.emit("stations")

    # ── internal ────────────────────────────────────────────────────────────────
    def _apply(self, role, coords, layer_id, edited):
        if role == "aoi":
            # coords: [[lon,lat],...] ring — ensure closed
            ring = [[float(x), float(y)] for x, y in coords]
            if ring and ring[0] != ring[-1]:
                ring.append(ring[0])
            state.aoi_polygon = ring
            self._aoi_id = layer_id

        elif role == "centerline":
            state.centerline = [(float(x), float(y)) for x, y in coords]
            self._centerline_id = layer_id

        elif role == "transects":
            line = [(float(x), float(y)) for x, y in coords]
            tr = list(state.transects)
            if edited and layer_id in self._transect_ids:
                tr[self._transect_ids.index(layer_id)] = line
            else:
                if layer_id not in self._transect_ids:
                    self._transect_ids.append(layer_id)
                    tr.append(line)
                else:
                    tr[self._transect_ids.index(layer_id)] = line
            state.transects = tr

        elif role == "stations":
            lon, lat = float(coords[0]), float(coords[1])
            st = list(state.stations)
            if edited and layer_id in self._station_ids:
                idx = self._station_ids.index(layer_id)
                st[idx] = {**st[idx], "coords": (lon, lat)}
            else:
                if layer_id not in self._station_ids:
                    self._station_ids.append(layer_id)
                    st.append({
                        "name": f"Station_{len(self._station_ids)}",
                        "coords": (lon, lat),
                        "buffer_pixels": 2,
                    })
                else:
                    idx = self._station_ids.index(layer_id)
                    st[idx] = {**st[idx], "coords": (lon, lat)}
            state.stations = st

        self.featuresChanged.emit(role)

    # ── reset (when loading fresh features from file) ──────────────────────────
    def reset_tracking(self):
        self._aoi_id = None
        self._centerline_id = None
        self._transect_ids = []
        self._station_ids = []
