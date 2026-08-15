"""
Core bio-optical radiative transfer algorithms for satellite water quality estimation.

Includes:
- Nechad et al. (2010/2016) semi-analytical single-band models
- Dogliotti et al. (2015) dual-band blended switching framework
- Multi-conditional Red-Edge (704 nm) extreme plume extension
- Cross-sensor Spectral Band Adjustment Factors (SBAFs)
- Water index extraction (NDWI, MNDWI)
"""

import numpy as np
from typing import Optional, Dict, Tuple, Union
from .config import (
    NECHAD_COEFFICIENTS,
    DOGLIOTTI_THRESHOLDS,
    REDEDGE_THRESHOLDS,
    SBAF_FACTORS
)


def compute_nechad_model(
    rho_w: np.ndarray,
    a_param: float,
    c_param: float
) -> np.ndarray:
    """
    Computes bio-optical parameter (Turbidity in FNU or TSS in mg/L) using the
    Nechad et al. semi-analytical formulation:
    
        Value = (A * rho_w) / (1 - rho_w / C)

    Parameters
    ----------
    rho_w : np.ndarray
        Water-leaving reflectance (dimensionless, rho_w = pi * Rrs).
    a_param : float
        Dimensional calibration coefficient (FNU or mg/L).
    c_param : float
        Dimensionless asymptotic saturation limit.

    Returns
    -------
    np.ndarray
        Calculated turbidity or TSS array.
    """
    rho = np.asarray(rho_w, dtype=np.float32)
    denominator = 1.0 - (rho / float(c_param))
    
    # Avoid zero division and unphysical negative denominators near saturation
    with np.errstate(divide='ignore', invalid='ignore'):
        result = (float(a_param) * rho) / denominator
        # Filter negative or asymptote overshoot
        result = np.where((denominator <= 0.0) | (rho < 0.0) | (result < 0.0), np.nan, result)
        
    return result.astype(np.float32)


def compute_dogliotti_blended(
    rho_red: np.ndarray,
    rho_nir: np.ndarray,
    parameter: str = "turbidity",
    sensor: str = "S2",
    custom_coeffs: Optional[Dict[str, Dict[str, float]]] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Executes the Dogliotti et al. (2015) dual-band blended switching algorithm.
    
    Dynamically blends Red and NIR single-band Nechad models based on Red band
    water-leaving reflectance (rho_w):
    - rho_w(Red) <= 0.05: Uses 100% Red model (maximizes sensitivity in clear/moderate waters)
    - rho_w(Red) >= 0.07: Uses 100% NIR model (prevents red-band saturation in turbid waters)
    - 0.05 < rho_w(Red) < 0.07: Linear continuous blending: W * NIR + (1 - W) * Red

    Parameters
    ----------
    rho_red : np.ndarray
        Red band water-leaving reflectance (~655-665 nm).
    rho_nir : np.ndarray
        NIR band water-leaving reflectance (~865 nm).
    parameter : str
        Target parameter: 'turbidity' (FNU) or 'tss' (mg/L).
    sensor : str
        Sensor identifier: 'S2' (Sentinel-2 MSI), 'L8' (Landsat 8), 'L9' (Landsat 9).
    custom_coeffs : dict, optional
        Custom calibration dictionary with 'red': {'A': float, 'C': float}
        and 'nir': {'A': float, 'C': float}.

    Returns
    -------
    tuple of (np.ndarray, np.ndarray)
        - Blended output array (Turbidity in FNU or TSS in mg/L)
        - Blending weight matrix W (0.0 = pure Red, 1.0 = pure NIR)
    """
    rho_r = np.asarray(rho_red, dtype=np.float32)
    rho_n = np.asarray(rho_nir, dtype=np.float32)

    # Determine coefficient keys
    param_key = "turbidity_FNU" if parameter.lower() in ["turbidity", "fnu", "ntu"] else "tss_mg_L"
    
    if custom_coeffs is not None:
        red_a, red_c = custom_coeffs["red"]["A"], custom_coeffs["red"]["C"]
        nir_a, nir_c = custom_coeffs["nir"]["A"], custom_coeffs["nir"]["C"]
    else:
        sensor_prefix = "S2" if sensor.upper().startswith("S2") else "L8"
        red_band_key = f"{sensor_prefix}_B4_665nm" if sensor_prefix == "S2" else "L8_B4_655nm"
        nir_band_key = f"{sensor_prefix}_B8A_865nm" if sensor_prefix == "S2" else "L8_B5_865nm"

        red_a = NECHAD_COEFFICIENTS[param_key][red_band_key]["A"]
        red_c = NECHAD_COEFFICIENTS[param_key][red_band_key]["C"]
        nir_a = NECHAD_COEFFICIENTS[param_key][nir_band_key]["A"]
        nir_c = NECHAD_COEFFICIENTS[param_key][nir_band_key]["C"]

    # Compute single-band estimates
    val_red = compute_nechad_model(rho_r, red_a, red_c)
    val_nir = compute_nechad_model(rho_n, nir_a, nir_c)

    # Dogliotti blending function boundaries
    bound_low = DOGLIOTTI_THRESHOLDS["rho_w_low"]
    bound_high = DOGLIOTTI_THRESHOLDS["rho_w_high"]

    # Calculate weight matrix W
    with np.errstate(divide='ignore', invalid='ignore'):
        weight = (rho_r - bound_low) / (bound_high - bound_low)
        weight = np.clip(weight, 0.0, 1.0)
        # In case rho_r is NaN, weight is NaN
        weight = np.where(np.isnan(rho_r), np.nan, weight)

    # Linearly blend estimates
    blended = (1.0 - weight) * val_red + weight * val_nir
    
    # Fallback to single band if one is valid and other is NaN
    blended = np.where(np.isnan(blended) & ~np.isnan(val_red) & (rho_r <= bound_low), val_red, blended)
    blended = np.where(np.isnan(blended) & ~np.isnan(val_nir) & (rho_r >= bound_high), val_nir, blended)

    return blended.astype(np.float32), weight.astype(np.float32)


def compute_rededge_turbidity(
    rho_red: np.ndarray,
    rho_rededge: np.ndarray,
    rho_nir: np.ndarray,
    parameter: str = "turbidity"
) -> np.ndarray:
    """
    Multi-conditional Red-Edge (704 nm, Sentinel-2 B5) adaptive switching.
    Incorporates the 704 nm spectral region for hyper-turbid river plumes
    where Red reflectance Rrs(665) exceeds 0.042 sr^-1 (~rho_w = 0.132).
    """
    param_key = "turbidity_FNU" if parameter.lower() in ["turbidity", "fnu", "ntu"] else "tss_mg_L"
    
    red_a = NECHAD_COEFFICIENTS[param_key]["S2_B4_665nm"]["A"]
    red_c = NECHAD_COEFFICIENTS[param_key]["S2_B4_665nm"]["C"]
    
    re_a = NECHAD_COEFFICIENTS[param_key]["S2_B5_704nm"]["A"]
    re_c = NECHAD_COEFFICIENTS[param_key]["S2_B5_704nm"]["C"]
    
    nir_a = NECHAD_COEFFICIENTS[param_key]["S2_B8A_865nm"]["A"]
    nir_c = NECHAD_COEFFICIENTS[param_key]["S2_B8A_865nm"]["C"]

    t_red = compute_nechad_model(rho_red, red_a, red_c)
    t_re = compute_nechad_model(rho_rededge, re_a, re_c)
    t_nir = compute_nechad_model(rho_nir, nir_a, nir_c)

    # Conversion thresholds
    rho_red_sat = REDEDGE_THRESHOLDS["Rrs_665_sat"] * np.pi  # ~0.132
    rho_re_sat = REDEDGE_THRESHOLDS["Rrs_704_sat"] * np.pi   # ~0.195

    output = np.copy(t_red)
    # Intermediate regime -> Red-Edge
    mask_re = (rho_red > rho_red_sat) & (rho_rededge <= rho_re_sat)
    output = np.where(mask_re, t_re, output)
    # Extreme regime -> NIR
    mask_nir = (rho_rededge > rho_re_sat)
    output = np.where(mask_nir, t_nir, output)

    return output.astype(np.float32)


def apply_sbaf_correction(
    reflectance: np.ndarray,
    band: str = "red",
    from_sensor: str = "L8",
    to_sensor: str = "S2"
) -> np.ndarray:
    """
    Applies Spectral Band Adjustment Factors (SBAFs) to harmonize Landsat 8/9 OLI
    reflectance to Sentinel-2 MSI equivalent.
    """
    if from_sensor.upper() in ["L8", "L9"] and to_sensor.upper() == "S2":
        band_key = band.lower()
        if band_key in SBAF_FACTORS["L8_to_S2"]:
            params = SBAF_FACTORS["L8_to_S2"][band_key]
            corrected = params["slope"] * reflectance + params["intercept"]
            return np.maximum(corrected, 0.0).astype(np.float32)
    return np.asarray(reflectance, dtype=np.float32)


def compute_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """
    Computes Normalized Difference Water Index (McFeeters, 1996):
        NDWI = (Green - NIR) / (Green + NIR)
    """
    g = np.asarray(green, dtype=np.float32)
    n = np.asarray(nir, dtype=np.float32)
    with np.errstate(divide='ignore', invalid='ignore'):
        ndwi = (g - n) / (g + n)
        ndwi = np.where(np.isnan(ndwi) | (g + n == 0), -1.0, ndwi)
    return np.clip(ndwi, -1.0, 1.0).astype(np.float32)


def compute_mndwi(green: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """
    Computes Modified Normalized Difference Water Index (Xu, 2006):
        MNDWI = (Green - SWIR) / (Green + SWIR)
    """
    g = np.asarray(green, dtype=np.float32)
    s = np.asarray(swir, dtype=np.float32)
    with np.errstate(divide='ignore', invalid='ignore'):
        mndwi = (g - s) / (g + s)
        mndwi = np.where(np.isnan(mndwi) | (g + s == 0), -1.0, mndwi)
    return np.clip(mndwi, -1.0, 1.0).astype(np.float32)
