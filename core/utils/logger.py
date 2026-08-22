"""Structured application logging."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from core.utils.constants import APP_NAME, LOG_DIR

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_configured = False


def setup_logging(debug: bool = False) -> logging.Logger:
    """Configure root logging once. Safe to call repeatedly."""
    global _configured
    root = logging.getLogger()
    level = logging.DEBUG if debug else logging.INFO

    if _configured:
        root.setLevel(level)
        return logging.getLogger(APP_NAME)

    root.setLevel(level)
    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_DIR / "glitch.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        # A log file is a convenience, never a startup requirement.
        root.warning("Could not open log file in %s", LOG_DIR)

    _configured = True
    return logging.getLogger(APP_NAME)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{APP_NAME}.{name}")
