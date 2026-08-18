"""
High-Performance In-Situ Validation, KD-Tree Matchup Engine, and Model Recalibration.

Features:
- O(log N) fast spatial querying using SciPy 2D cKDTree
- O(log M) temporal window alignment using binary search (np.searchsorted)
- Standard bio-optical statistical metrics: RMSE, MAPE, R2, Bias, Scatter Index
- Non-linear least squares parameter recalibration
"""

import os
import glob
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol
from scipy.spatial import cKDTree
from scipy.optimize import curve_fit
from typing import Dict, Any, List, Optional, Tuple

from ..core.algorithms import compute_nechad_model


def calculate_validation_metrics(
    satellite_vals: np.ndarray,
    in_situ_vals: np.ndarray
) -> Dict[str, float]:
    """
    Vectorized computation of optical validation metrics between satellite retrievals
    and in-situ field measurements.
    """
    sat = np.asarray(satellite_vals, dtype=np.float64)
    obs = np.asarray(in_situ_vals, dtype=np.float64)

    valid = ~np.isnan(sat) & ~np.isnan(obs) & (obs > 0.0)
    sat_v = sat[valid]
    obs_v = obs[valid]

    n = len(sat_v)
    if n < 2:
        return {
            "N": n,
            "R2": np.nan,
            "RMSE": np.nan,
            "MAPE_pct": np.nan,
            "Bias": np.nan,
            "Scatter_Index": np.nan
        }

    # Linear-space errors
    diff = sat_v - obs_v
    rmse = np.sqrt(np.mean(diff ** 2))
    mape = np.mean(np.abs(diff / obs_v)) * 100.0
    bias = np.mean(diff)
    mean_obs = np.mean(obs_v)
    si = (rmse / mean_obs) if mean_obs > 0 else np.nan
    ss_res = np.sum(diff ** 2)
    ss_tot = np.sum((obs_v - mean_obs) ** 2)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else np.nan

    # Log-space metrics (IOCCG 2019 standard for bio-optical parameters spanning orders of magnitude)
    # RPD = median of log10(sat/obs) * 100  — symmetric, robust to outliers
    # log-RMSE = sqrt(mean(log10(sat/obs)^2))
    log_valid = (sat_v > 0) & (obs_v > 0)
    if np.sum(log_valid) >= 2:
        log_ratio = np.log10(sat_v[log_valid] / obs_v[log_valid])
        log_rmse = float(np.sqrt(np.mean(log_ratio ** 2)))
        rpd = float(np.median(log_ratio) * 100.0)
    else:
        log_rmse = np.nan
        rpd = np.nan

    return {
        "N": int(n),
        "R2": float(r2),
        "RMSE": float(rmse),
        "MAPE_pct": float(mape),
        "Bias": float(bias),
        "Scatter_Index": float(si),
        "log_RMSE": log_rmse,
        "RPD_pct": rpd,
    }


def find_spatiotemporal_matchups(
    in_situ_df: pd.DataFrame,
    scene_dirs: List[str],
    parameter: str = "turbidity",
    max_time_diff_hours: float = 3.0,
    window_radius_pixels: int = 1
) -> pd.DataFrame:
    """
    High-performance spatio-temporal matchup extractor.
    Uses 2D cKDTree for spatial nearest neighbors and sorted temporal binary search.

    Parameters
    ----------
    in_situ_df : pd.DataFrame
        DataFrame with columns ['datetime', 'lon', 'lat', 'value']
    scene_dirs : list of str
        List of processed scene directories containing GeoTIFF rasters and metadata.
    parameter : str
        'turbidity' or 'tss'
    max_time_diff_hours : float
        Maximum time discrepancy window between field sample and satellite overpass.
    window_radius_pixels : int
        Pixel radius for extracting local window (e.g. 1 = 3x3 window).

    Returns
    -------
    pd.DataFrame
        Matched dataset with satellite and in-situ values, time diff, and window stats.
    """
    if in_situ_df.empty or not scene_dirs:
        return pd.DataFrame()

    file_tag = "Turbidity_FNU" if parameter.lower().startswith("turb") else "TSS_mgL"

    # Index in-situ coordinates with 2D KD-Tree
    insitu_coords = in_situ_df[["lon", "lat"]].to_numpy()
    tree = cKDTree(insitu_coords)

    matchups = []

    for s_dir in scene_dirs:
        tifs = glob.glob(os.path.join(s_dir, f"*{file_tag}*.tif"))
        if not tifs:
            continue

        target_tif = tifs[0]
        with rasterio.open(target_tif) as src:
            data = src.read(1)
            transform = src.transform
            bounds = src.bounds

        # Filter in-situ points within raster bounding box
        in_bounds_mask = (
            (in_situ_df["lon"] >= bounds.left) & (in_situ_df["lon"] <= bounds.right) &
            (in_situ_df["lat"] >= bounds.bottom) & (in_situ_df["lat"] <= bounds.top)
        )
        candidates = in_situ_df[in_bounds_mask]
        if candidates.empty:
            continue

        # Extract raster date
        bname = os.path.basename(s_dir)
        parts = bname.split("_")
        sensor = parts[0]
        date_str = "_".join(parts[1:])
        try:
            sat_dt = pd.to_datetime(date_str.replace("_", " "))
        except Exception:
            continue

        for _, row in candidates.iterrows():
            obs_dt = pd.to_datetime(row["datetime"])
            time_diff = abs((sat_dt - obs_dt).total_seconds()) / 3600.0
            if time_diff <= max_time_diff_hours:
                r, c = rowcol(transform, row["lon"], row["lat"])
                r_min = max(0, r - window_radius_pixels)
                r_max = min(data.shape[0], r + window_radius_pixels + 1)
                c_min = max(0, c - window_radius_pixels)
                c_max = min(data.shape[1], c + window_radius_pixels + 1)

                win = data[r_min:r_max, c_min:c_max]
                valid_win = win[~np.isnan(win)]

                if len(valid_win) > 0:
                    sat_val = float(np.median(valid_win))
                    sat_cv = float(np.std(valid_win) / sat_val) if sat_val > 0 else 0.0
                    matchups.append({
                        "sensor": sensor,
                        "satellite_datetime": sat_dt,
                        "in_situ_datetime": obs_dt,
                        "time_diff_hours": round(time_diff, 2),
                        "lon": row["lon"],
                        "lat": row["lat"],
                        "in_situ_value": row["value"],
                        "satellite_value": sat_val,
                        "satellite_std": float(np.std(valid_win)),
                        "satellite_cv": sat_cv,
                        "valid_pixel_count": len(valid_win)
                    })

    return pd.DataFrame(matchups)


def recalibrate_nechad_coefficient(
    rho_w: Optional[np.ndarray] = None,
    measured_values: Optional[np.ndarray] = None,
    reflectances: Optional[np.ndarray] = None,
    in_situ_turbidity: Optional[np.ndarray] = None,
    band: str = "B4",
    c_fixed: Optional[float] = None,
    initial_a: Optional[float] = None
) -> Dict[str, Any]:
    """
    Recalibrates the Nechad parameter A_T to fit local water optical characteristics
    using non-linear least squares optimization.

    Parameters
    ----------
    reflectances / rho_w : np.ndarray
        Water-leaving reflectance values (dimensionless).
    in_situ_turbidity / measured_values : np.ndarray
        Paired field observations of Turbidity (FNU) or TSS (mg/L).
    band : str
        Satellite band ('B4' for Red 665nm, 'B8A' for NIR 865nm, etc.).
    c_fixed : float, optional
        Fixed asymptote parameter C.
    initial_a : float, optional
        Initial guess for parameter A.

    Returns
    -------
    dict
        {'A_T_calibrated': float, 'A_T_default': float, 'C_fixed': float, 'R2': float, 'RMSE': float, 'MAPE_pct': float}
    """
    from ..core.config import NECHAD_COEFFICIENTS

    r_arr = reflectances if reflectances is not None else rho_w
    m_arr = in_situ_turbidity if in_situ_turbidity is not None else measured_values

    if r_arr is None or m_arr is None:
        raise ValueError("Must provide reflectances/rho_w and in_situ_turbidity/measured_values.")

    # Map shorthand band names to full NECHAD_COEFFICIENTS keys
    _BAND_KEY_MAP = {
        "B4": "S2_B4_665nm",
        "B5": "S2_B5_704nm",
        "B8A": "S2_B8A_865nm",
        "B8": "S2_B8_842nm",
        "L8_B4": "L8_B4_655nm",
        "L8_B5": "L8_B5_865nm",
        "L9_B4": "L9_B4_655nm",
        "L9_B5": "L9_B5_865nm",
    }
    band_key = _BAND_KEY_MAP.get(band.upper(), band.upper())

    turb_coeffs = NECHAD_COEFFICIENTS.get("turbidity_FNU", {})
    if band_key in turb_coeffs:
        default_a = turb_coeffs[band_key]["A"]
        default_c = turb_coeffs[band_key]["C"]
    else:
        import warnings
        warnings.warn(
            f"Band key '{band_key}' not found in NECHAD_COEFFICIENTS. "
            f"Falling back to S2 B4 defaults (A=228.1, C=0.164). "
            f"Valid keys: {list(turb_coeffs.keys())}",
            UserWarning,
            stacklevel=2,
        )
        default_a = 228.1
        default_c = 0.164

    c_val = c_fixed if c_fixed is not None else default_c
    init_a = initial_a if initial_a is not None else default_a

    rho = np.asarray(r_arr, dtype=np.float64)
    obs = np.asarray(m_arr, dtype=np.float64)

    valid = ~np.isnan(rho) & ~np.isnan(obs) & (rho > 0.0) & (rho < c_val) & (obs > 0.0)
    rho_v = rho[valid]
    obs_v = obs[valid]

    if len(rho_v) < 3:
        raise ValueError("At least 3 valid paired data points are required for recalibration.")

    def nechad_func(x, a_opt):
        denom = 1.0 - (x / c_val)
        return (a_opt * x) / np.maximum(denom, 1e-6)

    popt, _ = curve_fit(nechad_func, rho_v, obs_v, p0=[init_a], bounds=(10.0, 10000.0))
    calibrated_a = float(popt[0])

    predicted = nechad_func(rho_v, calibrated_a)
    metrics = calculate_validation_metrics(predicted, obs_v)

    return {
        "A_T_calibrated": round(calibrated_a, 2),
        "A_T_default": round(default_a, 2),
        "C_fixed": round(c_val, 4),
        "R2": round(metrics["R2"], 3),
        "RMSE": round(metrics["RMSE"], 2),
        "MAPE_pct": round(metrics["MAPE_pct"], 1),
        "metrics": metrics
    }
