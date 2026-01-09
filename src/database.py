"""
Database module for Media Organization System
JSON-based database with automatic backup functionality
"""

import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from tinydb import TinyDB, Query


def format_datetime_br(dt: datetime = None) -> str:
    """Format datetime to Brazilian format (DD/MM/YYYY HH:MM:SS)"""
    if dt is None:
        dt = datetime.utcnow()
    return dt.strftime("%d/%m/%Y %H:%M:%S")


class OrganizationDatabase:
    """JSON database for tracking organized media files"""

    def __init__(
        self,
        db_path: Path,
        backup_enabled: bool = True,
        backup_keep_days: int = 7
    ):
        """
        Initialize database

        Args:
            db_path: Path to database file
            backup_enabled: Whether to enable automatic backups
            backup_keep_days: Days to keep backups
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.backup_enabled = backup_enabled
        self.backup_keep_days = backup_keep_days
        self.backup_dir = self.db_path.parent / "backups"

        if backup_enabled:
            self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Initialize TinyDB
        self.db = TinyDB(str(self.db_path), indent=2, ensure_ascii=False)

        # Tables
        self.media_table = self.db.table('media')
        self.stats_table = self.db.table('statistics')
        self.failures_table = self.db.table('failed_operations')
        self.monitoring_table = self.db.table('monitoring')
        self.torrents_table = self.db.table('torrent_tracking')

        # Initialize stats if empty
        if not self.stats_table.all():
            self._initialize_stats()

    # ========== Media Operations ==========

    def add_media(
        self,
        file_hash: str,
        original_path: str,
        original_filename: str,
        original_size: int,
        organized_path: str,
        media_type: str,
        metadata: Dict[str, Any],
        subtitles: List[Dict[str, str]] = None,
        media_subtype: Optional[str] = None
    ) -> bool:
        """
        Add organized media to database

        Args:
            file_hash: SHA256 hash of file
            original_path: Original file path
            original_filename: Original filename
            original_size: File size in bytes
            organized_path: New organized path
            media_type: Type of media (movie, tv, anime, etc.)
            metadata: Metadata dictionary
            subtitles: List of subtitle files
            media_subtype: Optional subtype (series, dorama, etc.)

        Returns:
            True if successful
        """
        try:
            # Check if already exists
            existing = self.get_media_by_hash(file_hash)
            if existing:
                return False

            record = {
                "file_hash": file_hash,
                "original_path": original_path,
                "original_filename": original_filename,
                "original_size_bytes": original_size,
                "organized_path": organized_path,
                "media_type": media_type,
                "media_subtype": media_subtype,
                "processed_date": format_datetime_br(),
                "last_checked": format_datetime_br(),
                "file_exists": True,
                "hardlink_created": True,
                "metadata": metadata,
                "subtitles": subtitles or [],
                "errors": []
            }

            self.media_table.insert(record)
            self._update_stats_on_add(media_type)

            if self.backup_enabled:
                self.create_backup()

            return True

        except Exception as e:
            print(f"Error adding media to database: {e}")
            return False

    def get_media_by_hash(self, file_hash: str) -> Optional[Dict]:
        """Get media record by file hash"""
        Media = Query()
        results = self.media_table.search(Media.file_hash == file_hash)
        return results[0] if results else None

    def get_media_by_path(self, path: str) -> Optional[Dict]:
        """Get media record by organized path"""
        Media = Query()
        results = self.media_table.search(Media.organized_path == path)
        return results[0] if results else None

    def is_already_organized(self, file_hash: str) -> bool:
        """Check if file is already organized"""
        return self.get_media_by_hash(file_hash) is not None

    def is_file_organized(self, file_path: str) -> bool:
        """Check if file path is already organized (by original or organized path)"""
        Media = Query()
        # Check both original_path and organized_path
        results = self.media_table.search(
            (Media.original_path == str(file_path)) |
            (Media.organized_path == str(file_path))
        )
        return len(results) > 0

    def update_media(self, file_hash: str, updates: Dict) -> bool:
        """Update media record"""
        try:
            Media = Query()
            updates['last_checked'] = format_datetime_br()
            self.media_table.update(updates, Media.file_hash == file_hash)
            return True
        except Exception:
            return False

    def get_all_media(self, media_type: Optional[str] = None) -> List[Dict]:
        """Get all media records, optionally filtered by type"""
        if media_type:
            Media = Query()
            return self.media_table.search(Media.media_type == media_type)
        return self.media_table.all()

    def remove_media(self, file_hash: str) -> bool:
        """Remove media record from database"""
        try:
            Media = Query()
            self.media_table.remove(Media.file_hash == file_hash)
            return True
        except Exception:
            return False

    # ========== Statistics ==========

    def _initialize_stats(self):
        """Initialize statistics table"""
        stats = {
            "total_files_organized": 0,
            "movies_organized": 0,
            "series_organized": 0,
            "animes_organized": 0,
            "doramas_organized": 0,
            "music_organized": 0,
            "books_organized": 0,
            "audiobooks_organized": 0,
            "comics_organized": 0,
            "total_size_bytes": 0,
            "total_size_gb": 0,
            "space_saved_bytes": 0,
            "failed_operations": 0,
            "last_organization_run": None,
        }
        self.stats_table.insert(stats)

    def get_stats(self) -> Dict:
        """Get current statistics"""
        stats = self.stats_table.all()
        return stats[0] if stats else {}

    def _update_stats_on_add(self, media_type: str):
        """Update statistics when media is added"""
        stats = self.get_stats()
        stats['total_files_organized'] = stats.get(
            'total_files_organized', 0) + 1

        # Normalize media_type to plural for counter key
        # (movie -> movies, anime -> animes, book -> books, etc.)
        plural_map = {
            'movie': 'movies',
            'series': 'series',  # Already plural
            'anime': 'animes',
            'dorama': 'doramas',
            'music': 'music',  # Already plural/mass noun
            'book': 'books',
            'audiobook': 'audiobooks',
            'comic': 'comics'
        }

        plural_type = plural_map.get(media_type, media_type + 's')
        type_key = f"{plural_type}_organized"

        if type_key in stats:
            stats[type_key] = stats.get(type_key, 0) + 1

        stats['last_organization_run'] = format_datetime_br()

        # Update in database
        self.stats_table.truncate()
        self.stats_table.insert(stats)

    def update_stats(self, updates: Dict):
        """Update statistics with custom values"""
        stats = self.get_stats()
        stats.update(updates)
        self.stats_table.truncate()
        self.stats_table.insert(stats)

    # ========== Failed Operations ==========

    def add_failure(
        self,
        file_path: str,
        error_type: str,
        error_message: str,
        retry_count: int = 0
    ):
        """Add failed operation to database"""
        failure = {
            "timestamp": format_datetime_br(),
            "file_path": file_path,
            "error_type": error_type,
            "error_message": error_message,
            "retry_count": retry_count
        }
        self.failures_table.insert(failure)

        # Update stats
        stats = self.get_stats()
        stats['failed_operations'] = stats.get('failed_operations', 0) + 1
        self.update_stats(stats)

    def get_failures(self, limit: int = 100) -> List[Dict]:
        """Get recent failures"""
        all_failures = self.failures_table.all()
        return sorted(
            all_failures,
            key=lambda x: x.get('timestamp', ''),
            reverse=True
        )[:limit]

    def clear_old_failures(self, days: int = 30):
        """Clear failures older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        Failure = Query()
        self.failures_table.remove(Failure.timestamp < cutoff_str)

    # ========== Backup Operations ==========

    def create_backup(self) -> Optional[Path]:
        """
        Create timestamped backup of database

        Returns:
            Path to backup file or None if failed
        """
        if not self.backup_enabled:
            return None

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_path = self.backup_dir / f"organization_{timestamp}.json"

            # Close and copy file
            self.db.close()
            shutil.copy2(self.db_path, backup_path)

            # Reopen database
            self.db = TinyDB(str(self.db_path), indent=2, ensure_ascii=False)
            self._reconnect_tables()

            # Cleanup old backups
            self.cleanup_old_backups()

            return backup_path

        except Exception as e:
            print(f"Error creating backup: {e}")
            return None

    def restore_from_backup(self, backup_path: Path) -> bool:
        """
        Restore database from backup

        Args:
            backup_path: Path to backup file

        Returns:
            True if successful
        """
        try:
            if not backup_path.exists():
                return False

            # Close database
            self.db.close()

            # Backup current database first
            current_backup = self.db_path.parent / \
                f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(self.db_path, current_backup)

            # Restore from backup
            shutil.copy2(backup_path, self.db_path)

            # Reopen database
            self.db = TinyDB(str(self.db_path), indent=2, ensure_ascii=False)
            self._reconnect_tables()

            return True

        except Exception as e:
            print(f"Error restoring from backup: {e}")
            return False

    def cleanup_old_backups(self):
        """Remove backups older than keep_days"""
        if not self.backup_enabled:
            return

        try:
            cutoff = datetime.now() - timedelta(days=self.backup_keep_days)

            for backup_file in self.backup_dir.glob("organization_*.json"):
                # Parse timestamp from filename
                try:
                    timestamp_str = backup_file.stem.replace(
                        "organization_", "")
                    timestamp = datetime.strptime(
                        timestamp_str, "%Y-%m-%d_%H-%M-%S")

                    if timestamp < cutoff:
                        backup_file.unlink()

                except ValueError:
                    # Skip files with invalid timestamp format
                    continue

        except Exception as e:
            print(f"Error cleaning up backups: {e}")

    def list_backups(self) -> List[Dict]:
        """List all available backups"""
        backups = []

        for backup_file in sorted(self.backup_dir.glob("organization_*.json"), reverse=True):
            try:
                timestamp_str = backup_file.stem.replace("organization_", "")
                timestamp = datetime.strptime(
                    timestamp_str, "%Y-%m-%d_%H-%M-%S")

                backups.append({
                    "path": backup_file,
                    "timestamp": timestamp,
                    "size_bytes": backup_file.stat().st_size,
                    "age_days": (datetime.now() - timestamp).days
                })

            except ValueError:
                continue

        return backups

    def _reconnect_tables(self):
        """Reconnect to database tables after reopen"""
        self.media_table = self.db.table('media')
        self.stats_table = self.db.table('statistics')
        self.failures_table = self.db.table('failed_operations')
        self.monitoring_table = self.db.table('monitoring')
        self.torrents_table = self.db.table('torrent_tracking')

    # ========== Monitoring ==========

    def update_monitoring_status(self, status: Dict):
        """Update monitoring status"""
        self.monitoring_table.truncate()
        status['last_scan'] = datetime.utcnow().isoformat()
        self.monitoring_table.insert(status)

    def get_monitoring_status(self) -> Dict:
        """Get current monitoring status"""
        status = self.monitoring_table.all()
        return status[0] if status else {}

    # ========== Cleanup ==========

    def verify_file_existence(self) -> int:
        """
        Verify that organized files still exist

        Returns:
            Number of missing files found
        """
        missing_count = 0

        for record in self.media_table.all():
            organized_path = Path(record.get('organized_path', ''))

            if not organized_path.exists():
                self.update_media(
                    record['file_hash'],
                    {'file_exists': False}
                )
                missing_count += 1

        return missing_count

    def close(self):
        """Close database connection"""
        self.db.close()
