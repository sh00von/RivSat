"""
Core bio-optical radiative transfer algorithms for satellite water quality estimation.

Includes:
- Nechad et al. (2010/2016) semi-analytical single-band models
- Dogliotti et al. (2015) dual-band blended switching framework
- Multi-conditional Red-Edge (704 nm) extreme plume extension
- Cross-sensor Spectral Band Adjustment Factors (SBAFs) with L9 note
- Water index extraction (NDWI, MNDWI)
- OC3 band-ratio Chlorophyll-a (O'Reilly & Werdell 2019) — coastal/open-ocean
- Kd(490) diffuse attenuation coefficient (Morel et al. 2007)
- FAI Floating Algae Index (Hu 2009) — bloom/macrophyte detection
"""

import numpy as np
from typing import Optional, Dict, Tuple, Union
from .config import (
    NECHAD_COEFFICIENTS,
    DOGLIOTTI_THRESHOLDS,
    REDEDGE_THRESHOLDS,
    SBAF_FACTORS,
    WATER_QUALITY_COEFFICIENTS
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

    Notes
    -----
    L9 OLI-2 uses the same SBAF table as L8 OLI (Roy et al. 2021 confirm near-identical
    spectral response functions). The correction is a linear polynomial valid for
    rho_w ∈ [0, 0.25]; accuracy degrades at higher reflectances.
    Unsupported conversion directions return the input array unchanged with a warning.
    """
    import warnings
    fs = from_sensor.upper()
    ts = to_sensor.upper()

    if fs in ("L8", "L9") and ts == "S2":
        band_key = band.lower()
        if band_key in SBAF_FACTORS["L8_to_S2"]:
            if fs == "L9":
                warnings.warn(
                    "Applying L8→S2 SBAF factors to L9 data. "
                    "L9 OLI-2 spectral response is nearly identical to L8 OLI "
                    "(Roy et al. 2021), but validate locally if precision is critical.",
                    UserWarning,
                    stacklevel=2,
                )
            params = SBAF_FACTORS["L8_to_S2"][band_key]
            corrected = params["slope"] * reflectance + params["intercept"]
            return np.maximum(corrected, 0.0).astype(np.float32)
        else:
            warnings.warn(
                f"No SBAF entry for band='{band}' in L8→S2 table. "
                f"Available: {list(SBAF_FACTORS['L8_to_S2'].keys())}. "
                "Returning input unchanged.",
                UserWarning,
                stacklevel=2,
            )
    else:
        warnings.warn(
            f"SBAF from '{from_sensor}' to '{to_sensor}' is not supported. "
            "Only L8/L9→S2 is implemented. Returning input unchanged.",
            UserWarning,
            stacklevel=2,
        )
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


def compute_ndci_chlorophyll(
    rho_red: np.ndarray,
    rho_rededge: np.ndarray,
    custom_coeffs: Optional[Dict[str, float]] = None
) -> np.ndarray:
    """
    Computes Chlorophyll-a concentration (ug/L) using the Normalized Difference
    Chlorophyll Index (NDCI; Mishra & Mishra, 2012):

        NDCI = (rho_w(705) - rho_w(665)) / (rho_w(705) + rho_w(665))
        Chl-a = a0 + a1 * NDCI + a2 * NDCI^2
    """
    r_red = np.asarray(rho_red, dtype=np.float32)
    r_re = np.asarray(rho_rededge, dtype=np.float32)

    coeffs = custom_coeffs or WATER_QUALITY_COEFFICIENTS["chlorophyll_NDCI"]
    a0, a1, a2 = coeffs["a0"], coeffs["a1"], coeffs["a2"]

    with np.errstate(divide='ignore', invalid='ignore'):
        denom = r_re + r_red
        ndci = np.where(denom != 0.0, (r_re - r_red) / denom, np.nan)
        chl_a = a0 + a1 * ndci + a2 * (ndci ** 2)
        chl_a = np.where(np.isnan(ndci) | (chl_a < 0.0), np.nan, chl_a)

    return chl_a.astype(np.float32)


def compute_cdom(
    rho_green: np.ndarray,
    rho_red: np.ndarray,
    custom_coeffs: Optional[Dict[str, float]] = None
) -> np.ndarray:
    """
    Estimates Colored Dissolved Organic Matter (CDOM / a_g(440) in m^-1) using
    the Green/Red spectral reflectance ratio model (Griffin et al., 2018):

        a_cdom(440) = c0 * (rho_w(Green) / rho_w(Red))^c1
    """
    g = np.asarray(rho_green, dtype=np.float32)
    r = np.asarray(rho_red, dtype=np.float32)

    coeffs = custom_coeffs or WATER_QUALITY_COEFFICIENTS["cdom_GreenRed"]
    c0, c1 = coeffs["c0"], coeffs["c1"]

    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = g / r
        cdom = c0 * (ratio ** c1)
        cdom = np.where(np.isnan(ratio) | (r <= 0.0) | (g <= 0.0) | (cdom < 0.0), np.nan, cdom)

    return cdom.astype(np.float32)


def compute_salinity(
    cdom_arr: np.ndarray,
    custom_coeffs: Optional[Dict[str, float]] = None
) -> np.ndarray:
    """
    Estimates Estuarine Surface Salinity (SSS in PSU) using a CDOM empirical mixing
    proxy model (Subramaniam et al., 2011):

        Salinity (PSU) = S_ocean - k * a_cdom(440)
    """
    cdom = np.asarray(cdom_arr, dtype=np.float32)

    coeffs = custom_coeffs or WATER_QUALITY_COEFFICIENTS["salinity_CDOM"]
    s_ocean, k = coeffs["S_ocean"], coeffs["k"]

    with np.errstate(divide='ignore', invalid='ignore'):
        sal = s_ocean - k * cdom
        sal = np.where(np.isnan(cdom), np.nan, np.clip(sal, 0.0, s_ocean))

    return sal.astype(np.float32)


def compute_secchi_depth(
    turbidity_arr: np.ndarray,
    custom_coeffs: Optional[Dict[str, float]] = None
) -> np.ndarray:
    """
    Estimates Secchi Disk Depth (SDD in meters) from water turbidity (Lee et al., 2015):

        SDD = a / (Turbidity ^ b)
    """
    turb = np.asarray(turbidity_arr, dtype=np.float32)

    coeffs = custom_coeffs or WATER_QUALITY_COEFFICIENTS["secchi_Turbidity"]
    a, b = coeffs["a"], coeffs["b"]

    with np.errstate(divide='ignore', invalid='ignore'):
        sdd = a / (np.maximum(turb, 0.1) ** b)
        sdd = np.where(np.isnan(turb) | (turb <= 0.0), np.nan, sdd)

    return sdd.astype(np.float32)


def compute_oc3_chlorophyll(
    rho_blue: np.ndarray,
    rho_green: np.ndarray,
    rho_red: np.ndarray,
    custom_coeffs: Optional[Dict[str, float]] = None
) -> np.ndarray:
    """
    Estimates Chlorophyll-a (ug/L) using the NASA OC3 band-ratio algorithm
    (O'Reilly et al. 1998, updated coefficients from O'Reilly & Werdell 2019).

    OC3 is the operational standard for MODIS, SeaWiFS, and PACE. It outperforms
    NDCI in oligotrophic to mesotrophic coastal waters (Chl-a < 10 ug/L) where
    the blue/green ratio retains sensitivity. NDCI is preferred in turbid productive
    rivers (Chl-a > 20 ug/L, high TSS).

        R = log10(max(rho_blue, rho_green) / rho_red)
        log10(Chl-a) = a0 + a1*R + a2*R^2 + a3*R^3 + a4*R^4

    Parameters
    ----------
    rho_blue : np.ndarray
        Blue band water-leaving reflectance (~443-490 nm).
    rho_green : np.ndarray
        Green band water-leaving reflectance (~555 nm).
    rho_red : np.ndarray
        Red band water-leaving reflectance (~665 nm).
    custom_coeffs : dict, optional
        Override OC3 polynomial coefficients {'a0','a1','a2','a3','a4'}.

    Returns
    -------
    np.ndarray
        Chlorophyll-a in ug/L.

    References
    ----------
    O'Reilly & Werdell (2019). Chlorophyll algorithms for ocean color sensors —
    OC4, OC5 & OC6. RSE, 229, 32-47.
    """
    b = np.asarray(rho_blue, dtype=np.float32)
    g = np.asarray(rho_green, dtype=np.float32)
    r = np.asarray(rho_red, dtype=np.float32)

    # O'Reilly & Werdell (2019) OC3 coefficients for Sentinel-2 / generic visible
    _defaults = {"a0": 0.2515, "a1": -2.3798, "a2": 1.5823, "a3": -0.6372, "a4": -0.5692}
    coeffs = custom_coeffs or _defaults
    a0, a1, a2, a3, a4 = coeffs["a0"], coeffs["a1"], coeffs["a2"], coeffs["a3"], coeffs["a4"]

    with np.errstate(divide='ignore', invalid='ignore'):
        max_bg = np.maximum(b, g)
        ratio = np.where((r > 0.0) & (max_bg > 0.0), max_bg / r, np.nan)
        log_r = np.where(ratio > 0.0, np.log10(ratio), np.nan)
        log_chl = a0 + a1 * log_r + a2 * log_r**2 + a3 * log_r**3 + a4 * log_r**4
        chl_oc3 = np.where(np.isnan(log_r), np.nan, 10.0 ** log_chl)
        chl_oc3 = np.where(chl_oc3 < 0.01, np.nan, chl_oc3)

    return chl_oc3.astype(np.float32)


def compute_kd490(
    rho_blue: np.ndarray,
    rho_green: np.ndarray,
    custom_coeffs: Optional[Dict[str, float]] = None
) -> np.ndarray:
    """
    Estimates the diffuse attenuation coefficient at 490 nm — Kd(490) in m^-1 —
    using the NASA KD2 band-ratio algorithm (Mueller 2000, Morel et al. 2007).

    Kd(490) quantifies how rapidly downwelling light attenuates with depth and is a
    standard MODIS/SeaWiFS/PACE Level-3 ocean color product. It is the primary
    input for euphotic zone depth (Zeu ≈ 4.6 / Kd(490)) and primary production
    models in estuarine and coastal studies.

        log10(Kd490) = a0 + a1 * log10(rho_blue / rho_green)

    Parameters
    ----------
    rho_blue : np.ndarray
        Blue band water-leaving reflectance (~443-490 nm).
    rho_green : np.ndarray
        Green band water-leaving reflectance (~555 nm).
    custom_coeffs : dict, optional
        Override coefficients {'a0', 'a1'}.

    Returns
    -------
    np.ndarray
        Kd(490) in m^-1.

    References
    ----------
    Mueller (2000). SeaWiFS algorithm for the diffuse attenuation coefficient, K(490),
    using water-leaving radiances at 490 and 555 nm. SeaWiFS Postlaunch Tech. Rep.
    Morel et al. (2007). Examining the consistency of products derived from various
    ocean color sensors. RSE, 111(1), 69-88.
    """
    b = np.asarray(rho_blue, dtype=np.float32)
    g = np.asarray(rho_green, dtype=np.float32)

    # KD2 coefficients (Morel et al. 2007, updated for generic blue/green bands)
    _defaults = {"a0": -0.8813, "a1": -2.0584}
    coeffs = custom_coeffs or _defaults
    a0, a1 = coeffs["a0"], coeffs["a1"]

    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = np.where((g > 0.0) & (b > 0.0), b / g, np.nan)
        log_kd = a0 + a1 * np.log10(np.where(ratio > 0.0, ratio, np.nan))
        kd490 = np.where(np.isnan(log_kd), np.nan, 10.0 ** log_kd)
        kd490 = np.where(kd490 < 0.0, np.nan, kd490)

    return kd490.astype(np.float32)


def compute_fai(
    rho_red: np.ndarray,
    rho_nir: np.ndarray,
    rho_swir: np.ndarray,
    red_wl: float = 665.0,
    nir_wl: float = 865.0,
    swir_wl: float = 1610.0
) -> np.ndarray:
    """
    Computes the Floating Algae Index (FAI) for detection of surface algal blooms,
    Sargassum, water hyacinth, and other floating macrophytes (Hu 2009).

    FAI = rho_nir - rho_nir_prime
    where rho_nir_prime is the linear baseline between red and SWIR:
        rho_nir_prime = rho_red + (rho_swir - rho_red) * (nir_wl - red_wl) / (swir_wl - red_wl)

    Positive FAI indicates floating vegetation / algae. Negative FAI indicates open water.
    Near-zero FAI (|FAI| < 0.01) is ambiguous (mixed pixels, cloud edges, turbid plumes).

    Parameters
    ----------
    rho_red : np.ndarray
        Red band reflectance (~665 nm).
    rho_nir : np.ndarray
        NIR band reflectance (~865 nm).
    rho_swir : np.ndarray
        SWIR band reflectance (~1610 nm).
    red_wl, nir_wl, swir_wl : float
        Central wavelengths (nm) for the three bands. Defaults are Sentinel-2 B4/B8A/B11.

    Returns
    -------
    np.ndarray
        FAI array (dimensionless). Positive = floating algae, negative = open water.

    References
    ----------
    Hu (2009). A novel ocean color index to detect floating algae in the global oceans.
    RSE, 113(10), 2118-2129.
    """
    r = np.asarray(rho_red, dtype=np.float32)
    n = np.asarray(rho_nir, dtype=np.float32)
    s = np.asarray(rho_swir, dtype=np.float32)

    alpha = (nir_wl - red_wl) / (swir_wl - red_wl)
    nir_prime = r + (s - r) * alpha
    fai = n - nir_prime

    invalid = np.isnan(r) | np.isnan(n) | np.isnan(s)
    return np.where(invalid, np.nan, fai).astype(np.float32)
