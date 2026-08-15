"""
Earth Engine satellite data acquisition and temporal compositing.
"""

from .gee_downloader import (
    initialize_gee,
    GEEDownloader,
    get_http_session
)

__all__ = [
    "initialize_gee",
    "GEEDownloader",
    "get_http_session"
]
