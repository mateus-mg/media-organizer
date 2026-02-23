#!/usr/bin/env python3
"""
Centralized logging configuration for Media Organization System

Clean, structured logging with simple symbols (no emojis).
Follows the same principles as Music Automation System.
"""

from typing import Optional, Dict, Any, List
import logging
import os
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.logging import RichHandler
from logging.handlers import RotatingFileHandler

console = Console()

# Log symbols (simple, clean - no emojis)
SYMBOLS = {
    'success': '✓',
    'error': '✗',
    'warning': '!',
    'info': '',
    'organize': '',
    'movie': '',
    'tv': '',
    'anime': '',
    'dorama': '',
    'music': '',
    'book': '',
    'comic': '',
    'database': '',
    'tmdb': '',
    'qbittorrent': '',
    'cleanup': '',
    'progress': '',
    'time': '',
    'stats': '',
    'conflict': '',
    'subtitle': '',
}


class MediaOrganizerLogger:
    """Centralized logger for Media Organization System"""

    def __init__(self, name: str = "MediaOrganizer", log_file: Optional[str] = None,
                 dry_run: bool = False):
        self.name = name
        self.dry_run = dry_run
        self.logger = logging.getLogger(name)

        # Avoid duplicate handlers
        if self.logger.handlers:
            return

        # Get log level from environment or default to INFO
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))

        # Console handler with Rich
        console_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            markup=False  # Disable markup to avoid parsing issues
        )
        console_handler.setLevel(logging.WARNING)  # Default to WARNING, CLI can override
        console_format = logging.Formatter(
            "%(message)s",
            datefmt="[%X]"
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)

        # File handler with rotation
        if log_file is None:
            log_file = os.getenv('LOG_FILE', './logs/organizer.log')

        log_path = Path(log_file)
        log_path.parent.mkdir(exist_ok=True)

        # Use rotating file handler with max size of 50MB and up to 5 backup files
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=50*1024*1024,  # 50MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)

    def get_logger(self):
        """Return the configured logger"""
        return self.logger

    @staticmethod
    def format_message(symbol_key: str, message: str) -> str:
        """Format message with symbol"""
        symbol = SYMBOLS.get(symbol_key, '')
        return f"{symbol} {message}" if symbol else message


def get_logger(name: str = "MediaOrganizer", dry_run: bool = False) -> logging.Logger:
    """Get or create a logger instance"""
    return MediaOrganizerLogger(name, dry_run=dry_run).get_logger()


# Convenience functions for formatted logging
def log_success(logger: logging.Logger, message: str):
    """Log success message"""
    logger.info(MediaOrganizerLogger.format_message('success', message))


def log_error(logger: logging.Logger, message: str):
    """Log error message"""
    logger.error(MediaOrganizerLogger.format_message('error', message))


def log_warning(logger: logging.Logger, message: str):
    """Log warning message"""
    logger.warning(MediaOrganizerLogger.format_message('warning', message))


def log_info(logger: logging.Logger, message: str):
    """Log info message"""
    logger.info(MediaOrganizerLogger.format_message('info', message))


def log_organize(logger: logging.Logger, message: str):
    """Log organization operation message"""
    logger.info(MediaOrganizerLogger.format_message('organize', message))


def log_movie(logger: logging.Logger, message: str):
    """Log movie operation message"""
    logger.info(MediaOrganizerLogger.format_message('movie', message))


def log_tv(logger: logging.Logger, message: str):
    """Log TV show operation message"""
    logger.info(MediaOrganizerLogger.format_message('tv', message))


def log_anime(logger: logging.Logger, message: str):
    """Log anime operation message"""
    logger.info(MediaOrganizerLogger.format_message('anime', message))


def log_dorama(logger: logging.Logger, message: str):
    """Log dorama operation message"""
    logger.info(MediaOrganizerLogger.format_message('dorama', message))


def log_music(logger: logging.Logger, message: str):
    """Log music operation message"""
    logger.info(MediaOrganizerLogger.format_message('music', message))


def log_book(logger: logging.Logger, message: str):
    """Log book operation message"""
    logger.info(MediaOrganizerLogger.format_message('book', message))


def log_comic(logger: logging.Logger, message: str):
    """Log comic operation message"""
    logger.info(MediaOrganizerLogger.format_message('comic', message))


def log_database(logger: logging.Logger, message: str):
    """Log database operation message"""
    logger.info(MediaOrganizerLogger.format_message('database', message))


def log_tmdb(logger: logging.Logger, message: str):
    """Log TMDB operation message"""
    logger.info(MediaOrganizerLogger.format_message('tmdb', message))


def log_qbittorrent(logger: logging.Logger, message: str):
    """Log qBittorrent operation message"""
    logger.info(MediaOrganizerLogger.format_message('qbittorrent', message))


def log_conflict(logger: logging.Logger, message: str):
    """Log conflict resolution message"""
    logger.info(MediaOrganizerLogger.format_message('conflict', message))


def log_subtitle(logger: logging.Logger, message: str):
    """Log subtitle operation message"""
    logger.info(MediaOrganizerLogger.format_message('subtitle', message))


def log_progress(logger: logging.Logger, message: str):
    """Log progress message"""
    logger.info(MediaOrganizerLogger.format_message('progress', message))


def log_time(logger: logging.Logger, message: str):
    """Log time-related message"""
    logger.info(MediaOrganizerLogger.format_message('time', message))


def log_stats(logger: logging.Logger, message: str):
    """Log statistics message"""
    logger.info(MediaOrganizerLogger.format_message('stats', message))


def log_debug(logger: logging.Logger, message: str):
    """Log debug message"""
    logger.debug(message)


# ============================================================================
# STRUCTURED LOGGING - Consolidated log functions
# ============================================================================

def log_structured(logger: logging.Logger, lines: List[str]):
    """
    Log multiple structured lines

    Args:
        logger: Logger instance
        lines: List of lines to log
    """
    for line in lines:
        if line:  # Ignore empty lines
            logger.info(line)


def log_organization_start(logger: logging.Logger, directory: Path, media_type: str = "all"):
    """
    Log organization start
    
    Format:
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        ORGANIZATION START - /path/to/downloads
        Media Type: all | Mode: Normal
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    from log_formatter import LogSection
    
    title = f"ORGANIZATION START - {directory}"
    subtitle = f"Media Type: {media_type} | Mode: Dry-Run" if os.getenv('DRY_RUN_MODE', 'false').lower() == 'true' else f"Media Type: {media_type} | Mode: Normal"
    
    lines = LogSection.major_header(title, subtitle)
    log_structured(logger, lines)


def log_organization_complete(logger: logging.Logger, organized: int, skipped: int,
                               failed: int, duration_seconds: float):
    """
    Log organization complete summary
    
    Format:
        Organization Complete: 45 organized | 12 skipped | 3 failed | Duration: 2m 34s
    """
    from log_formatter import LogSection
    
    # Format duration
    hours = int(duration_seconds // 3600)
    minutes = int((duration_seconds % 3600) // 60)
    seconds = int(duration_seconds % 60)
    
    if hours > 0:
        duration_str = f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        duration_str = f"{minutes}m {seconds}s"
    else:
        duration_str = f"{seconds}s"
    
    message = f"Organization Complete: {organized} organized | {skipped} skipped | {failed} failed | Duration: {duration_str}"
    logger.info(LogSection.SEP_MINOR)
    logger.info(message)
    logger.info(LogSection.SEP_MINOR)


def log_movie_organized(logger: logging.Logger, title: str, year: int,
                        tmdb_id: int, dest_path: Path):
    """
    Log movie organization
    
    Format:
        → Movie Title (2020)
          TMDB ID: 12345 | movies/Movie Title (2020) [tmdbid-12345]/
    """
    from log_formatter import LogSection
    
    details = f"TMDB ID: {tmdb_id} | {dest_path.parent}"
    lines = LogSection.download_item(f"{title} ({year})", "", details)
    log_structured(logger, lines)


def log_tv_organized(logger: logging.Logger, series: str, season: int,
                     episode: int, tmdb_id: int, dest_path: Path):
    """
    Log TV episode organization
    
    Format:
        → Series Name S01E01
          TMDB ID: 67890 | tv/Series Name (2020) [tmdbid-67890]/Season 01/
    """
    from log_formatter import LogSection
    
    details = f"TMDB ID: {tmdb_id} | {dest_path.parent}"
    lines = LogSection.download_item(f"{series} S{season:02d}E{episode:02d}", "", details)
    log_structured(logger, lines)


def log_music_organized(logger: logging.Logger, artist: str, album: str,
                        track: str, dest_path: Path):
    """
    Log music organization
    
    Format:
        → Artist - Track
          Album: Album Name | musics/Artist/Album/
    """
    from log_formatter import LogSection
    
    details = f"Album: {album} | {dest_path.parent}"
    lines = LogSection.download_item(artist, track, details)
    log_structured(logger, lines)


def log_book_organized(logger: logging.Logger, title: str, author: str,
                       dest_path: Path):
    """
    Log book organization
    
    Format:
        → Book Title
          Author: Author Name | books/Author/Title/
    """
    from log_formatter import LogSection
    
    details = f"Author: {author} | {dest_path.parent}"
    lines = LogSection.download_item(title, "", details)
    log_structured(logger, lines)


def log_conflict_detected(logger: logging.Logger, file_path: Path,
                          strategy: str, resolution: str):
    """
    Log conflict detection
    
    Format:
        ! Conflict: filename.mkv (strategy: skip, resolution: skipped)
    """
    message = f"Conflict: {file_path.name} (strategy: {strategy}, resolution: {resolution})"
    log_warning(logger, message)


def log_tmdb_lookup(logger: logging.Logger, title: str, year: Optional[int],
                    tmdb_id: Optional[int], found: bool):
    """
    Log TMDB lookup
    
    Format:
        TMDB Lookup: Movie Title (2020) → ID: 12345
        TMDB Lookup: Movie Title (2020) → Not found
    """
    if found and tmdb_id:
        message = f"TMDB Lookup: {title} ({year or 'N/A'}) → ID: {tmdb_id}"
    else:
        message = f"TMDB Lookup: {title} ({year or 'N/A'}) → Not found"
    
    log_tmdb(logger, message)


def log_subtitle_moved(logger: logging.Logger, subtitle_path: Path,
                       video_dest: Path):
    """
    Log subtitle move operation
    
    Format:
        Subtitle: subtitle.srt → video_dest/
    """
    message = f"Subtitle: {subtitle_path.name} → {video_dest.parent}/"
    log_subtitle(logger, message)


def log_system_startup(logger: logging.Logger, config: Any, stats: Dict[str, Any]):
    """
    Log system startup summary
    
    Args:
        logger: Logger instance
        config: Config object
        stats: Statistics dictionary
    """
    from log_formatter import LogSection
    
    # Check paths
    download_paths = config.get_all_download_paths()
    library_paths = config.get_all_library_paths()
    
    paths_info = {
        'Downloads': f"{len([p for p in download_paths.values() if p and p != Path('')])} configured",
        'Libraries': f"{len([p for p in library_paths.values() if p and p != Path('')])} configured",
        'Database': str(config.database_path),
        'Dry-Run': os.getenv('DRY_RUN_MODE', 'false').lower() == 'true'
    }
    
    lines = LogSection.section("System Configuration", paths_info)
    log_structured(logger, lines)


def set_console_log_level(level: int = logging.WARNING):
    """
    Set console logging level for all loggers
    
    Args:
        level: logging level (logging.WARNING, logging.ERROR, etc.)
    
    Use this to suppress INFO logs from console when running CLI commands.
    File logging will continue to capture all levels.
    """
    for logger_name in logging.root.manager.loggerDict:
        logger_obj = logging.getLogger(logger_name)
        
        for handler in logger_obj.handlers:
            if isinstance(handler, RichHandler):
                handler.setLevel(level)


def is_verbose_logging() -> bool:
    """Check if verbose logging is enabled (DEBUG level)"""
    return os.getenv('LOG_LEVEL', 'INFO').upper() == 'DEBUG'
