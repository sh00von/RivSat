"""
RivSat: High-Performance Satellite Remote Sensing of Water Turbidity and TSS.

A modular CoastSat-style bio-optical satellite processing framework utilizing Google Earth Engine,
the Dogliotti et al. (2015) blended dual-band algorithm, and Nechad et al. (2010/2016)
semi-analytical models for mapping riverine, estuarine, and coastal water quality.

Sub-packages:
    - rivsat.core: Radiative transfer equations, Nechad/Dogliotti models, and water masking
    - rivsat.acquisition: Earth Engine query engine and temporal compositing
    - rivsat.processing: Parallel batch bio-optical raster processor
    - rivsat.analytics: Longitudinal profiles, cross-river transects, and Mann-Kendall time-series
    - rivsat.validation: In-situ KD-Tree spatial matchups and optical parameter recalibration
    - rivsat.visualization: Publication-quality spatial maps, product triplets, and scatter plots
    - rivsat.utils: GeoJSON spatial layer tools, interactive Leaflet maps, and logging
"""

from .core import (
    NECHAD_COEFFICIENTS,
    DOGLIOTTI_THRESHOLDS,
    REDEDGE_THRESHOLDS,
    SBAF_FACTORS,
    GEE_DATASETS,
    compute_nechad_model,
    compute_dogliotti_blended,
    compute_rededge_turbidity,
    apply_sbaf_correction,
    compute_ndwi,
    compute_mndwi,
    create_s2_water_mask,
    create_landsat_water_mask,
    create_hybrid_water_mask
)
from .acquisition import (
    initialize_gee,
    GEEDownloader,
    get_http_session
)
from .processing import (
    SceneProcessor,
    process_batch_parallel
)
from .analytics import (
    extract_station_data,
    extract_longitudinal_profile,
    extract_cross_transects,
    TimeSeriesEngine,
    calculate_temporal_trends
)
from .validation import (
    calculate_validation_metrics,
    find_spatiotemporal_matchups,
    recalibrate_nechad_coefficient
)
from .visualization import (
    fill_spatial_cloud_gaps,
    plot_turbidity_map,
    plot_scene_triplet,
    plot_multiparameter_grid,
    plot_station_timeseries,
    plot_longitudinal_gradient,
    plot_cross_transects,
    plot_validation_scatter
)
from .utils import (
    bbox_to_polygon,
    load_geojson_polygon,
    load_geojson_features,
    validate_spatial_features,
    export_to_geojson,
    create_interactive_roi_map,
    create_centerline_draw_map,
    create_stations_draw_map,
    save_study_site_config,
    load_study_site_config,
    get_logger
)

__version__ = "1.2.0"
__author__ = "Md Minaruzzaman Shovon"

__all__ = [
    # Core Physics & Models
    "NECHAD_COEFFICIENTS",
    "DOGLIOTTI_THRESHOLDS",
    "REDEDGE_THRESHOLDS",
    "SBAF_FACTORS",
    "GEE_DATASETS",
    "compute_nechad_model",
    "compute_dogliotti_blended",
    "compute_rededge_turbidity",
    "apply_sbaf_correction",
    "compute_ndwi",
    "compute_mndwi",
    "create_s2_water_mask",
    "create_landsat_water_mask",
    "create_hybrid_water_mask",
    # Acquisition
    "initialize_gee",
    "GEEDownloader",
    "get_http_session",
    # Processing
    "SceneProcessor",
    "process_batch_parallel",
    # Analytics
    "extract_station_data",
    "extract_longitudinal_profile",
    "extract_cross_transects",
    "TimeSeriesEngine",
    "calculate_temporal_trends",
    # Validation
    "calculate_validation_metrics",
    "find_spatiotemporal_matchups",
    "recalibrate_nechad_coefficient",
    # Visualization
    "plot_turbidity_map",
    "plot_scene_triplet",
    "plot_station_timeseries",
    "plot_longitudinal_gradient",
    "plot_cross_transects",
    "plot_validation_scatter",
    # Utils & ROI Tools
    "bbox_to_polygon",
    "load_geojson_polygon",
    "load_geojson_features",
    "validate_spatial_features",
    "export_to_geojson",
    "create_interactive_roi_map",
    "create_centerline_draw_map",
    "create_stations_draw_map",
    "save_study_site_config",
    "load_study_site_config",
    "get_logger"
]
