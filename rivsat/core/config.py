"""
Configuration and bio-optical calibration coefficients for multi-parameter satellite
water quality estimation (Turbidity, TSS, Chlorophyll-a, CDOM, Salinity, Secchi Depth).

Peer-Reviewed Literature References:
- Dogliotti et al. (2015): A single algorithm to retrieve turbidity from low to high turbid
  waters based on red and near-infrared reflectance. RSE, 156, 157-168.
- Nechad et al. (2010): Calibration and validation of a universal algorithm for retrieval of
  total suspended matter from MERIS and MODIS. RSE, 114(5), 854-866.
- Nechad et al. (2016): Sensor-specific calibration of a semi-analytical algorithm for
  turbidity and TSS from Sentinel-2 MSI and Landsat-8 OLI.
- Mishra & Mishra (2012): Normalized difference chlorophyll index: A novel model for remote
  estimation of chlorophyll-a in turbid productive waters. RSE, 117, 394-406.
- Griffin et al. (2018): Satellite remote sensing of dissolved organic carbon in major river systems.
  RSE, 209, 94-109.
- Subramaniam et al. (2011): Amazon river plume dynamics and sea surface salinity from optical remote sensing.
  JGR: Oceans, 116(C3).
- Lee et al. (2015): Secchi disk depth: A new theory and mechanistic model for underwater visibility.
  RSE, 157, 135-144.
"""

from typing import Dict, Any

# ==============================================================================
# 1. NECHAD (2010/2016) SEMI-ANALYTICAL MODEL COEFFICIENTS
# ==============================================================================
# Model formula: T (FNU) = (A_T * rho_w) / (1 - rho_w / C_T)
#               TSS (mg/L) = (A_SPM * rho_w) / (1 - rho_w / C_SPM)
# where rho_w = pi * Rrs (dimensionless water-leaving reflectance)

NECHAD_COEFFICIENTS: Dict[str, Dict[str, Dict[str, float]]] = {
    "turbidity_FNU": {
        # Sentinel-2 MSI
        "S2_B4_665nm": {"A": 228.1, "C": 0.164},   # Red band (low-moderate turbidity)
        "S2_B5_704nm": {"A": 650.2, "C": 0.185},   # Red-Edge band (intermediate plume)
        "S2_B8A_865nm": {"A": 3078.9, "C": 0.211}, # Narrow NIR band (high-extreme turbidity)
        "S2_B8_842nm": {"A": 2890.5, "C": 0.208},  # Broad NIR band
        # Landsat 8/9 OLI
        "L8_B4_655nm": {"A": 242.7, "C": 0.169},   # Red band
        "L8_B5_865nm": {"A": 2987.2, "C": 0.211},  # NIR band
        "L9_B4_655nm": {"A": 242.7, "C": 0.169},
        "L9_B5_865nm": {"A": 2987.2, "C": 0.211},
    },
    "tss_mg_L": {
        # Sentinel-2 MSI
        "S2_B4_665nm": {"A": 245.5, "C": 0.164},
        "S2_B5_704nm": {"A": 710.0, "C": 0.185},
        "S2_B8A_865nm": {"A": 3310.0, "C": 0.211},
        "S2_B8_842nm": {"A": 3120.0, "C": 0.208},
        # Landsat 8/9 OLI
        "L8_B4_655nm": {"A": 260.8, "C": 0.169},
        "L8_B5_865nm": {"A": 3215.0, "C": 0.211},
        "L9_B4_655nm": {"A": 260.8, "C": 0.169},
        "L9_B5_865nm": {"A": 3215.0, "C": 0.211},
    }
}

# ==============================================================================
# 2. DOGLIOTTI (2015) DUAL-BAND BLENDING BOUNDARIES
# ==============================================================================
DOGLIOTTI_THRESHOLDS = {
    "rho_w_low": 0.05,     # Below this, pure Red-band Nechad model is used
    "rho_w_high": 0.07,    # Above this, pure NIR-band Nechad model is used
    # In-between [0.05, 0.07], linear blending weight W is applied:
    # W = (rho_w_red - 0.05) / (0.07 - 0.05)
    # Output = (1 - W) * T_red + W * T_nir
}

# ==============================================================================
# 3. RED-EDGE MULTI-CONDITIONAL EXTENSION THRESHOLDS
# ==============================================================================
REDEDGE_THRESHOLDS = {
    "Rrs_665_sat": 0.042,     # sr^-1 (equivalent to rho_w ~ 0.132)
    "Rrs_704_sat": 0.062,     # sr^-1 (equivalent to rho_w ~ 0.195)
}

# ==============================================================================
# 4. CROSS-SENSOR SPECTRAL BAND ADJUSTMENT FACTORS (SBAF)
# ==============================================================================
# Polynomial mappings to align Landsat 8/9 OLI reflectances to Sentinel-2 MSI equivalent:
# rho_w_S2_equiv = slope * rho_w_L8 + intercept
SBAF_FACTORS = {
    "L8_to_S2": {
        "red": {"slope": 0.982, "intercept": 0.0008},
        "nir": {"slope": 1.005, "intercept": -0.0003},
        "green": {"slope": 0.991, "intercept": 0.0004},
    }
}

# ==============================================================================
# 5. MULTI-PARAMETER WATER QUALITY CALIBRATION COEFFICIENTS
# ==============================================================================
# Regional applicability notes:
# - chlorophyll_NDCI: calibrated for turbid productive inland/coastal waters (Mishra & Mishra 2012).
#   For oligotrophic coastal waters or open ocean use OC3/OCI instead.
# - cdom_GreenRed: calibrated for large river systems (Griffin et al. 2018). Use with caution
#   in highly stratified estuaries or optically complex coastal water.
# - salinity_CDOM: S_ocean=35.0 PSU assumes North Atlantic / equatorial ocean.
#   Override with site-specific S_ocean for Bay of Bengal (~30-32 PSU),
#   Mediterranean (~38-39 PSU), Red Sea (~40 PSU), or Baltic (<10 PSU).
# - secchi_Turbidity: simplified empirical power law (Lee et al. 2015). Valid for
#   turbid inland/estuarine water (T > 2 FNU). Use full QAA for optically complex open ocean.
# References:
# - Mishra & Mishra (2012): NDCI for Chlorophyll-a retrieval
# - Griffin et al. (2018): CDOM estimation from spectral reflectance ratios
# - Subramaniam et al. (2011): CDOM-salinity proxy model in estuarine plumes
# - Lee et al. (2015): Quasi-analytical algorithm for water clarity / Secchi depth
WATER_QUALITY_COEFFICIENTS = {
    "chlorophyll_NDCI": {
        "a0": 14.039,
        "a1": 86.11,
        "a2": 194.32
    },
    "cdom_GreenRed": {
        "c0": 1.25,
        "c1": -1.42
    },
    "salinity_CDOM": {
        "S_ocean": 35.0,
        "k": 4.2
    },
    "secchi_Turbidity": {
        "a": 1.7,
        "b": 0.8
    }
}

# ==============================================================================
# 6. GOOGLE EARTH ENGINE DATASET CATALOG & BAND NAMES
# ==============================================================================
GEE_DATASETS: Dict[str, Dict[str, Any]] = {
    "S2_HARMONIZED": {
        "collection": "COPERNICUS/S2_SR_HARMONIZED",
        "bands": {
            "blue": "B2",
            "green": "B3",
            "red": "B4",
            "red_edge_1": "B5",
            "nir": "B8A",
            "nir_broad": "B8",
            "swir1": "B11",
            "scl": "SCL",
            "qa60": "QA60"
        },
        "scale_factor": 0.0001,  # DN to surface reflectance
        "cloud_mask_property": "CLOUDY_PIXEL_PERCENTAGE",
        "default_resolution": 20.0 # meters (20m optimal for regional estuaries and multi-band GEE downloads)
    },
    "L8": {
        "collection": "LANDSAT/LC08/C02/T1_L2",
        "bands": {
            "blue": "SR_B2",
            "green": "SR_B3",
            "red": "SR_B4",
            "nir": "SR_B5",
            "swir1": "SR_B6",
            "qa_pixel": "QA_PIXEL"
        },
        "scale_factor": 0.0000275,
        "offset": -0.2,
        "cloud_mask_property": "CLOUD_COVER",
        "default_resolution": 30.0 # meters
    },
    "L9": {
        "collection": "LANDSAT/LC09/C02/T1_L2",
        "bands": {
            "blue": "SR_B2",
            "green": "SR_B3",
            "red": "SR_B4",
            "nir": "SR_B5",
            "swir1": "SR_B6",
            "qa_pixel": "QA_PIXEL"
        },
        "scale_factor": 0.0000275,
        "offset": -0.2,
        "cloud_mask_property": "CLOUD_COVER",
        "default_resolution": 30.0 # meters
    }
}
