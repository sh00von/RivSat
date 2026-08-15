"""
Centralized logging configuration for Bio-Optic River.

Provides a consistent, configurable logger across all framework modules.
Replaces scattered print() calls with structured logging that supports
both console output and optional file logging.

Usage:
    from biooptic.logger import get_logger
    logger = get_logger(__name__)
    logger.info("[OK] Processing complete.")
"""

import logging
import sys
from typing import Optional

_CONFIGURED = False


def get_logger(
    name: str = "rivsat",
    level: int = logging.INFO,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Returns a configured logger instance for the Bio-Optic River framework.

    Parameters
    ----------
    name : str
        Logger name (typically __name__ of the calling module).
    level : int
        Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    log_file : str, optional
        Path to optional log file for persistent logging.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    global _CONFIGURED

    logger = logging.getLogger(name)

    if not _CONFIGURED and not logger.handlers:
        logger.setLevel(level)

        # Console handler with clean formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_fmt = logging.Formatter(
            "%(message)s"
        )
        console_handler.setFormatter(console_fmt)
        logger.addHandler(console_handler)

        # Optional file handler
        if log_file:
            file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_fmt = logging.Formatter(
                "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_fmt)
            logger.addHandler(file_handler)

        logger.propagate = False
        _CONFIGURED = True

    return logger
