"""
Core physics, radiative transfer models, and water masking algorithms.
"""

from .config import (
    NECHAD_COEFFICIENTS,
    DOGLIOTTI_THRESHOLDS,
    REDEDGE_THRESHOLDS,
    SBAF_FACTORS,
    WATER_QUALITY_COEFFICIENTS,
    GEE_DATASETS
)
from .algorithms import (
    compute_nechad_model,
    compute_dogliotti_blended,
    compute_rededge_turbidity,
    apply_sbaf_correction,
    compute_ndwi,
    compute_mndwi,
    compute_ndci_chlorophyll,
    compute_cdom,
    compute_salinity,
    compute_secchi_depth,
    compute_oc3_chlorophyll,
    compute_kd490,
    compute_fai,
)
from .water_mask import (
    create_s2_water_mask,
    create_landsat_water_mask,
    create_hybrid_water_mask
)

__all__ = [
    "NECHAD_COEFFICIENTS",
    "DOGLIOTTI_THRESHOLDS",
    "REDEDGE_THRESHOLDS",
    "SBAF_FACTORS",
    "WATER_QUALITY_COEFFICIENTS",
    "GEE_DATASETS",
    "compute_nechad_model",
    "compute_dogliotti_blended",
    "compute_rededge_turbidity",
    "apply_sbaf_correction",
    "compute_ndwi",
    "compute_mndwi",
    "compute_ndci_chlorophyll",
    "compute_cdom",
    "compute_salinity",
    "compute_secchi_depth",
    "compute_oc3_chlorophyll",
    "compute_kd490",
    "compute_fai",
    "create_s2_water_mask",
    "create_landsat_water_mask",
    "create_hybrid_water_mask",
]
