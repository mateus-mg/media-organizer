"""
Base organizer class for media files
All specific organizers inherit from this class
"""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from ..config import Config
from ..database import OrganizationDatabase
from ..rate_limiter import RateLimiter
from ..utils.conflict_handler import ConflictHandler, ConflictResolution
from ..utils.file_ops import (
    calculate_file_hash,
    calculate_partial_hash,
    create_hardlink,
    move_subtitles_with_video,
    safe_create_directory,
    get_file_size
)
from ..utils.logger import MediaOrganizerLogger


class OrganizationResult:
    """Result of organization operation"""

    def __init__(self):
        self.success: bool = False
        self.file_path: str = ""
        self.organized_path: str = ""
        self.file_hash: str = ""
        self.conflict_resolution: str = ConflictResolution.NO_CONFLICT
        self.subtitles_moved: List[str] = []
        self.error_message: str = ""
        self.skipped: bool = False
        self.dry_run: bool = False


class BaseOrganizer(ABC):
    """Base class for all media organizers"""

    def __init__(
        self,
        config: Config,
        database: OrganizationDatabase,
        rate_limiter: RateLimiter,
        conflict_handler: ConflictHandler,
        logger: MediaOrganizerLogger,
        dry_run: bool = False
    ):
        """
        Initialize base organizer

        Args:
            config: Configuration object
            database: Database instance
            rate_limiter: Rate limiter instance
            conflict_handler: Conflict handler instance
            logger: Logger instance
            dry_run: If True, only simulate operations
        """
        self.config = config
        self.database = database
        self.rate_limiter = rate_limiter
        self.conflict_handler = conflict_handler
        self.logger = logger
        self.dry_run = dry_run

        # Cache database state to avoid repeated get_stats() calls
        db_stats = self.database.get_stats()
        self._has_organized_files = db_stats.get(
            'total_files_organized', 0) > 0

    @abstractmethod
    async def organize(self, file_path: Path) -> OrganizationResult:
        """
        Organize a media file

        Args:
            file_path: Path to file to organize

        Returns:
            OrganizationResult object
        """
        pass

    @abstractmethod
    def get_destination_path(self, file_path: Path, metadata: Dict) -> Path:
        """
        Determine destination path for organized file

        Args:
            file_path: Source file path
            metadata: Extracted metadata

        Returns:
            Destination path
        """
        pass

    async def check_if_already_organized(self, file_path: Path) -> bool:
        """
        Check if file is already organized using partial hash (fast)

        Args:
            file_path: File path to check

        Returns:
            True if already organized
        """
        # Use partial hash for faster checking
        file_hash = calculate_partial_hash(file_path, chunk_size_mb=1)
        if not file_hash:
            return False

        return self.database.is_already_organized(file_hash)

    async def create_folder_structure(self, folder_path: Path) -> bool:
        """
        Create folder structure for organized media

        Args:
            folder_path: Folder path to create

        Returns:
            True if successful
        """
        if self.dry_run:
            self.logger.dry_run_action(
                "create folder",
                str(folder_path)
            )
            return True

        async with self.rate_limiter.file_operation():
            return safe_create_directory(folder_path, self.dry_run)

    async def organize_file(
        self,
        source: Path,
        dest: Path,
        metadata: Dict
    ) -> OrganizationResult:
        """
        Common organization logic for all media types

        Args:
            source: Source file path
            dest: Destination file path
            metadata: Media metadata

        Returns:
            OrganizationResult
        """
        result = OrganizationResult()
        result.file_path = str(source)
        result.dry_run = self.dry_run

        # Quick check: if destination already exists, skip (avoid hash calculation)
        if dest.exists():
            # Check if it's the same file (same inode = hardlink)
            try:
                if source.stat().st_ino == dest.stat().st_ino:
                    result.skipped = True
                    result.error_message = "Already organized (same file)"
                    self.logger.debug(
                        f"Destination already exists: {dest.name}")
                    return result
            except Exception:
                pass  # Continue to normal processing

        # Calculate file hash ONLY if database has entries (need to check duplicates)
        # Use partial hash (fast) instead of full hash for large files
        file_hash = None
        if self._has_organized_files:
            # Database has entries, use PARTIAL hash for faster duplicate detection
            # Partial hash reads only first+last 1MB chunks (much faster than full file)
            file_hash = calculate_partial_hash(source, chunk_size_mb=1)
            if not file_hash:
                result.error_message = "Failed to calculate file hash"
                return result

            result.file_hash = file_hash

            # Check if already organized in database
            if await self.check_if_already_organized(source):
                result.skipped = True
                result.error_message = "Already organized"
                self.logger.debug(f"Already in database: {source.name}")
                return result
        else:
            # Empty database, use lightweight identifier (path + size + mtime)
            result.file_hash = f"quick-{source.stat().st_size}-{source.stat().st_mtime}"

        # Create destination folder
        dest_folder = dest.parent
        if not await self.create_folder_structure(dest_folder):
            result.error_message = "Failed to create destination folder"
            return result

        # Handle conflicts
        resolved_dest, conflict_action = self.conflict_handler.resolve(
            source, dest, self.dry_run
        )
        result.conflict_resolution = conflict_action
        result.organized_path = str(resolved_dest)

        if conflict_action == ConflictResolution.SKIPPED:
            result.skipped = True
            self.logger.conflict_detected(
                str(dest),
                self.conflict_handler.strategy,
                "Skipped (file exists)"
            )
            return result

        elif conflict_action == ConflictResolution.RENAMED:
            self.logger.conflict_detected(
                str(dest),
                self.conflict_handler.strategy,
                f"Renamed to {resolved_dest.name}"
            )

        elif conflict_action == ConflictResolution.OVERWRITTEN:
            self.logger.conflict_detected(
                str(dest),
                self.conflict_handler.strategy,
                "Overwritten"
            )

        # Create hardlink
        async with self.rate_limiter.file_operation():
            success, error = create_hardlink(
                source, resolved_dest, self.dry_run)

        if not success:
            result.error_message = error
            self.logger.file_operation(
                "hardlink",
                str(source),
                str(resolved_dest),
                success=False,
                dry_run=self.dry_run,
                error_msg=error
            )
            return result

        # Log success
        self.logger.file_operation(
            "hardlink",
            str(source),
            str(resolved_dest),
            success=True,
            dry_run=self.dry_run
        )

        # Move subtitles
        if not self.dry_run:
            moved_subs = move_subtitles_with_video(
                source, resolved_dest, self.dry_run)
            result.subtitles_moved = [str(s) for s in moved_subs]

            for sub_path in moved_subs:
                self.logger.success(f"Moved subtitle: {sub_path.name}")

        # Save to database
        if not self.dry_run:
            self.database.add_media(
                file_hash=file_hash,
                original_path=str(source),
                original_filename=source.name,
                original_size=get_file_size(source),
                organized_path=str(resolved_dest),
                media_type=metadata.get('media_type', 'unknown'),
                metadata=metadata,
                subtitles=[{'path': str(s), 'language': 'unknown'}
                           for s in result.subtitles_moved],
                media_subtype=metadata.get('media_subtype')
            )

        result.success = True
        return result

    async def organize_batch(self, file_paths: List[Path]) -> List[OrganizationResult]:
        """
        Organize multiple files

        Args:
            file_paths: List of file paths to organize

        Returns:
            List of OrganizationResult objects
        """
        results = []

        for file_path in file_paths:
            try:
                result = await self.organize(file_path)
                results.append(result)
            except Exception as e:
                result = OrganizationResult()
                result.file_path = str(file_path)
                result.error_message = str(e)
                results.append(result)
                self.logger.error(f"Error organizing {file_path}: {e}")

        return results

    def format_folder_name(self, title: str, year: Optional[int], tmdb_id: Optional[int] = None) -> str:
        """
        Format folder name with title, year, and optional TMDB ID

        Args:
            title: Media title
            year: Release year
            tmdb_id: TMDB ID (optional)

        Returns:
            Formatted folder name
        """
        # Always include TMDB ID if available (helps media server identification)
        tmdb_suffix = f" [tmdbid-{tmdb_id}]" if tmdb_id else ""

        if year:
            return f"{title} ({year}){tmdb_suffix}"
        else:
            return f"{title}{tmdb_suffix}"

    def sanitize_title(self, title: str) -> str:
        """
        Sanitize title for use in folder/file names

        Args:
            title: Original title

        Returns:
            Sanitized title
        """
        from ..utils.validators import sanitize_filename
        return sanitize_filename(title)
