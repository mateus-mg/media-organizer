"""Logging package for Media Organization System."""

from app.logging.config import (
    get_logger,
    log_success,
    log_error,
    log_warning,
    log_info,
    log_organize,
    log_music,
    log_book,
    log_comic,
    log_database,
    log_conflict,
    log_progress,
    log_stats,
    log_debug,
    set_console_log_level,
    log_error,
)
from app.logging.formatter import LogSection

__all__ = [
    "get_logger",
    "log_success",
    "log_error",
    "log_warning",
    "log_info",
    "log_organize",
    "log_music",
    "log_book",
    "log_comic",
    "log_database",
    "log_conflict",
    "log_progress",
    "log_stats",
    "log_debug",
    "set_console_log_level",
    "LogSection",
]
