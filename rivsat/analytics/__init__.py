"""
CoastSat-style spatial analytics, longitudinal profiles, transects, and time-series trend analysis.
"""

from .transects import (
    extract_station_data,
    extract_longitudinal_profile,
    extract_cross_transects
)
from .timeseries import (
    TimeSeriesEngine,
    calculate_temporal_trends
)

__all__ = [
    "extract_station_data",
    "extract_longitudinal_profile",
    "extract_cross_transects",
    "TimeSeriesEngine",
    "calculate_temporal_trends"
]
