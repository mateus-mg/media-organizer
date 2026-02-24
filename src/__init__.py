"""
Media Organization System

Consolidated module structure:
- config: Configuration management
- core: Types, interfaces, validators, orchestrator
- detection: Media classification and file scanning
- integrations: TMDB, QBittorrent, file completion validation
- organizers: All media organizers (movie, tv, music, book)
- persistence: Database operations
- utils: Logging, conflict handling, concurrency, helpers
- metadata: Metadata extraction and enrichment

Usage:
    from src import Config, MediaOrganizerOrchestrator
    from src.organizers import MovieOrganizer, TVOrganizer
    from src.integrations import get_tmdb_id_for_movie
"""

__version__ = "2.0.0"
__author__ = "Media Organizer Team"

# Configuration
from src.config import Config

# Core types and interfaces
from src.core import (
    MediaType,
    ValidationResult,
    FileMetadata,
    OrganizationResult,
    ProcessedFile,
    ValidatorInterface,
    OrganizadorInterface,
    DatabaseInterface,
    MediaClassifierInterface,
    FileScannerInterface,
    Orquestrador,
    FileExistenceValidator,
    FileTypeValidator,
    IncompleteFileValidator,
    JunkFileValidator,
)

# Detection
from src.detection import MediaClassifier, FileScanner, FileAnalyzer

# Integrations
from src.integrations import (
    TMDBClient,
    TMDBResult,
    get_tmdb_id_for_movie,
    get_tmdb_id_for_tv_show,
    extract_year_from_directory,
    FileCompletionValidator,
    QBittorrentClient,
    QBittorrentValidator,
)

# Organizers
from src.organizers import (
    BaseOrganizer,
    MovieOrganizer,
    TVOrganizer,
    MusicOrganizer,
    BookOrganizer,
    CalibreManager,
)

# Persistence
from src.persistence import OrganizationDatabase, UnorganizedDatabase, format_datetime_br

# Utils
from src.log_config import (
    get_logger,
    log_success, log_error, log_warning, log_info,
    log_organize, log_movie, log_tv, log_anime, log_dorama,
    log_music, log_book, log_comic, log_database, log_tmdb,
    log_qbittorrent, log_conflict, log_subtitle, log_progress,
    log_stats, log_debug,
    set_console_log_level,
)
from src.utils import (
    ConflictHandler,
    ConflictResolution,
    ConcurrencyManager,
    FileOperations,
    calculate_partial_hash,
    calculate_file_hash,
    normalize_title,
    normalize_movie_filename,
    normalize_tv_filename,
    normalize_comic_filename,
    move_subtitles_with_video,
)

# Metadata
from src.metadata import (
    extract_audio_metadata,
    enrich_book_metadata_with_online_sources,
    enrich_music_metadata_with_online_sources,
    MetadataParser,
    MetadataResult,
)

# Subtitle Downloader (OpenSubtitles)
from src.subtitle_config import SubtitleConfig, get_config
from src.subtitle_downloader import OpenSubtitlesClient, SubtitleDownloader
from src.subtitle_daemon import SubtitleDaemon


__all__ = [
    # Version
    "__version__",
    
    # Config
    "Config",
    
    # Core types
    "MediaType",
    "ValidationResult",
    "FileMetadata",
    "OrganizationResult",
    "ProcessedFile",
    
    # Core interfaces
    "ValidatorInterface",
    "OrganizadorInterface",
    "DatabaseInterface",
    "MediaClassifierInterface",
    "FileScannerInterface",
    
    # Core orchestrator
    "Orquestrador",
    
    # Core validators
    "FileExistenceValidator",
    "FileTypeValidator",
    "IncompleteFileValidator",
    "JunkFileValidator",
    
    # Detection
    "MediaClassifier",
    "FileScanner",
    "FileAnalyzer",
    
    # Integrations
    "TMDBClient",
    "TMDBResult",
    "get_tmdb_id_for_movie",
    "get_tmdb_id_for_tv_show",
    "extract_year_from_directory",
    "FileCompletionValidator",
    "QBittorrentClient",
    "QBittorrentValidator",
    
    # Organizers
    "BaseOrganizer",
    "MovieOrganizer",
    "TVOrganizer",
    "MusicOrganizer",
    "BookOrganizer",
    "CalibreManager",
    
    # Persistence
    "OrganizationDatabase",
    "UnorganizedDatabase",
    "format_datetime_br",
    
    # Utils
    "get_logger",
    "log_success", "log_error", "log_warning", "log_info",
    "log_organize", "log_movie", "log_tv", "log_anime", "log_dorama",
    "log_music", "log_book", "log_comic", "log_database", "log_tmdb",
    "log_qbittorrent", "log_conflict", "log_subtitle", "log_progress",
    "log_stats", "log_debug",
    "set_console_log_level",
    "ConflictHandler",
    "ConflictResolution",
    "ConcurrencyManager",
    "FileOperations",
    "calculate_partial_hash",
    "calculate_file_hash",
    "normalize_title",
    "normalize_movie_filename",
    "normalize_tv_filename",
    "normalize_comic_filename",
    "move_subtitles_with_video",
    
    # Metadata
    "extract_audio_metadata",
    "enrich_book_metadata_with_online_sources",
    "enrich_music_metadata_with_online_sources",
    "MetadataParser",
    "MetadataResult",
    
    # Subtitle Downloader (OpenSubtitles)
    "SubtitleConfig",
    "get_config",
    "OpenSubtitlesClient",
    "SubtitleDownloader",
    "SubtitleDaemon",
]
