#!/usr/bin/env python3
"""Centralized logging configuration for Media Organization System."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.logging import RichHandler

console = Console()

SYMBOLS = {
    "success": "✓",
    "error": "✗",
    "warning": "!",
    "info": "",
    "organize": "",
    "music": "",
    "book": "",
    "comic": "",
    "database": "",
    "cleanup": "",
    "progress": "",
    "time": "",
    "stats": "",
    "conflict": "",
}


class MediaOrganizerLogger:
    """Centralized logger for Media Organization System."""

    def __init__(self, name: str = "MediaOrganizer", log_file: Optional[str] = None, dry_run: bool = False):
        self.name = name
        self.dry_run = dry_run
        self.logger = logging.getLogger(name)

        if self.logger.handlers:
            return

        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))

        console_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            markup=False,
        )
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(
            logging.Formatter("%(message)s", datefmt="[%X]"))
        self.logger.addHandler(console_handler)

        if log_file is None:
            log_file = os.getenv("LOG_FILE", "./logs/organizer.log")

        log_path = Path(log_file)
        log_path.parent.mkdir(exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=50 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        self.logger.addHandler(file_handler)

    def get_logger(self):
        return self.logger

    @staticmethod
    def format_message(symbol_key: str, message: str) -> str:
        symbol = SYMBOLS.get(symbol_key, "")
        return f"{symbol} {message}" if symbol else message


def get_logger(name: str = "MediaOrganizer", dry_run: bool = False) -> logging.Logger:
    return MediaOrganizerLogger(name, dry_run=dry_run).get_logger()


def log_success(logger: logging.Logger, message: str):
    logger.info(MediaOrganizerLogger.format_message("success", message))


def log_error(logger: logging.Logger, message: str):
    logger.error(MediaOrganizerLogger.format_message("error", message))


def log_warning(logger: logging.Logger, message: str):
    logger.warning(MediaOrganizerLogger.format_message("warning", message))


def log_info(logger: logging.Logger, message: str):
    logger.info(MediaOrganizerLogger.format_message("info", message))


def log_organize(logger: logging.Logger, message: str):
    logger.info(MediaOrganizerLogger.format_message("organize", message))


def log_music(logger: logging.Logger, message: str):
    logger.info(MediaOrganizerLogger.format_message("music", message))


def log_book(logger: logging.Logger, message: str):
    logger.info(MediaOrganizerLogger.format_message("book", message))


def log_comic(logger: logging.Logger, message: str):
    logger.info(MediaOrganizerLogger.format_message("comic", message))


def log_database(logger: logging.Logger, message: str):
    logger.info(MediaOrganizerLogger.format_message("database", message))


def log_conflict(logger: logging.Logger, message: str):
    logger.info(MediaOrganizerLogger.format_message("conflict", message))


def log_progress(logger: logging.Logger, message: str):
    logger.info(MediaOrganizerLogger.format_message("progress", message))


def log_time(logger: logging.Logger, message: str):
    logger.info(MediaOrganizerLogger.format_message("time", message))


def log_stats(logger: logging.Logger, message: str):
    logger.info(MediaOrganizerLogger.format_message("stats", message))


def log_debug(logger: logging.Logger, message: str):
    logger.debug(message)


def log_structured(logger: logging.Logger, lines: List[str]):
    for line in lines:
        if line:
            logger.info(line)


def log_organization_start(logger: logging.Logger, directory: Path, media_type: str = "all"):
    title = f"ORGANIZATION START - {directory}"
    mode = "Dry-Run" if os.getenv("DRY_RUN_MODE",
                                  "false").lower() == "true" else "Normal"
    logger.info("-" * 80)
    logger.info(title)
    logger.info(f"Media Type: {media_type} | Mode: {mode}")
    logger.info("-" * 80)


def log_organization_complete(logger: logging.Logger, organized: int, skipped: int, failed: int, duration_seconds: float):
    hours = int(duration_seconds // 3600)
    minutes = int((duration_seconds % 3600) // 60)
    seconds = int(duration_seconds % 60)

    if hours > 0:
        duration_str = f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        duration_str = f"{minutes}m {seconds}s"
    else:
        duration_str = f"{seconds}s"

    logger.info("-" * 80)
    logger.info(
        f"Organization Complete: {organized} organized | {skipped} skipped | {failed} failed | Duration: {duration_str}"
    )
    logger.info("-" * 80)


def log_system_startup(logger: logging.Logger, config, stats: Dict[str, int]):
    download_paths = config.get_all_download_paths()
    library_paths = config.get_all_library_paths()

    logger.info("System Configuration")
    logger.info(
        f"  Downloads: {len([p for p in download_paths.values() if p and p != Path('')])} configured")
    logger.info(
        f"  Libraries: {len([p for p in library_paths.values() if p and p != Path('')])} configured")
    logger.info(f"  Database: {config.database_path}")
    logger.info(
        f"  Dry-Run: {os.getenv('DRY_RUN_MODE', 'false').lower() == 'true'}")


def set_console_log_level(level: int = logging.WARNING):
    for logger_name in logging.root.manager.loggerDict:
        logger_obj = logging.getLogger(logger_name)
        for handler in logger_obj.handlers:
            if isinstance(handler, RichHandler):
                handler.setLevel(level)


def is_verbose_logging() -> bool:
    return os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"
