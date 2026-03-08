"""
Aura — Rotating File Logger
Provides a unified logging interface for the entire application.
"""

import logging
from logging.handlers import RotatingFileHandler
import sys

from config import LOG_PATH, APP_NAME

# CLI override for console log level (None = default INFO)
_cli_console_level = [None]


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ from the calling module).

    Returns:
        Configured logging.Logger instance.
    """
    logger_name = f"{APP_NAME}.{name}" if name else APP_NAME
    logger = logging.getLogger(logger_name)

    # Only add handlers if none exist (prevents duplicate handlers)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # File handler — rotating, max 5MB per file, keep 3 backups
        file_handler = RotatingFileHandler(
            LOG_PATH,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console handler — respects CLI override if set
        console_handler = logging.StreamHandler(sys.stdout)
        console_level = _cli_console_level[0] if _cli_console_level[0] is not None else logging.INFO
        console_handler.setLevel(console_level)
        console_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


def set_console_level(level: int):
    """Set console log level for all Aura loggers (current and future).

    Called by CLI before engine init to suppress INFO noise.
    File handler continues at DEBUG regardless.
    """
    _cli_console_level[0] = level

    # Update all existing Aura loggers
    for name, lg in logging.Logger.manager.loggerDict.items():
        if isinstance(lg, logging.Logger) and name.startswith(APP_NAME):
            for handler in lg.handlers:
                if isinstance(handler, logging.StreamHandler) and \
                   not isinstance(handler, RotatingFileHandler):
                    handler.setLevel(level)
