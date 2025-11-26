"""
Lightweight logging utilities for the VoteMarket toolkit.

Provides a consistent logger with a simple console handler and optional
log-level override via the VM_LOG_LEVEL environment variable.
"""

import logging
import os
from typing import Optional

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a configured logger with a stream handler.

    The first time a logger is created, a StreamHandler is attached with a
    plain-text formatter. Subsequent calls reuse the existing configuration.

    Log level can be overridden with the VM_LOG_LEVEL environment variable.
    """
    logger = logging.getLogger(name if name else __name__)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        logger.addHandler(handler)

        level_str = os.getenv("VM_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_str, logging.INFO)
        logger.setLevel(level)

    return logger
