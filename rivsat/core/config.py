"""
Configuration and bio-optical calibration coefficients for satellite water turbidity
and Total Suspended Solids (TSS) retrieval.

References:
- Dogliotti et al. (2015): A single algorithm to retrieve turbidity from 
  low to high turbid waters based on red and near-infrared reflectance. RSE.
- Nechad et al. (2010): Calibration and validation of a universal algorithm
  for retrieval of total suspended matter from MERIS and MODIS. RSE.
- Nechad et al. (2016): Sensor-specific calibration of a semi-analytical algorithm
  for turbidity and TSS from Sentinel-2 MSI and Landsat-8 OLI.
- Pahlevan et al. (2019): Seamless Retrievals of Suspended Particulate Matter
  from Landsat-8 and Sentinel-2. RSE.
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
# 5. GOOGLE EARTH ENGINE DATASET CATALOG & BAND NAMES
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
