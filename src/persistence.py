"""
Persistence module for Media Organization System

Consolidated module containing:
- OrganizationDatabase (Track organized media)
- UnorganizedDatabase (Track files that couldn't be organized)

Usage:
    from src.persistence import OrganizationDatabase, UnorganizedDatabase
"""
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from tinydb import TinyDB, Query

from src.core import DatabaseInterface


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_datetime_br(dt: datetime = None) -> str:
    """Format datetime to Brazilian format (DD/MM/YYYY HH:MM:SS)"""
    if dt is None:
        dt = datetime.utcnow()
    return dt.strftime("%d/%m/%Y %H:%M:%S")


# ============================================================================
# SECTION 1: ORGANIZATION DATABASE
# ============================================================================

class OrganizationDatabase(DatabaseInterface):
    """
    JSON database for tracking organized media files.
    
    Uses TinyDB for simple, human-readable storage.
    Automatic backups with configurable retention.
    """
    
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
            backup_enabled: Enable automatic backups
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
        
        # Initialize stats
        if not self.stats_table.all():
            self._init_stats()
    
    def _init_stats(self):
        """Initialize statistics table"""
        stats = {
            "total_files_organized": 0,
            "movies": 0,
            "series": 0,
            "animes": 0,
            "doramas": 0,
            "music_tracks": 0,
            "books": 0,
            "comics": 0,
            "failed_operations": 0,
            "last_organization_run": format_datetime_br()
        }
        self.stats_table.truncate()
        self.stats_table.insert(stats)
    
    def adicionar_midia(
        self,
        file_hash: str,
        original_path: str,
        organized_path: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Add organized media to database
        
        Args:
            file_hash: File hash
            original_path: Original file path
            organized_path: Organized file path
            metadata: File metadata
            
        Returns:
            True if successful
        """
        try:
            Media = Query()
            existing = self.media_table.search(
                (Media.file_hash == file_hash) &
                (Media.original_path == original_path)
            )
            
            if existing:
                # Update existing record
                self.media_table.update(
                    {
                        "metadata": metadata,
                        "last_checked": format_datetime_br(),
                        "subtitles": existing[0].get('subtitles', []),  # Preserve subtitles
                        "errors": []
                    },
                    (Media.file_hash == file_hash) &
                    (Media.original_path == original_path)
                )
                return True
            
            # Insert new record
            record = {
                "file_hash": file_hash,
                "original_path": original_path,
                "organized_path": organized_path,
                "processed_date": format_datetime_br(),
                "last_checked": format_datetime_br(),
                "file_exists": True,
                "hardlink_created": True,
                "metadata": metadata,
                "subtitles": [],  # NEW: Track subtitles
                "errors": []
            }
            
            self.media_table.insert(record)
            self._update_stats(metadata)
            
            # Backup if needed
            if self.backup_enabled:
                self.create_backup_if_needed()
            
            return True
            
        except Exception as e:
            print(f"Error adding media: {e}")
            return False
    
    def is_file_organized(self, file_path: str) -> bool:
        """
        Check if file is already organized
        
        Args:
            file_path: File path to check
            
        Returns:
            True if file is organized
        """
        Media = Query()
        results = self.media_table.search(Media.original_path == str(file_path))
        return len(results) > 0
    
    def get_stats(self) -> Dict:
        """Get organization statistics"""
        stats = self.stats_table.all()
        return stats[0] if stats else {}
    
    def _update_stats(self, metadata: Dict):
        """Update statistics when media is added"""
        stats = self.get_stats()
        
        stats['total_files_organized'] += 1
        
        media_type = (metadata.get('media_type', '') or '').lower()
        media_subtype = (metadata.get('media_subtype', '') or '').lower()
        
        type_map = {
            'movie': 'movies',
            'tv': 'series',
            'series': 'series',
            'anime': 'animes',
            'dorama': 'doramas',
            'music': 'music_tracks',
            'book': 'books',
            'comic': 'comics'
        }
        
        if media_subtype in type_map:
            stats[type_map[media_subtype]] += 1
        elif media_type in type_map:
            stats[type_map[media_type]] += 1
        
        stats['last_organization_run'] = format_datetime_br()
        
        self.stats_table.truncate()
        self.stats_table.insert(stats)
    
    def add_failure(self, file_path: str, error_type: str, error_message: str):
        """
        Add failed operation to database
        
        Args:
            file_path: File path
            error_type: Error type
            error_message: Error message
        """
        failure = {
            "timestamp": format_datetime_br(),
            "file_path": file_path,
            "error_type": error_type,
            "error_message": error_message
        }
        self.failures_table.insert(failure)
        
        stats = self.get_stats()
        stats['failed_operations'] += 1
        self.stats_table.truncate()
        self.stats_table.insert(stats)
    
    def get_failures(self, limit: int = 100) -> List[Dict]:
        """Get recent failures"""
        all_failures = self.failures_table.all()
        return sorted(
            all_failures,
            key=lambda x: x.get('timestamp', ''),
            reverse=True
        )[:limit]

    # ========================================================================
    # SUBTITLE MANAGEMENT
    # ========================================================================

    def save_subtitle_rate_limit(
        self,
        downloads_today: int,
        last_download_time: str = None,
        rate_limit_remaining: int = 20
    ) -> bool:
        """
        Save subtitle rate limit state to database
        
        Args:
            downloads_today: Number of downloads made today
            last_download_time: ISO format timestamp of first download
            rate_limit_remaining: Remaining downloads
            
        Returns:
            True if successful
        """
        try:
            # Use a dedicated table for rate limit state
            rate_limit_table = self.db.table('subtitle_rate_limit')
            
            # Clear existing record
            rate_limit_table.truncate()
            
            # Save new state
            record = {
                'downloads_today': downloads_today,
                'last_download_time': last_download_time,
                'rate_limit_remaining': rate_limit_remaining,
                'updated_at': format_datetime_br()
            }
            
            rate_limit_table.insert(record)
            return True
            
        except Exception as e:
            print(f"Error saving rate limit state: {e}")
            return False

    def load_subtitle_rate_limit(self) -> Dict[str, Any]:
        """
        Load subtitle rate limit state from database
        
        Returns:
            Dictionary with rate limit state
        """
        try:
            rate_limit_table = self.db.table('subtitle_rate_limit')
            records = rate_limit_table.all()
            
            if records:
                return records[0]
            
            # Default state
            return {
                'downloads_today': 0,
                'last_download_time': None,
                'rate_limit_remaining': 20
            }
            
        except Exception as e:
            print(f"Error loading rate limit state: {e}")
            return {
                'downloads_today': 0,
                'last_download_time': None,
                'rate_limit_remaining': 20
            }

    def add_subtitle(
        self,
        file_hash: str,
        subtitle_path: str,
        language: str
    ) -> bool:
        """
        Add subtitle to media record
        
        Args:
            file_hash: File hash
            subtitle_path: Path to subtitle file
            language: Language code (e.g., 'pt', 'en')
            
        Returns:
            True if successful
        """
        try:
            Media = Query()
            record = self.media_table.get(Media.file_hash == file_hash)
            
            if not record:
                return False
            
            # Get existing subtitles
            subtitles = record.get('subtitles', [])
            
            # Check if subtitle already exists
            for sub in subtitles:
                if sub.get('path') == subtitle_path:
                    return True  # Already exists
            
            # Add new subtitle
            subtitles.append({
                'path': subtitle_path,
                'language': language.lower(),
                'added_date': format_datetime_br(),
                'source': 'opensubtitles'
            })
            
            # Update record
            self.media_table.update(
                {'subtitles': subtitles},
                Media.file_hash == file_hash
            )
            
            return True
            
        except Exception as e:
            print(f"Error adding subtitle: {e}")
            return False

    def has_subtitle(
        self,
        file_hash: str,
        language: str = None
    ) -> bool:
        """
        Check if media has subtitle
        
        Args:
            file_hash: File hash
            language: Optional language code to check
            
        Returns:
            True if has subtitle
        """
        try:
            Media = Query()
            record = self.media_table.get(Media.file_hash == file_hash)
            
            if not record:
                return False
            
            subtitles = record.get('subtitles', [])
            
            if not subtitles:
                return False
            
            if language:
                # Check for specific language
                return any(
                    sub.get('language', '').lower() == language.lower()
                    for sub in subtitles
                )
            
            return len(subtitles) > 0
            
        except Exception as e:
            print(f"Error checking subtitle: {e}")
            return False

    def get_files_without_subtitles(
        self,
        media_type: str = None
    ) -> List[Dict]:
        """
        Get list of files without subtitles
        
        Args:
            media_type: Filter by media type (movie, tv, etc.)
            
        Returns:
            List of file records without subtitles
        """
        try:
            files = []
            all_media = self.media_table.all()
            
            for record in all_media:
                # Filter by media type if specified
                if media_type:
                    record_media_type = record.get('metadata', {}).get('media_type', '')
                    if record_media_type != media_type:
                        continue
                
                # Check if has subtitles
                subtitles = record.get('subtitles', [])
                if not subtitles:
                    files.append(record)
            
            return files
            
        except Exception as e:
            print(f"Error getting files without subtitles: {e}")
            return []

    def get_subtitle_statistics(self) -> Dict[str, Any]:
        """
        Get subtitle statistics
        
        Returns:
            Dictionary with subtitle stats
        """
        try:
            all_media = self.media_table.all()
            
            total = len(all_media)
            with_subtitles = sum(1 for m in all_media if m.get('subtitles', []))
            without_subtitles = total - with_subtitles
            
            # Count by language
            languages = {}
            for media in all_media:
                for sub in media.get('subtitles', []):
                    lang = sub.get('language', 'unknown')
                    languages[lang] = languages.get(lang, 0) + 1
            
            return {
                'total_files': total,
                'with_subtitles': with_subtitles,
                'without_subtitles': without_subtitles,
                'coverage_percent': (with_subtitles / total * 100) if total > 0 else 0,
                'languages': languages
            }
            
        except Exception as e:
            print(f"Error getting subtitle statistics: {e}")
            return {}

    
    def create_backup(self) -> Optional[Path]:
        """Create timestamped backup"""
        if not self.backup_enabled:
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_path = self.backup_dir / f"organization_{timestamp}.json"
            
            self.db.close()
            shutil.copy2(self.db_path, backup_path)
            
            self.db = TinyDB(str(self.db_path), indent=2, ensure_ascii=False)
            self._reconnect_tables()
            
            self.cleanup_old_backups()
            
            return backup_path
        except Exception as e:
            print(f"Backup error: {e}")
            return None
    
    def create_backup_if_needed(self) -> Optional[Path]:
        """Create backup only if 7+ days since last backup"""
        if not self.backup_enabled:
            return None
        
        recent = self._get_recent_backups(days=7)
        
        if recent:
            return None
        
        return self.create_backup()
    
    def _get_recent_backups(self, days: int) -> List[Path]:
        """Get backups created within last N days"""
        if not self.backup_dir.exists():
            return []
        
        cutoff = datetime.now() - timedelta(days=days)
        recent = []
        
        for backup_file in self.backup_dir.glob("organization_*.json"):
            try:
                timestamp_str = backup_file.stem.replace("organization_", "")
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S")
                if timestamp >= cutoff:
                    recent.append(backup_file)
            except ValueError:
                continue
        
        return recent
    
    def cleanup_old_backups(self):
        """Remove backups older than keep_days"""
        if not self.backup_enabled:
            return
        
        cutoff = datetime.now() - timedelta(days=self.backup_keep_days)
        
        for backup_file in self.backup_dir.glob("organization_*.json"):
            try:
                timestamp_str = backup_file.stem.replace("organization_", "")
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S")
                if timestamp < cutoff:
                    backup_file.unlink()
            except ValueError:
                continue
    
    def _reconnect_tables(self):
        """Reconnect to tables after DB reopen"""
        self.media_table = self.db.table('media')
        self.stats_table = self.db.table('statistics')
        self.failures_table = self.db.table('failed_operations')
    
    def close(self):
        """Close database connection"""
        self.db.close()


# ============================================================================
# SECTION 2: UNORGANIZED DATABASE
# ============================================================================

class UnorganizedDatabase:
    """
    Track files that couldn't be organized.
    
    Stores reason for failure and suggestions for resolution.
    Simple JSON file format.
    """
    
    def __init__(self, db_path: Path):
        """
        Initialize unorganized database
        
        Args:
            db_path: Path to database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()
    
    def _load(self):
        """Load database from file"""
        if self.db_path.exists():
            with open(self.db_path, 'r', encoding='utf-8') as f:
                try:
                    self.data = json.load(f)
                except json.JSONDecodeError:
                    self.data = {"unorganized": []}
        else:
            self.data = {"unorganized": []}
    
    def _save(self):
        """Save database to file"""
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def add_unorganized(self, file_path: str, error_message: str):
        """
        Add file to unorganized list
        
        Args:
            file_path: File path
            error_message: Reason why file couldn't be organized
        """
        now = datetime.utcnow().isoformat()
        entry = {
            "file_path": file_path,
            "filename": Path(file_path).name,
            "directory": str(Path(file_path).parent),
            "last_attempt": now,
            "error": error_message
        }
        
        # Remove previous entry for this file
        self.data["unorganized"] = [
            e for e in self.data["unorganized"] if e["file_path"] != file_path
        ]
        
        self.data["unorganized"].append(entry)
        self._save()
    
    def remove_unorganized(self, file_path: str):
        """
        Remove entry for file if it exists
        
        Args:
            file_path: File path to remove
        """
        before = len(self.data["unorganized"])
        self.data["unorganized"] = [
            e for e in self.data["unorganized"] if e["file_path"] != file_path
        ]
        
        if len(self.data["unorganized"]) != before:
            self._save()
    
    def get_all(self) -> List[Dict]:
        """
        Get all unorganized files
        
        Returns:
            List of unorganized file entries
        """
        return self.data["unorganized"]
    
    def get_unorganized_files(self) -> List[Dict]:
        """
        Get all unorganized files (alias for get_all)
        
        Returns:
            List of unorganized file entries
        """
        return self.get_all()
