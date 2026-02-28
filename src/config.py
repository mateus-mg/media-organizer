"""
Configuration module for Media Organization System

Consolidated configuration manager - all settings loaded from .env file.
Paths are automatically converted to Path objects.

Usage:
    from src.config import Config
    config = Config()
    print(config.library_path_movies)
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv


class Config:
    """
    Unified configuration manager for Media Organization System.
    
    All configuration is loaded from .env file and exposed via properties.
    Boolean values are parsed from strings ("true"/"false").
    Numeric values are parsed from strings.
    Paths are converted to Path objects.
    """
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration
        
        Args:
            env_file: Path to .env file (default: .env in project root)
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
    
    # ========== Library Paths ==========
    @property
    def library_path_movies(self) -> Path:
        return Path(os.getenv("LIBRARY_PATH_MOVIES", ""))
    
    @property
    def library_path_tv(self) -> Path:
        return Path(os.getenv("LIBRARY_PATH_TV", ""))
    
    @property
    def library_path_animes(self) -> Path:
        return Path(os.getenv("LIBRARY_PATH_ANIMES", ""))
    
    @property
    def library_path_doramas(self) -> Path:
        return Path(os.getenv("LIBRARY_PATH_DORAMAS", ""))
    
    @property
    def library_path_music(self) -> Path:
        return Path(os.getenv("LIBRARY_PATH_MUSIC", ""))
    
    @property
    def library_path_books(self) -> Path:
        return Path(os.getenv("LIBRARY_PATH_BOOKS", ""))
    
    @property
    def library_path_comics(self) -> Path:
        return Path(os.getenv("LIBRARY_PATH_COMICS", ""))
    
    # ========== Download Paths ==========
    @property
    def download_path_movies(self) -> Path:
        return Path(os.getenv("DOWNLOAD_PATH_MOVIES", ""))
    
    @property
    def download_path_tv(self) -> Path:
        return Path(os.getenv("DOWNLOAD_PATH_TV", ""))
    
    @property
    def download_path_animes(self) -> Path:
        return Path(os.getenv("DOWNLOAD_PATH_ANIMES", ""))
    
    @property
    def download_path_doramas(self) -> Path:
        return Path(os.getenv("DOWNLOAD_PATH_DORAMAS", ""))
    
    @property
    def download_path_music(self) -> Path:
        return Path(os.getenv("DOWNLOAD_PATH_MUSIC", ""))
    
    @property
    def download_path_books(self) -> Path:
        return Path(os.getenv("DOWNLOAD_PATH_BOOKS", ""))
    
    @property
    def download_path_comics(self) -> Path:
        return Path(os.getenv("DOWNLOAD_PATH_COMICS", ""))
    
    @property
    def download_path_torrents(self) -> Path:
        return Path(os.getenv("DOWNLOAD_PATH_TORRENTS", ""))
    
    # ========== Calibre Integration ==========
    @property
    def calibre_library_path(self) -> Optional[Path]:
        """Path to Calibre library"""
        path = os.getenv("CALIBRE_LIBRARY_PATH", "")
        return Path(path) if path else None
    
    @property
    def calibre_enabled(self) -> bool:
        """Enable Calibre integration"""
        return os.getenv("CALIBRE_ENABLED", "false").lower() == "true"
    
    # ========== Music Automation ==========
    @property
    def music_automation_db_path(self) -> Path:
        """Path to Music Automation downloaded.json"""
        path = os.getenv("MUSIC_AUTOMATION_DB_PATH", "")
        return Path(path) if path else Path("")
    
    # ========== qBittorrent ==========
    @property
    def qbittorrent_enabled(self) -> bool:
        return os.getenv("QBITTORRENT_ENABLED", "false").lower() == "true"
    
    @property
    def qbittorrent_host(self) -> str:
        return os.getenv("QBITTORRENT_HOST", "http://localhost:8080")
    
    @property
    def qbittorrent_username(self) -> str:
        return os.getenv("QBITTORRENT_USERNAME", "")
    
    @property
    def qbittorrent_password(self) -> str:
        return os.getenv("QBITTORRENT_PASSWORD", "")
    
    @property
    def qbittorrent_watch_folder(self) -> Path:
        return Path(os.getenv("QBITTORRENT_WATCH_FOLDER", ""))
    
    @property
    def qbittorrent_check_completion(self) -> bool:
        return os.getenv("QBITTORRENT_CHECK_COMPLETION", "true").lower() == "true"
    
    @property
    def qbittorrent_states_to_process(self) -> list:
        states = os.getenv("QBITTORRENT_STATES_TO_PROCESS", "seeding,pausedUP")
        return [s.strip() for s in states.split(",")]
    
    @property
    def qbittorrent_min_progress(self) -> float:
        return float(os.getenv("QBITTORRENT_MIN_PROGRESS", "1.0"))
    
    @property
    def qbittorrent_path_mapping(self) -> Dict[str, str]:
        """
        Get qBittorrent path mapping (container -> host paths)
        Format: "container_path:host_path,container_path2:host_path2"
        """
        mapping_str = os.getenv("QBITTORRENT_PATH_MAPPING", "")
        if not mapping_str:
            return {}
        
        mapping = {}
        for pair in mapping_str.split(","):
            if ":" in pair:
                container_path, host_path = pair.split(":", 1)
                mapping[container_path.strip()] = host_path.strip()
        
        return mapping
    
    @property
    def qbittorrent_ignored_categories(self) -> list:
        """Get list of qBittorrent categories to ignore"""
        categories = os.getenv("QBITTORRENT_IGNORED_CATEGORIES", "outros,others,other")
        return [c.strip().lower() for c in categories.split(",") if c.strip()]
    
    # ========== Rate Limiting ==========
    @property
    def max_concurrent_file_ops(self) -> int:
        return int(os.getenv("MAX_CONCURRENT_FILE_OPS", "3"))
    
    @property
    def max_concurrent_api_calls(self) -> int:
        return int(os.getenv("MAX_CONCURRENT_API_CALLS", "2"))
    
    @property
    def file_op_delay_ms(self) -> int:
        return int(os.getenv("FILE_OP_DELAY_MS", "100"))
    
    # ========== Dry-Run Mode ==========
    @property
    def dry_run_mode(self) -> bool:
        return os.getenv("DRY_RUN_MODE", "false").lower() == "true"
    
    @property
    def dry_run_log_level(self) -> str:
        return os.getenv("DRY_RUN_LOG_LEVEL", "INFO").upper()
    
    # ========== Health Check ==========
    @property
    def health_check_enabled(self) -> bool:
        return os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true"
    
    @property
    def health_check_host(self) -> str:
        return os.getenv("HEALTH_CHECK_HOST", "127.0.0.1")
    
    @property
    def health_check_port(self) -> int:
        return int(os.getenv("HEALTH_CHECK_PORT", "8765"))
    
    # ========== Conflict Resolution ==========
    @property
    def conflict_strategy(self) -> str:
        strategy = os.getenv("CONFLICT_STRATEGY", "skip").lower()
        if strategy not in ["skip", "rename", "overwrite"]:
            return "skip"
        return strategy
    
    @property
    def conflict_rename_pattern(self) -> str:
        return os.getenv("CONFLICT_RENAME_PATTERN", "{name}_{counter}{ext}")
    
    @property
    def conflict_max_attempts(self) -> int:
        return int(os.getenv("CONFLICT_MAX_ATTEMPTS", "100"))
    
    # ========== Scheduling ==========
    @property
    def check_interval(self) -> int:
        """Daemon mode: Interval between automatic checks (seconds)"""
        return int(os.getenv("CHECK_INTERVAL", "3600"))
    
    @property
    def organization_check_interval(self) -> int:
        return int(os.getenv("ORGANIZATION_CHECK_INTERVAL", "300"))
    
    # Processing priorities
    @property
    def processing_priority_movies(self) -> int:
        return int(os.getenv("PROCESSING_PRIORITY_MOVIES", "1"))
    
    @property
    def processing_priority_tv(self) -> int:
        return int(os.getenv("PROCESSING_PRIORITY_TV", "2"))
    
    @property
    def processing_priority_animes(self) -> int:
        return int(os.getenv("PROCESSING_PRIORITY_ANIMES", "3"))
    
    @property
    def processing_priority_doramas(self) -> int:
        return int(os.getenv("PROCESSING_PRIORITY_DORAMAS", "4"))
    
    @property
    def processing_priority_music(self) -> int:
        return int(os.getenv("PROCESSING_PRIORITY_MUSIC", "5"))
    
    @property
    def processing_priority_books(self) -> int:
        return int(os.getenv("PROCESSING_PRIORITY_BOOKS", "9"))
    
    # ========== Database ==========
    @property
    def database_path(self) -> Path:
        return Path(os.getenv("DATABASE_PATH", "./data/organization.json"))
    
    @property
    def database_backup_enabled(self) -> bool:
        return os.getenv("DATABASE_BACKUP_ENABLED", "true").lower() == "true"
    
    @property
    def database_backup_keep_days(self) -> int:
        return int(os.getenv("DATABASE_BACKUP_KEEP_DAYS", "7"))
    
    # ========== Logging ==========
    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO").upper()
    
    @property
    def log_file(self) -> Path:
        return Path(os.getenv("LOG_FILE", "./logs/organizer.log"))
    
    @property
    def log_max_size_mb(self) -> int:
        return int(os.getenv("LOG_MAX_SIZE_MB", "50"))
    
    @property
    def log_backup_count(self) -> int:
        return int(os.getenv("LOG_BACKUP_COUNT", "5"))
    
    # ========== API Keys ==========
    @property
    def tmdb_api_key(self) -> str:
        """TMDB API key"""
        return os.getenv("TMDB_API_KEY", "")
    
    @property
    def lastfm_api_key(self) -> str:
        """Last.fm API key"""
        return os.getenv("LASTFM_API_KEY", "")
    
    # ========== Book Organization ==========
    @property
    def enrich_book_metadata(self) -> bool:
        """Enrich book metadata using Calibre"""
        return os.getenv("ENRICH_BOOK_METADATA", "true").lower() == "true"
    
    @property
    def enrich_book_metadata_online(self) -> bool:
        """Fetch book metadata from online sources"""
        return os.getenv("ENRICH_BOOK_METADATA_ONLINE", "false").lower() == "true"
    
    @property
    def convert_pdf_to_epub(self) -> bool:
        """Convert PDF books to EPUB"""
        return os.getenv("CONVERT_PDF_TO_EPUB", "false").lower() == "true"
    
    @property
    def book_format_priority(self) -> List[str]:
        """Book format priority (highest to lowest)"""
        priority = os.getenv("BOOK_FORMAT_PRIORITY", "epub,mobi,azw3,azw,pdf")
        return [fmt.strip().lower().lstrip('.') for fmt in priority.split(',')]
    
    # ========== Music Organization ==========
    @property
    def enrich_music_metadata_online(self) -> bool:
        """Fetch music metadata from online sources"""
        return os.getenv("ENRICH_MUSIC_METADATA_ONLINE", "false").lower() == "true"
    
    # ========== Comic Organization ==========
    @property
    def comic_fetch_metadata(self) -> bool:
        """Fetch comic metadata from online sources"""
        return os.getenv("COMIC_FETCH_METADATA", "true").lower() == "true"
    
    @property
    def comic_metadata_source(self) -> str:
        """Source for comic metadata"""
        return os.getenv("COMIC_METADATA_SOURCE", "comicvine")
    
    @property
    def comic_download_covers(self) -> bool:
        """Download comic covers automatically"""
        return os.getenv("COMIC_DOWNLOAD_COVERS", "true").lower() == "true"

    # ========== Trash & Deletion ==========
    @property
    def trash_enabled(self) -> bool:
        """Enable trash system"""
        return os.getenv("TRASH_ENABLED", "true").lower() == "true"

    @property
    def trash_path(self) -> Path:
        """Path to trash directory"""
        path = os.getenv("TRASH_PATH", "./data/trash")
        return Path(path)

    @property
    def trash_retention_days(self) -> int:
        """Days to keep items in trash"""
        return int(os.getenv("TRASH_RETENTION_DAYS", "30"))

    @property
    def link_registry_path(self) -> Path:
        """Path to link registry database"""
        path = os.getenv("LINK_REGISTRY_PATH", "./data/link_registry.json")
        return Path(path)

    @property
    def delete_confirmation_required(self) -> bool:
        """Require confirmation for permanent deletion"""
        return os.getenv("DELETE_CONFIRMATION_REQUIRED", "true").lower() == "true"

    @property
    def delete_dry_run_default(self) -> bool:
        """Default to dry-run mode for deletions"""
        return os.getenv("DELETE_DRY_RUN_DEFAULT", "true").lower() == "true"

    # ========== Helper Methods ==========
    
    def get_all_download_paths(self) -> Dict[str, Path]:
        """Get all download paths as dictionary"""
        return {
            "movies": self.download_path_movies,
            "tv": self.download_path_tv,
            "animes": self.download_path_animes,
            "doramas": self.download_path_doramas,
            "music": self.download_path_music,
            "books": self.download_path_books,
            "comics": self.download_path_comics
        }
    
    def get_all_library_paths(self) -> Dict[str, Path]:
        """Get all library paths as dictionary"""
        return {
            "movies": self.library_path_movies,
            "tv": self.library_path_tv,
            "animes": self.library_path_animes,
            "doramas": self.library_path_doramas,
            "music": self.library_path_music,
            "books": self.library_path_books,
            "comics": self.library_path_comics
        }
    
    def is_valid(self) -> tuple[bool, list[str]]:
        """
        Validate configuration
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check critical paths
        if not self.database_path:
            errors.append("DATABASE_PATH is not set")
        
        # Check if at least one download path is configured
        download_paths = self.get_all_download_paths()
        if not any(p and p != Path("") for p in download_paths.values()):
            errors.append("No download paths configured")
        
        # Check if at least one library path is configured
        library_paths = self.get_all_library_paths()
        if not any(p and p != Path("") for p in library_paths.values()):
            errors.append("No library paths configured")
        
        # Validate API keys if features are enabled
        if self.qbittorrent_enabled and not self.qbittorrent_username:
            errors.append("QBITTORRENT_USERNAME required when enabled")
        
        return len(errors) == 0, errors
