"""
Shared mutable state passed between all tabs.
All tabs import this module and read/write the same object.
"""
import param


class AppState(param.Parameterized):
    # ── Site configuration ────────────────────────────────────────────
    site_name       = param.String(default="My_River_Site")
    start_date      = param.String(default="2023-01-01")
    end_date        = param.String(default="2023-12-31")
    sensors         = param.List(default=["S2", "L8"])
    max_cloud_cover = param.Number(default=20.0, bounds=(0, 100))
    acq_mode        = param.ObjectSelector(
        default="seasonal",
        objects=["annual", "seasonal", "monthly", "daily_overpass"]
    )
    gee_project_id  = param.String(default="")

    # ── Spatial layers (populated by the Map workspace) ───────────────
    aoi_polygon  = param.List(default=[])     # [[lon, lat], ...]
    centerline   = param.List(default=[])     # [(lon, lat), ...]
    transects    = param.List(default=[])     # [ [(lon, lat), ...], ... ] user-drawn transect lines
    stations     = param.List(default=[])     # [{"name", "coords": (lon, lat), "buffer_pixels"}]

    # Currently active drawing role: 'aoi' | 'centerline' | 'transects' | 'stations'
    active_layer = param.String(default="aoi")

    # ── Processing results (populated by Process tab) ─────────────────
    scene_dirs        = param.List(default=[])
    processed_results = param.List(default=[])

    # Map result overlays: {param_key: {"png": path, "bounds": [[s,w],[n,e]],
    #                                    "opacity": float, "visible": bool, "label": str}}
    overlays = param.Dict(default={})

    # ── GEE initialised flag ──────────────────────────────────────────
    gee_ready = param.Boolean(default=False)

    # ── Data directories ──────────────────────────────────────────────
    data_dir   = param.String(default="./data")
    output_dir = param.String(default="./outputs")

    # ── Project file path (empty = unsaved) ───────────────────────────
    project_path = param.String(default="")


# Singleton — import and use this everywhere
state = AppState()
