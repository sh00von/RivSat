"""
Water masking and radiometric quality assessment for Sentinel-2 MSI and Landsat 8/9 OLI.

Provides:
- SCL (Scene Classification Layer) decoding for Sentinel-2
- QA_PIXEL bitmask decoding for Landsat 8/9
- Hybrid dynamic water masking (combining QA masks with NDWI / MNDWI and NIR thresholds)
"""

import numpy as np
from typing import Optional
from .algorithms import compute_ndwi, compute_mndwi


def create_s2_water_mask(
    scl_data: np.ndarray,
    strict_water_only: bool = True
) -> np.ndarray:
    """
    Decodes Sentinel-2 Scene Classification Layer (SCL) to create a binary water mask.

    SCL Classes:
    0 = NO_DATA
    1 = SATURATED_OR_DEFECTIVE
    2 = DARK_AREA_PIXELS
    3 = CLOUD_SHADOWS
    4 = VEGETATION
    5 = NOT_VEGETATED
    6 = WATER
    7 = UNCLASSIFIED
    8 = CLOUD_MEDIUM_PROBABILITY
    9 = CLOUD_HIGH_PROBABILITY
    10 = THIN_CIRRUS
    11 = SNOW

    Parameters
    ----------
    scl_data : np.ndarray
        SCL raster values.
    strict_water_only : bool
        If True, only class 6 is marked as water.
        If False, excludes clouds/shadows/vegetation and keeps water & dark pixels.

    Returns
    -------
    np.ndarray (bool)
        Boolean mask where True indicates valid water.
    """
    scl = np.asarray(scl_data, dtype=np.int32)
    if strict_water_only:
        water_mask = (scl == 6)
    else:
        # Exclude clouds, shadows, land vegetation, bare soil, snow
        invalid = (
            (scl == 0) | (scl == 1) | (scl == 3) | (scl == 4) |
            (scl == 5) | (scl == 8) | (scl == 9) | (scl == 10) | (scl == 11)
        )
        water_mask = ~invalid

    return water_mask


def create_landsat_water_mask(
    qa_pixel: np.ndarray,
    strict_water_only: bool = True
) -> np.ndarray:
    """
    Decodes Landsat 8/9 Collection 2 Tier 1 QA_PIXEL bitmask.

    Bit Positions:
    Bit 0: Fill (0 = no fill, 1 = fill)
    Bit 1: Dilated Cloud (0 = no, 1 = yes)
    Bit 2: Cirrus (0 = no, 1 = yes)
    Bit 3: Cloud (0 = no, 1 = yes)
    Bit 4: Cloud Shadow (0 = no, 1 = yes)
    Bit 5: Snow (0 = no, 1 = yes)
    Bit 6: Clear (0 = no, 1 = yes)
    Bit 7: Water (0 = no, 1 = yes)

    Parameters
    ----------
    qa_pixel : np.ndarray
        QA_PIXEL integer bitmask array.
    strict_water_only : bool
        If True, requires Bit 7 == 1 and no cloud/shadow.

    Returns
    -------
    np.ndarray (bool)
        Boolean mask where True indicates valid water.
    """
    qa = np.asarray(qa_pixel, dtype=np.uint16)

    fill_bit = (qa & (1 << 0)) != 0
    dilated_cloud = (qa & (1 << 1)) != 0
    cirrus = (qa & (1 << 2)) != 0
    cloud = (qa & (1 << 3)) != 0
    cloud_shadow = (qa & (1 << 4)) != 0
    snow = (qa & (1 << 5)) != 0
    water_bit = (qa & (1 << 7)) != 0

    cloud_contaminated = fill_bit | dilated_cloud | cirrus | cloud | cloud_shadow | snow

    if strict_water_only:
        return water_bit & (~cloud_contaminated)
    else:
        return (~cloud_contaminated)


def create_hybrid_water_mask(
    green: np.ndarray,
    red: np.ndarray,
    nir: np.ndarray,
    swir: Optional[np.ndarray] = None,
    qa_or_scl: Optional[np.ndarray] = None,
    sensor: str = "S2",
    ndwi_threshold: float = -0.10,
    mndwi_threshold: float = -0.05
) -> np.ndarray:
    """
    Creates a robust hybrid water mask tailored for turbid inland rivers and estuaries.
    
    Standard satellite QA water classifiers frequently misclassify hyper-turbid water as
    land or cloud shadow due to high red/NIR backscattering. This hybrid mask combines:
    1. Base QA / SCL mask (clearing clouds and shadows)
    2. Dynamic NDWI / MNDWI optical index thresholds
    3. Non-physical reflectance filters (removes negative reflectances and terrestrial NIR spikes)

    Parameters
    ----------
    green, red, nir : np.ndarray
        Surface reflectance bands.
    swir : np.ndarray, optional
        SWIR surface reflectance band (~1610 nm).
    qa_or_scl : np.ndarray, optional
        SCL (Sentinel-2) or QA_PIXEL (Landsat) array.
    sensor : str
        'S2' or 'L8'/'L9'.
    ndwi_threshold : float
        NDWI cutoff for water detection (default -0.10 accommodates turbid river water).
    mndwi_threshold : float
        MNDWI cutoff when SWIR band is available.

    Returns
    -------
    np.ndarray (bool)
        Final refined water mask.
    """
    # 1. Base QA mask if provided
    if qa_or_scl is not None:
        if sensor.upper().startswith("S2"):
            # Exclude fill, defective, cloud shadows, vegetation, clouds, cirrus, snow
            # SCL 4=VEGETATION is excluded here; NDWI below provides a second catch for
            # mixed pixels (e.g., emergent macrophytes in turbid water). SCL 5=NOT_VEGETATED
            # and SCL 7=UNCLASSIFIED are allowed so that hyper-turbid water misclassified
            # as non-water land by the classifier still reaches the NDWI filter.
            qa_valid = ~np.isin(qa_or_scl, [0, 1, 3, 4, 8, 9, 10, 11])
        else:
            qa_valid = create_landsat_water_mask(qa_or_scl, strict_water_only=False)
    else:
        qa_valid = np.ones_like(red, dtype=bool)

    # 2. Optical Index Masking
    ndwi = compute_ndwi(green, nir)
    water_index = (ndwi > ndwi_threshold)

    if swir is not None:
        mndwi = compute_mndwi(green, swir)
        water_index = water_index | (mndwi > mndwi_threshold)

    # 3. Physical boundaries (turbid river water has NIR < Red * 1.5, whereas dense land vegetation has NIR >> Red)
    # Dense terrestrial vegetation typically has NIR / Red > 2.5
    with np.errstate(divide='ignore', invalid='ignore'):
        nir_red_ratio = nir / np.where(red <= 0.001, np.nan, red)
        not_dense_vegetation = np.where(np.isnan(nir_red_ratio), True, (nir_red_ratio < 2.8))

    # Basic positive reflectance filter
    valid_reflectance = (red > 0.0) & (nir >= 0.0) & (green > 0.0)

    final_mask = qa_valid & water_index & not_dense_vegetation & valid_reflectance
    return final_mask
