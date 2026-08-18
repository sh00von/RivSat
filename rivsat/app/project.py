"""
RivSat project persistence — .rivsat JSON format.

ProjectManager handles:
  - save / open / Save As
  - reconstruct_results() — reads GeoTIFFs back into processed_results arrays
  - dirty flag + autosave (QTimer-driven, ~5 min)
  - recent projects list (QSettings)
"""
import json
import os
from pathlib import Path
from typing import Optional

import numpy as np
from PyQt6.QtCore import QSettings, QTimer, QObject, pyqtSignal

from rivsat.app.state import state

_VERSION = 1
_AUTOSAVE_INTERVAL_MS = 5 * 60 * 1000  # 5 minutes
_RECENT_MAX = 8

# Fallback autosave path when no project has been saved yet
def _default_autosave_path() -> Path:
    p = Path.home() / ".rivsat"
    p.mkdir(exist_ok=True)
    return p / "autosave.rivsat.autosave"

# Map processor result keys → stats["files"] keys
_KEY_TO_FILE_KEY = {
    "turbidity":    "turbidity_geotiff",
    "tss":          "tss_geotiff",
    "chlorophyll":  "chlorophyll_geotiff",
    "cdom":         "cdom_geotiff",
    "salinity":     "salinity_geotiff",
    "secchi_depth": "secchi_geotiff",
    "water_mask":   "water_mask_geotiff",
}


def _serialize_profile(profile: dict) -> dict:
    """Convert rasterio profile to JSON-serializable dict."""
    crs = profile.get("crs")
    crs_str = crs.to_wkt() if crs is not None else None
    transform = profile.get("transform")
    transform_list = list(transform)[:6] if transform is not None else None
    return {
        "crs": crs_str,
        "transform": transform_list,
        "width": profile.get("width"),
        "height": profile.get("height"),
        "nodata": profile.get("nodata"),
    }


def _deserialize_profile(d: dict) -> dict:
    from rasterio.crs import CRS
    from rasterio.transform import Affine
    profile: dict = {}
    if d.get("crs"):
        try:
            profile["crs"] = CRS.from_wkt(d["crs"])
        except Exception:
            try:
                profile["crs"] = CRS.from_string(d["crs"])
            except Exception:
                profile["crs"] = None
    if d.get("transform"):
        profile["transform"] = Affine(*d["transform"])
    profile["width"]  = d.get("width")
    profile["height"] = d.get("height")
    profile["nodata"] = d.get("nodata")
    return profile


def _make_relative(path: str, base: str) -> str:
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return path  # different drive on Windows


def _resolve(path: str, base: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(base, path))


class ProjectManager(QObject):
    dirtied = pyqtSignal()        # emitted when dirty state changes to True
    saved   = pyqtSignal(str)     # emitted with path after a successful save
    opened  = pyqtSignal(str)     # emitted with path after a successful open

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_path: Optional[str] = None
        self._dirty = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(_AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start()

    # ── Dirty tracking ─────────────────────────────────────────────────────────
    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self.dirtied.emit()

    def _clear_dirty(self):
        self._dirty = False

    # ── Serialization ──────────────────────────────────────────────────────────
    def _build_doc(self, base_dir: str) -> dict:
        scenes = []
        for res in state.processed_results:
            s = res.get("stats", {})
            files = s.get("files", {})
            rel_files = {k: _make_relative(v, base_dir) for k, v in files.items()}
            scenes.append({
                "stats":   {k: v for k, v in s.items() if k != "files"},
                "files":   rel_files,
                "profile": _serialize_profile(res.get("profile", {})),
            })

        rel_scene_dirs = [_make_relative(d, base_dir) for d in state.scene_dirs]

        return {
            "rivsat_version": _VERSION,
            "site_name":      state.site_name,
            "start_date":     state.start_date,
            "end_date":       state.end_date,
            "sensors":        state.sensors,
            "max_cloud_cover": state.max_cloud_cover,
            "acq_mode":       state.acq_mode,
            "gee_project_id": state.gee_project_id,
            "data_dir":       _make_relative(state.data_dir, base_dir),
            "output_dir":     _make_relative(state.output_dir, base_dir),
            "aoi_polygon":    state.aoi_polygon,
            "centerline":     [list(p) for p in state.centerline],
            "transects":      [[list(p) for p in t] for t in state.transects],
            "stations":       state.stations,
            "scene_dirs":     rel_scene_dirs,
            "scenes":         scenes,
        }

    def _apply_doc(self, doc: dict, base_dir: str):
        state.site_name       = doc.get("site_name", state.site_name)
        state.start_date      = doc.get("start_date", state.start_date)
        state.end_date        = doc.get("end_date", state.end_date)
        state.sensors         = doc.get("sensors", state.sensors)
        state.max_cloud_cover = doc.get("max_cloud_cover", state.max_cloud_cover)
        state.acq_mode        = doc.get("acq_mode", state.acq_mode)
        state.gee_project_id  = doc.get("gee_project_id", state.gee_project_id)
        state.data_dir        = _resolve(doc.get("data_dir", state.data_dir), base_dir)
        state.output_dir      = _resolve(doc.get("output_dir", state.output_dir), base_dir)
        state.aoi_polygon     = doc.get("aoi_polygon", [])
        state.centerline      = [tuple(p) for p in doc.get("centerline", [])]
        state.transects       = [[tuple(p) for p in t] for t in doc.get("transects", [])]
        state.stations        = doc.get("stations", [])
        state.scene_dirs      = [_resolve(d, base_dir) for d in doc.get("scene_dirs", [])]
        state.project_path    = self.project_path

    # ── Public API ─────────────────────────────────────────────────────────────
    def save(self, path: Optional[str] = None) -> bool:
        target = path or self.project_path
        if not target:
            return False
        base = os.path.dirname(os.path.abspath(target))
        doc = self._build_doc(base)
        try:
            with open(target, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2)
        except OSError as exc:
            raise RuntimeError(f"Save failed: {exc}") from exc
        self.project_path = target
        state.project_path = target
        self._clear_dirty()
        self._add_recent(target)
        self.saved.emit(target)
        return True

    def open(self, path: str) -> list[str]:
        """Parse project file, apply state, return list of missing file warnings."""
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        base = os.path.dirname(os.path.abspath(path))
        self.project_path = path
        self._apply_doc(doc, base)
        self._clear_dirty()
        self._add_recent(path)

        # Check missing files
        warnings = []
        for entry in doc.get("scenes", []):
            for k, rel in entry.get("files", {}).items():
                abs_p = _resolve(rel, base)
                if not os.path.exists(abs_p):
                    warnings.append(f"Missing: {abs_p}")

        self.opened.emit(path)
        return warnings

    def reconstruct_results(self) -> list:
        """
        Read GeoTIFFs for every saved scene back into processed_results format.
        Returns the reconstructed list (also sets state.processed_results).
        """
        import rasterio
        if not self.project_path:
            return []
        base = os.path.dirname(os.path.abspath(self.project_path))

        with open(self.project_path, encoding="utf-8") as f:
            doc = json.load(f)

        results = []
        for entry in doc.get("scenes", []):
            files   = {k: _resolve(v, base) for k, v in entry.get("files", {}).items()}
            profile = _deserialize_profile(entry.get("profile", {}))
            stats   = dict(entry.get("stats", {}))
            stats["files"] = files

            result = {"stats": stats, "profile": profile}

            for key, file_key in _KEY_TO_FILE_KEY.items():
                tif = files.get(file_key)
                if tif and os.path.exists(tif):
                    try:
                        with rasterio.open(tif) as src:
                            arr = src.read(1).astype(np.float32)
                            if src.nodata is not None:
                                arr[arr == src.nodata] = np.nan
                    except Exception:
                        arr = None
                else:
                    arr = None
                result[key] = arr

            results.append(result)

        state.processed_results = results
        return results

    def new_project(self):
        """Reset state to defaults for a new project."""
        from rivsat.app.state import AppState
        defaults = AppState()
        for name in defaults.param:
            if name == "name":
                continue
            try:
                setattr(state, name, getattr(defaults, name))
            except Exception:
                pass
        self.project_path = None
        state.project_path = ""
        self._clear_dirty()

    # ── Autosave ───────────────────────────────────────────────────────────────
    def _autosave(self):
        if not self._dirty:
            return
        if self.project_path:
            path = self.project_path + ".autosave"
        else:
            path = str(_default_autosave_path())
        base = os.path.dirname(os.path.abspath(path))
        try:
            doc = self._build_doc(base)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def autosave_path_for(project_path: Optional[str]) -> Path:
        if project_path:
            return Path(project_path + ".autosave")
        return _default_autosave_path()

    @staticmethod
    def check_autosave(project_path: Optional[str]) -> Optional[str]:
        """Return autosave path if it's newer than the project file, else None."""
        as_path = ProjectManager.autosave_path_for(project_path)
        if not as_path.exists():
            return None
        if project_path and os.path.exists(project_path):
            if as_path.stat().st_mtime <= os.path.getmtime(project_path):
                return None
        return str(as_path)

    @staticmethod
    def discard_autosave(project_path: Optional[str]):
        as_path = ProjectManager.autosave_path_for(project_path)
        try:
            as_path.unlink(missing_ok=True)
        except Exception:
            pass

    # ── Recent projects ────────────────────────────────────────────────────────
    @staticmethod
    def _settings() -> QSettings:
        return QSettings("RivSat", "RivSat")

    @staticmethod
    def recent_projects() -> list[str]:
        s = ProjectManager._settings()
        return s.value("recent_projects", [], type=list)

    @staticmethod
    def _add_recent(path: str):
        s = ProjectManager._settings()
        recent = ProjectManager.recent_projects()
        path = os.path.abspath(path)
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        s.setValue("recent_projects", recent[:_RECENT_MAX])
