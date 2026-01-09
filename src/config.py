"""
Configuration module for Media Organization System
Loads and validates settings from .env file
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv


class Config:
    """Configuration manager for the application"""

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

        self._validate_required_paths()

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
    def library_path_audiobooks(self) -> Path:
        return Path(os.getenv("LIBRARY_PATH_AUDIOBOOKS", ""))

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
    def download_path_audiobooks(self) -> Path:
        return Path(os.getenv("DOWNLOAD_PATH_AUDIOBOOKS", ""))

    @property
    def download_path_comics(self) -> Path:
        return Path(os.getenv("DOWNLOAD_PATH_COMICS", ""))

    @property
    def download_path_torrents(self) -> Path:
        return Path(os.getenv("DOWNLOAD_PATH_TORRENTS", ""))

    # ========== TMDB API ==========
    @property
    def tmdb_api_key(self) -> str:
        return os.getenv("TMDB_API_KEY", "")

    @property
    def tmdb_use_fallback_parsing(self) -> bool:
        return os.getenv("TMDB_USE_FALLBACK_PARSING", "true").lower() == "true"

    # ========== Music Automation ==========
    @property
    def music_automation_db_path(self) -> Path:
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
        Example: "/media/downloads:/host/downloads,/downloads:/host/downloads"

        Returns:
            Dict mapping container paths to host paths
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
        """
        Get list of qBittorrent categories to ignore (case-insensitive)

        Returns:
            List of category names to skip during organization
        """
        categories = os.getenv(
            "QBITTORRENT_IGNORED_CATEGORIES", "outros,others,other")
        return [c.strip().lower() for c in categories.split(",") if c.strip()]

    # ========== Rate Limiting ==========
    @property
    def max_concurrent_file_ops(self) -> int:
        return int(os.getenv("MAX_CONCURRENT_FILE_OPS", "3"))

    @property
    def max_concurrent_api_calls(self) -> int:
        return int(os.getenv("MAX_CONCURRENT_API_CALLS", "2"))

    @property
    def tmdb_rate_limit_per_second(self) -> float:
        return float(os.getenv("TMDB_RATE_LIMIT_PER_SECOND", "4"))

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

    # ========== Helper Methods ==========

    def get_all_download_paths(self) -> Dict[str, Path]:
        """Get all download paths as a dictionary"""
        return {
            "movies": self.download_path_movies,
            "tv": self.download_path_tv,
            "animes": self.download_path_animes,
            "doramas": self.download_path_doramas,
            "music": self.download_path_music,
            "books": self.download_path_books,
        }

    def get_all_library_paths(self) -> Dict[str, Path]:
        """Get all library paths as a dictionary"""
        return {
            "movies": self.library_path_movies,
            "tv": self.library_path_tv,
            "animes": self.library_path_animes,
            "doramas": self.library_path_doramas,
            "music": self.library_path_music,
            "books": self.library_path_books,
        }

    def _validate_required_paths(self):
        """Validate that required paths exist (warning only, not fatal)"""
        paths_to_check = {
            **self.get_all_download_paths(),
            **self.get_all_library_paths()
        }

        # Note: We don't raise errors here to allow dry-run mode
        # Validation will be more strict when actually running operations
        for name, path in paths_to_check.items():
            if path and not path.exists():
                # Just a note, will be logged by logger when initialized
                pass

    def is_valid(self) -> tuple[bool, list[str]]:
        """
        Check if configuration is valid

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

        return len(errors) == 0, errors


# Global config instance
config = Config()
