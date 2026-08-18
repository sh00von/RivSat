"""
Result raster → georeferenced RGBA PNG for Leaflet image overlays.

Given a processed water-quality array and its rasterio profile, produce:
  - a colourised PNG with transparent nodata, and
  - WGS84 bounds [[south, west], [north, east]] for L.imageOverlay.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import cmocean
    _CMAPS = {
        "turbidity": cmocean.cm.turbid, "tss": cmocean.cm.matter,
        "chlorophyll": cmocean.cm.algae, "cdom": cmocean.cm.dense,
        "salinity": cmocean.cm.haline, "secchi_depth": cmocean.cm.ice,
    }
except ImportError:
    _CMAPS = {
        "turbidity": "turbo", "tss": "YlOrRd", "chlorophyll": "YlGn",
        "cdom": "Blues", "salinity": "YlGnBu", "secchi_depth": "Greys_r",
    }

_HARD_MAX = {
    "turbidity": 500, "tss": 600, "chlorophyll": 150,
    "cdom": 10, "salinity": 35, "secchi_depth": None,
}

_LABELS = {
    "turbidity": "Turbidity", "tss": "TSS", "chlorophyll": "Chlorophyll-a",
    "cdom": "CDOM", "salinity": "Salinity", "secchi_depth": "Secchi Depth",
}


def _vmax(arr, hard):
    v = float(np.nanpercentile(arr, 95))
    if hard is not None:
        return min(v * 1.1, hard) if v > 0 else hard
    return max(v * 1.1, 0.1)


def colorize_to_png(arr, key, out_path):
    """Write a transparent-nodata RGBA PNG for one WQ parameter. Returns out_path."""
    cmap = _CMAPS.get(key, "viridis")
    cmap_obj = plt.get_cmap(cmap) if isinstance(cmap, str) else cmap

    vmax = _vmax(arr, _HARD_MAX.get(key))
    norm = np.clip(np.nan_to_num(arr, nan=0.0) / max(vmax, 1e-9), 0.0, 1.0)
    rgba = cmap_obj(norm)                      # (H, W, 4) float 0..1
    rgba[np.isnan(arr), 3] = 0.0               # transparent where nodata
    rgba[~np.isnan(arr), 3] = 1.0

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.imsave(out_path, rgba)
    return out_path


def raster_bounds_wgs84(profile):
    """Return [[south, west], [north, east]] in EPSG:4326 from a rasterio profile."""
    from rasterio.transform import array_bounds
    from rasterio.warp import transform_bounds

    transform = profile["transform"]
    width  = profile["width"]
    height = profile["height"]
    crs    = profile.get("crs")

    left, bottom, right, top = array_bounds(height, width, transform)
    if crs is not None and str(crs).upper() not in ("EPSG:4326", "OGC:CRS84"):
        left, bottom, right, top = transform_bounds(crs, "EPSG:4326",
                                                     left, bottom, right, top)
    return [[float(bottom), float(left)], [float(top), float(right)]]


def build_overlays(result, output_dir, keys=None):
    """
    For a single processed-scene result dict, build overlay PNGs + bounds.

    Returns dict: key -> {"png": path, "bounds": [[s,w],[n,e]], "label": str}
    """
    keys = keys or ["turbidity", "chlorophyll", "tss", "cdom", "salinity", "secchi_depth"]
    profile = result.get("profile")
    if profile is None:
        return {}
    try:
        bounds = raster_bounds_wgs84(profile)
    except Exception:
        return {}

    ov_dir = os.path.join(output_dir, "overlays")
    out = {}
    for key in keys:
        arr = result.get(key)
        if arr is None or np.all(np.isnan(arr)):
            continue
        png = os.path.join(ov_dir, f"{key}_overlay.png")
        try:
            colorize_to_png(arr, key, png)
            out[key] = {"png": png, "bounds": bounds, "label": _LABELS.get(key, key)}
        except Exception:
            continue
    return out
