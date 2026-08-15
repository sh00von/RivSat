"""
High-Performance Vectorized Spatial Analytics for Rivers and Estuaries.

Features:
- Vectorized arc-length interpolation on river centerlines using binary search (np.searchsorted)
- Simultaneous batch affine coordinate transformations
- Fast spatial window extractions and percentile calculations
"""

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol
from typing import List, Dict, Any, Tuple, Optional


def extract_station_data(
    raster_data: np.ndarray,
    transform: rasterio.Affine,
    stations: List[Dict[str, Any]],
    buffer_pixels: int = 1
) -> List[Dict[str, Any]]:
    """
    Vectorized extraction of spatial statistics for virtual monitoring stations.
    """
    height, width = raster_data.shape
    if not stations:
        return []

    # Vectorized coordinate extraction
    lons = np.array([st["coords"][0] for st in stations], dtype=np.float64)
    lats = np.array([st["coords"][1] for st in stations], dtype=np.float64)
    names = [st.get("name", f"Station_{i+1}") for i, st in enumerate(stations)]
    radii = [st.get("buffer_pixels", buffer_pixels) for st in stations]

    # Batch compute pixel row, col via affine inverse
    inv_transform = ~transform
    cols, rows = inv_transform * (lons, lats)
    rows = np.round(rows).astype(np.int32)
    cols = np.round(cols).astype(np.int32)

    results = []
    for i in range(len(stations)):
        r = rows[i]
        c = cols[i]
        rad = radii[i]

        r_min = max(0, r - rad)
        r_max = min(height, r + rad + 1)
        c_min = max(0, c - rad)
        c_max = min(width, c + rad + 1)

        if r_max > r_min and c_max > c_min:
            window = raster_data[r_min:r_max, c_min:c_max]
            valid_vals = window[~np.isnan(window)]
        else:
            valid_vals = np.array([], dtype=np.float32)

        # Adaptive spatial expansion fallback: if station pin hits land/cloud mask, search nearby water pixels
        if len(valid_vals) == 0:
            for extra in [1, 2, 3]:
                search_rad = rad + extra * 2
                sr_min = max(0, r - search_rad)
                sr_max = min(height, r + search_rad + 1)
                sc_min = max(0, c - search_rad)
                sc_max = min(width, c + search_rad + 1)
                if sr_max > sr_min and sc_max > sc_min:
                    win_sub = raster_data[sr_min:sr_max, sc_min:sc_max]
                    valid_vals = win_sub[~np.isnan(win_sub)]
                    if len(valid_vals) > 0:
                        break

        if len(valid_vals) > 0:
            stats = {
                "station_name": names[i],
                "lon": float(lons[i]),
                "lat": float(lats[i]),
                "pixel_row": int(r),
                "pixel_col": int(c),
                "valid_pixels": int(len(valid_vals)),
                "mean": float(np.mean(valid_vals)),
                "median": float(np.median(valid_vals)),
                "std": float(np.std(valid_vals)),
                "min": float(np.min(valid_vals)),
                "max": float(np.max(valid_vals)),
                "p10": float(np.percentile(valid_vals, 10)),
                "p90": float(np.percentile(valid_vals, 90)),
            }
        else:
            stats = {
                "station_name": names[i],
                "lon": float(lons[i]),
                "lat": float(lats[i]),
                "pixel_row": int(r),
                "pixel_col": int(c),
                "valid_pixels": 0,
                "mean": np.nan,
                "median": np.nan,
                "std": np.nan,
                "min": np.nan,
                "max": np.nan,
                "p10": np.nan,
                "p90": np.nan,
            }
        results.append(stats)

    return results


def extract_longitudinal_profile(
    raster_data: np.ndarray,
    transform: rasterio.Affine,
    centerline_coords: List[Tuple[float, float]],
    num_samples: int = 100,
    sampling_radius_pixels: int = 1
) -> pd.DataFrame:
    """
    Vectorized extraction of longitudinal centerline profile using binary search
    along the piecewise linear arc-length curve.

    Complexity: O(M + N log M) where M is vertex count and N is sample count.
    """
    pts = np.asarray(centerline_coords, dtype=np.float64)
    if len(pts) < 2:
        raise ValueError("River centerline must contain at least 2 coordinate points.")

    # 1. Vectorized calculation of segment lengths & cumulative arc-lengths
    dx = np.diff(pts[:, 0])
    dy = np.diff(pts[:, 1])
    seg_lengths = np.hypot(dx, dy)
    cum_dist = np.concatenate(([0.0], np.cumsum(seg_lengths)))
    total_len = cum_dist[-1]

    # Geodesic metric scale factor approximation (deg -> km)
    mid_lat = np.mean(pts[:, 1])
    km_per_deg_lat = 110.574
    km_per_deg_lon = 111.320 * np.cos(np.radians(mid_lat))
    avg_scale = np.sqrt((km_per_deg_lat**2 + km_per_deg_lon**2) / 2.0)
    total_km = total_len * avg_scale

    # 2. Generate N target equidistant distance points
    target_dists = np.linspace(0.0, total_len, num_samples)
    target_km = (target_dists / total_len) * total_km

    # 3. Binary search (np.searchsorted) to find enclosing segment index for each point in O(log M)
    seg_idx = np.searchsorted(cum_dist, target_dists, side='right') - 1
    seg_idx = np.clip(seg_idx, 0, len(seg_lengths) - 1)

    # 4. Parametric interpolation parameter t in [0, 1]
    denom = np.where(seg_lengths[seg_idx] == 0, 1.0, seg_lengths[seg_idx])
    t = (target_dists - cum_dist[seg_idx]) / denom
    t = np.clip(t, 0.0, 1.0)

    # 5. Interpolated coordinates
    interp_x = pts[seg_idx, 0] + t * dx[seg_idx]
    interp_y = pts[seg_idx, 1] + t * dy[seg_idx]

    # 6. Batch affine transformation to pixel rows and columns
    inv_transform = ~transform
    sample_cols, sample_rows = inv_transform * (interp_x, interp_y)
    sample_rows = np.round(sample_rows).astype(np.int32)
    sample_cols = np.round(sample_cols).astype(np.int32)

    height, width = raster_data.shape
    values = np.full(num_samples, np.nan, dtype=np.float32)
    stds = np.full(num_samples, np.nan, dtype=np.float32)

    # 7. Fast local window extraction
    rad = sampling_radius_pixels
    for i in range(num_samples):
        r, c = sample_rows[i], sample_cols[i]
        r_min = max(0, r - rad)
        r_max = min(height, r + rad + 1)
        c_min = max(0, c - rad)
        c_max = min(width, c + rad + 1)

        if r_max > r_min and c_max > c_min:
            win = raster_data[r_min:r_max, c_min:c_max]
            v = win[~np.isnan(win)]
            if len(v) > 0:
                values[i] = float(np.median(v))
                stds[i] = float(np.std(v))

    df = pd.DataFrame({
        "distance_km": target_km,
        "lon": interp_x,
        "lat": interp_y,
        "pixel_row": sample_rows,
        "pixel_col": sample_cols,
        "value": values,
        "std": stds
    })
    return df


def extract_cross_transects(
    raster_data: np.ndarray,
    transform: rasterio.Affine,
    centerline_coords: List[Tuple[float, float]],
    num_transects: int = 5,
    transect_length_m: float = 1000.0,
    samples_per_transect: int = 40
) -> pd.DataFrame:
    """
    Extracts CoastSat-style perpendicular cross-river transect profiles
    to analyze lateral sediment plume diffusion and channel-width dynamics.

    Parameters
    ----------
    raster_data : np.ndarray
        2D raster array (Turbidity or TSS).
    transform : rasterio.Affine
        Affine georeferencing transform.
    centerline_coords : list of (lon, lat)
        River centerline polyline.
    num_transects : int
        Number of perpendicular transects along the river length.
    transect_length_m : float
        Total cross-river width to sample in meters (e.g. 4000m).
    samples_per_transect : int
        Number of sample points across each transect.

    Returns
    -------
    pd.DataFrame
        DataFrame containing cross-sectional profiles with columns:
        ['transect_id', 'chainage_km', 'cross_dist_m', 'lon', 'lat', 'value']
    """
    pts = np.asarray(centerline_coords, dtype=np.float64)
    if len(pts) < 2:
        raise ValueError("Centerline must have at least 2 points.")

    dx = np.diff(pts[:, 0])
    dy = np.diff(pts[:, 1])
    seg_lens = np.hypot(dx, dy)
    cum_dist = np.concatenate(([0.0], np.cumsum(seg_lens)))
    total_len = cum_dist[-1]

    mid_lat = np.mean(pts[:, 1])
    m_per_deg_lat = 110574.0
    m_per_deg_lon = 111320.0 * np.cos(np.radians(mid_lat))
    avg_scale_m = np.sqrt((m_per_deg_lat**2 + m_per_deg_lon**2) / 2.0)
    total_km = (total_len * avg_scale_m) / 1000.0

    # Anchor locations along centerline
    anchor_dists = np.linspace(total_len * 0.1, total_len * 0.9, num_transects)
    anchor_kms = (anchor_dists / total_len) * total_km

    seg_idx = np.searchsorted(cum_dist, anchor_dists, side='right') - 1
    seg_idx = np.clip(seg_idx, 0, len(seg_lens) - 1)

    denom = np.where(seg_lens[seg_idx] == 0, 1.0, seg_lens[seg_idx])
    t = np.clip((anchor_dists - cum_dist[seg_idx]) / denom, 0.0, 1.0)

    anchor_x = pts[seg_idx, 0] + t * dx[seg_idx]
    anchor_y = pts[seg_idx, 1] + t * dy[seg_idx]

    # Tangent and Normal unit vectors (in meters space)
    tx = dx[seg_idx] * m_per_deg_lon
    ty = dy[seg_idx] * m_per_deg_lat
    t_mag = np.hypot(tx, ty)
    t_mag = np.where(t_mag == 0, 1.0, t_mag)
    
    # Perpendicular unit normal vector
    nx = -ty / t_mag
    ny = tx / t_mag

    # Lateral offsets in meters from -L/2 to +L/2
    offsets_m = np.linspace(-transect_length_m / 2.0, transect_length_m / 2.0, samples_per_transect)
    
    inv_transform = ~transform
    height, width = raster_data.shape

    records = []
    for k in range(num_transects):
        t_id = f"T{k+1}"
        cx, cy = anchor_x[k], anchor_y[k]
        norm_x, norm_y = nx[k], ny[k]
        ch_km = anchor_kms[k]

        # Points along this perpendicular line in degrees
        px_deg = cx + (offsets_m * norm_x) / m_per_deg_lon
        py_deg = cy + (offsets_m * norm_y) / m_per_deg_lat

        cols, rows = inv_transform * (px_deg, py_deg)
        cols = np.round(cols).astype(np.int32)
        rows = np.round(rows).astype(np.int32)

        for s in range(samples_per_transect):
            r, c = rows[s], cols[s]
            if 0 <= r < height and 0 <= c < width:
                val = float(raster_data[r, c])
            else:
                val = np.nan

            records.append({
                "transect_id": t_id,
                "chainage_km": round(ch_km, 2),
                "cross_dist_m": round(offsets_m[s], 1),
                "lon": float(px_deg[s]),
                "lat": float(py_deg[s]),
                "value": val
            })

    return pd.DataFrame(records)
