"""
Configuration module for Media Organization System.

The active scope includes only music, books, and comics.
"""
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv


class Config:
    """Unified configuration manager for the current media scope."""

    def __init__(self, env_file: Optional[str] = None):
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

    @property
    def library_path_music(self) -> Path:
        return Path(os.getenv("LIBRARY_PATH_MUSIC", ""))

    @property
    def library_path_books(self) -> Path:
        return Path(os.getenv("LIBRARY_PATH_BOOKS", ""))

    @property
    def library_path_comics(self) -> Path:
        return Path(os.getenv("LIBRARY_PATH_COMICS", ""))

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

    @property
    def calibre_library_path(self) -> Optional[Path]:
        path = os.getenv("CALIBRE_LIBRARY_PATH", "")
        return Path(path) if path else None

    @property
    def calibre_enabled(self) -> bool:
        return os.getenv("CALIBRE_ENABLED", "false").lower() == "true"

    @property
    def max_concurrent_file_ops(self) -> int:
        return int(os.getenv("MAX_CONCURRENT_FILE_OPS", "3"))

    @property
    def max_concurrent_api_calls(self) -> int:
        return int(os.getenv("MAX_CONCURRENT_API_CALLS", "2"))

    @property
    def file_op_delay_ms(self) -> int:
        return int(os.getenv("FILE_OP_DELAY_MS", "100"))

    @property
    def dry_run_mode(self) -> bool:
        return os.getenv("DRY_RUN_MODE", "false").lower() == "true"

    @property
    def dry_run_log_level(self) -> str:
        return os.getenv("DRY_RUN_LOG_LEVEL", "INFO").upper()

    @property
    def health_check_enabled(self) -> bool:
        return os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true"

    @property
    def health_check_host(self) -> str:
        return os.getenv("HEALTH_CHECK_HOST", "127.0.0.1")

    @property
    def health_check_port(self) -> int:
        return int(os.getenv("HEALTH_CHECK_PORT", "8765"))

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

    @property
    def check_interval(self) -> int:
        return int(os.getenv("CHECK_INTERVAL", "3600"))

    @property
    def organization_check_interval(self) -> int:
        return int(os.getenv("ORGANIZATION_CHECK_INTERVAL", "300"))

    @property
    def processing_priority_music(self) -> int:
        return int(os.getenv("PROCESSING_PRIORITY_MUSIC", "1"))

    @property
    def processing_priority_books(self) -> int:
        return int(os.getenv("PROCESSING_PRIORITY_BOOKS", "2"))

    @property
    def processing_priority_comics(self) -> int:
        return int(os.getenv("PROCESSING_PRIORITY_COMICS", "3"))

    @property
    def database_path(self) -> Path:
        return Path(os.getenv("DATABASE_PATH", "./data/organization.json"))

    @property
    def database_backup_enabled(self) -> bool:
        return os.getenv("DATABASE_BACKUP_ENABLED", "true").lower() == "true"

    @property
    def database_backup_keep_days(self) -> int:
        return int(os.getenv("DATABASE_BACKUP_KEEP_DAYS", "7"))

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

    @property
    def lastfm_api_key(self) -> str:
        return os.getenv("LASTFM_API_KEY", "")

    @property
    def google_books_api_key(self) -> str:
        return os.getenv("GOOGLE_BOOKS_API_KEY", "")

    @property
    def enrich_book_metadata(self) -> bool:
        return os.getenv("ENRICH_BOOK_METADATA", "true").lower() == "true"

    @property
    def enrich_book_metadata_online(self) -> bool:
        return os.getenv("ENRICH_BOOK_METADATA_ONLINE", "false").lower() == "true"

    @property
    def enrich_book_metadata_google_books(self) -> bool:
        return os.getenv("ENRICH_BOOK_METADATA_GOOGLE_BOOKS", "true").lower() == "true"

    @property
    def book_cover_update_enabled(self) -> bool:
        return os.getenv("BOOK_UPDATE_COVERS", "false").lower() == "true"

    @property
    def book_cover_min_match_score(self) -> int:
        return int(os.getenv("BOOK_COVER_MIN_MATCH_SCORE", "80"))

    @property
    def book_metadata_trust_mode(self) -> str:
        """Metadata trust strategy for books.

        - missing_only: preserve existing tags and only fill gaps (default)
        - replace_with_online: when online lookup is reliable, overwrite core
          book fields with provider data to avoid polluted embedded metadata.
        """
        mode = os.getenv("BOOK_METADATA_TRUST_MODE",
                         "missing_only").strip().lower()
        if mode not in {"missing_only", "replace_with_online"}:
            return "missing_only"
        return mode

    @property
    def epub_rewrite_with_ebooklib(self) -> bool:
        return os.getenv("EPUB_REWRITE_WITH_EBOOKLIB", "false").lower() == "true"

    @property
    def infer_genre_from_source_path(self) -> bool:
        return os.getenv("INFER_GENRE_FROM_SOURCE_PATH", "false").lower() == "true"

    @property
    def convert_pdf_to_epub(self) -> bool:
        return os.getenv("CONVERT_PDF_TO_EPUB", "false").lower() == "true"

    @property
    def book_format_priority(self) -> List[str]:
        priority = os.getenv("BOOK_FORMAT_PRIORITY", "epub,mobi,azw3,azw,pdf")
        return [fmt.strip().lower().lstrip(".") for fmt in priority.split(",")]

    @property
    def enrich_music_metadata_online(self) -> bool:
        return os.getenv("ENRICH_MUSIC_METADATA_ONLINE", "false").lower() == "true"

    @property
    def music_genre_complement_enabled(self) -> bool:
        return os.getenv("MUSIC_GENRE_COMPLEMENT_ENABLED", "true").lower() == "true"

    @property
    def music_genre_complement_max_existing_genres(self) -> int:
        try:
            value = int(
                os.getenv("MUSIC_GENRE_COMPLEMENT_MAX_EXISTING_GENRES", "1"))
        except ValueError:
            value = 1
        return max(value, 0)

    @property
    def music_genre_complement_max_total_genres(self) -> int:
        try:
            value = int(
                os.getenv("MUSIC_GENRE_COMPLEMENT_MAX_TOTAL_GENRES", "4"))
        except ValueError:
            value = 4
        return max(value, 1)

    @property
    def music_metadata_api_delay_seconds(self) -> float:
        """Base delay between metadata API calls.

        Service-specific floors are enforced in metadata module.
        """
        try:
            value = float(os.getenv("MUSIC_METADATA_API_DELAY_SECONDS", "1.1"))
        except ValueError:
            value = 1.1
        return max(value, 0.0)

    @property
    def music_metadata_api_max_retries(self) -> int:
        try:
            value = int(os.getenv("MUSIC_METADATA_API_MAX_RETRIES", "4"))
        except ValueError:
            value = 4
        return max(value, 0)

    @property
    def music_metadata_api_timeout_seconds(self) -> float:
        """Timeout for metadata API requests (MusicBrainz, Last.fm)."""
        try:
            value = float(
                os.getenv("MUSIC_METADATA_API_TIMEOUT_SECONDS", "20.0"))
        except ValueError:
            value = 20.0
        return max(value, 5.0)  # Minimum 5 seconds

    @property
    def navidrome_enabled(self) -> bool:
        return os.getenv("NAVIDROME_ENABLED", "false").lower() == "true"

    @property
    def navidrome_base_url(self) -> str:
        return os.getenv("NAVIDROME_BASE_URL", "").strip().rstrip("/")

    @property
    def navidrome_username(self) -> str:
        return os.getenv("NAVIDROME_USERNAME", "").strip()

    @property
    def navidrome_password(self) -> str:
        return os.getenv("NAVIDROME_PASSWORD", "")

    @property
    def navidrome_api_version(self) -> str:
        return os.getenv("NAVIDROME_API_VERSION", "1.16.1").strip() or "1.16.1"

    @property
    def navidrome_client_name(self) -> str:
        return os.getenv("NAVIDROME_CLIENT_NAME", "media-organizer").strip() or "media-organizer"

    @property
    def navidrome_timeout_seconds(self) -> float:
        try:
            value = float(os.getenv("NAVIDROME_TIMEOUT_SECONDS", "20.0"))
        except ValueError:
            value = 20.0
        return max(value, 3.0)

    @property
    def navidrome_verify_tls(self) -> bool:
        return os.getenv("NAVIDROME_VERIFY_TLS", "true").lower() == "true"

    @property
    def navidrome_smart_playlist_dir(self) -> Path:
        # NSP files should be in the music library folder (or subfolder) per Navidrome docs:
        # https://www.navidrome.org/docs/usage/features/smart-playlists/
        env_path = os.getenv("NAVIDROME_SMART_PLAYLIST_DIR", "")
        if env_path:
            return Path(env_path)
        # Default: use music library if available, otherwise use data directory
        music_lib = self.library_path_music
        if music_lib and str(music_lib).strip():
            return music_lib / ".smart_playlists"
        return Path("./data/navidrome/smart_playlists")

    @property
    def navidrome_smart_playlist_auto_scan(self) -> bool:
        return os.getenv("NAVIDROME_SMART_PLAYLIST_AUTO_SCAN", "true").lower() == "true"

    @property
    def navidrome_playlists_state_path(self) -> Path:
        return Path(os.getenv("NAVIDROME_PLAYLISTS_STATE_PATH", "./data/navidrome/playlists_state.json"))

    @property
    def comic_download_covers(self) -> bool:
        return os.getenv("COMIC_DOWNLOAD_COVERS", "true").lower() == "true"

    @property
    def trash_enabled(self) -> bool:
        return os.getenv("TRASH_ENABLED", "true").lower() == "true"

    @property
    def trash_path(self) -> Path:
        return Path(os.getenv("TRASH_PATH", "./data/trash"))

    @property
    def trash_retention_days(self) -> int:
        return int(os.getenv("TRASH_RETENTION_DAYS", "30"))

    @property
    def link_registry_path(self) -> Path:
        return Path(os.getenv("LINK_REGISTRY_PATH", "./data/link_registry.json"))

    @property
    def delete_confirmation_required(self) -> bool:
        return os.getenv("DELETE_CONFIRMATION_REQUIRED", "true").lower() == "true"

    @property
    def delete_dry_run_default(self) -> bool:
        return os.getenv("DELETE_DRY_RUN_DEFAULT", "true").lower() == "true"

    @property
    def quality_monitor_min_tracks_threshold(self) -> int:
        try:
            value = int(os.getenv("QUALITY_MONITOR_MIN_TRACKS_THRESHOLD", "3"))
        except ValueError:
            value = 3
        return max(value, 1)

    @property
    def filename_preview_limit_default(self) -> int:
        try:
            value = int(os.getenv("FILENAME_PREVIEW_LIMIT_DEFAULT", "30"))
        except ValueError:
            value = 30
        return max(value, 0)

    @property
    def quality_dashboard_top_n_default(self) -> int:
        try:
            value = int(os.getenv("QUALITY_DASHBOARD_TOP_N_DEFAULT", "10"))
        except ValueError:
            value = 10
        return max(value, 1)

    @property
    def quality_monitor_expect_artist_in_filename(self) -> bool:
        return os.getenv("QUALITY_MONITOR_EXPECT_ARTIST_IN_FILENAME", "false").lower() == "true"

    def get_all_download_paths(self) -> Dict[str, Path]:
        return {
            "music": self.download_path_music,
            "books": self.download_path_books,
            "comics": self.download_path_comics,
        }

    def get_all_library_paths(self) -> Dict[str, Path]:
        return {
            "music": self.library_path_music,
            "books": self.library_path_books,
            "comics": self.library_path_comics,
        }

    def is_valid(self) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not self.database_path:
            errors.append("DATABASE_PATH is not set")

        download_paths = self.get_all_download_paths()
        if not any(path and path != Path("") for path in download_paths.values()):
            errors.append("No download paths configured")

        library_paths = self.get_all_library_paths()
        if not any(path and path != Path("") for path in library_paths.values()):
            errors.append("No library paths configured")

        if self.navidrome_enabled:
            if not self.navidrome_base_url:
                errors.append(
                    "NAVIDROME_BASE_URL is required when NAVIDROME_ENABLED=true")
            if not self.navidrome_username:
                errors.append(
                    "NAVIDROME_USERNAME is required when NAVIDROME_ENABLED=true")
            if not self.navidrome_password:
                errors.append(
                    "NAVIDROME_PASSWORD is required when NAVIDROME_ENABLED=true")

        return len(errors) == 0, errors
