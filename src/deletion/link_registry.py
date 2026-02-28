#!/usr/bin/env python3
"""
Link Registry for Media Organization System

Tracks all hardlinks by inode to enable safe deletion of files
in hardlink-based environments.

Usage:
    from src.deletion import LinkRegistry
    
    registry = LinkRegistry(Path("data/link_registry.json"))
    registry.register_link(source_path, dest_path, metadata)
    all_links = registry.get_all_links(path)
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from tinydb import TinyDB, Query

from src.log_config import get_logger, log_success, log_error, log_info, log_warning
from src.log_formatter import LogSection


class LinkRegistry:
    """
    Registry of hardlinks by inode.
    
    Tracks all hardlinks pointing to the same file, enabling:
    - Safe deletion of all hardlinks at once
    - Filesystem scan to rebuild registry
    - Statistics and monitoring
    """

    def __init__(self, db_path: Path):
        """
        Initialize Link Registry
        
        Args:
            db_path: Path to JSON database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.logger = get_logger(__name__)
        
        # Initialize TinyDB
        self.db = TinyDB(str(self.db_path), indent=2, ensure_ascii=False)
        self.files_table = self.db.table('files')
        
        log_info(self.logger, f"Link Registry initialized: {db_path}")

    def get_inode(self, path: Path) -> Optional[int]:
        """
        Get inode of a file
        
        Args:
            path: File path
            
        Returns:
            Inode number or None if file doesn't exist
        """
        try:
            return path.stat().st_ino
        except (OSError, FileNotFoundError):
            return None

    def get_hardlink_count(self, path: Path) -> int:
        """
        Get number of hardlinks to a file
        
        Args:
            path: File path
            
        Returns:
            Number of hardlinks
        """
        try:
            return path.stat().st_nlink
        except (OSError, FileNotFoundError):
            return 0

    def register_link(
        self,
        source_path: Path,
        dest_path: Path,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Register a new hardlink relationship
        
        Args:
            source_path: Original file path
            dest_path: Hardlink destination path
            metadata: Optional metadata (title, year, media_type, etc.)
            
        Returns:
            True if successful
        """
        try:
            inode = self.get_inode(source_path)
            if not inode:
                log_error(self.logger, f"Cannot get inode for: {source_path}")
                return False

            File = Query()
            existing = self.files_table.get(File.inode == inode)

            now = datetime.utcnow().isoformat()

            if existing:
                # Update existing record - add new link
                links = existing.get('links', [])
                
                # Check if link already registered
                for link in links:
                    if link.get('path') == str(dest_path):
                        return True  # Already registered

                links.append({
                    'path': str(dest_path),
                    'type': 'organized',
                    'registered_at': now
                })

                self.files_table.update(
                    {
                        'links': links,
                        'last_updated': now,
                        'metadata': metadata or existing.get('metadata', {})
                    },
                    File.inode == inode
                )

                log_debug(self.logger, f"Updated link registry for inode {inode}")

            else:
                # Create new record
                source_link = {
                    'path': str(source_path),
                    'type': 'original',
                    'registered_at': now
                }

                dest_link = {
                    'path': str(dest_path),
                    'type': 'organized',
                    'registered_at': now
                }

                record = {
                    'inode': inode,
                    'size_bytes': source_path.stat().st_size,
                    'created_at': now,
                    'last_updated': now,
                    'links': [source_link, dest_link],
                    'metadata': metadata or {}
                }

                self.files_table.insert(record)

                log_info(self.logger, f"Registered new inode {inode} with {len(record['links'])} links")

            return True

        except Exception as e:
            log_error(self.logger, f"Failed to register link: {e}")
            return False

    def unregister_link(self, path: Path) -> bool:
        """
        Unregister a link from the registry
        
        Args:
            path: File path to unregister
            
        Returns:
            True if successful
        """
        try:
            inode = self.get_inode(path)
            if not inode:
                # File already deleted, search by path
                return self._unregister_by_path(path)

            File = Query()
            existing = self.files_table.get(File.inode == inode)

            if not existing:
                return True  # Already unregistered

            links = existing.get('links', [])
            path_str = str(path)

            # Remove link from list
            new_links = [link for link in links if link.get('path') != path_str]

            if len(new_links) == 0:
                # No more links, remove record
                self.files_table.remove(File.inode == inode)
                log_info(self.logger, f"Removed inode record {inode} (no more links)")
            else:
                # Update with remaining links
                self.files_table.update(
                    {
                        'links': new_links,
                        'last_updated': datetime.utcnow().isoformat()
                    },
                    File.inode == inode
                )
                log_info(self.logger, f"Unregistered link: {path}")

            return True

        except Exception as e:
            log_error(self.logger, f"Failed to unregister link: {e}")
            return False

    def _unregister_by_path(self, path: Path) -> bool:
        """
        Unregister link by searching all records for the path
        
        Args:
            path: File path to find and remove
            
        Returns:
            True if successful
        """
        try:
            File = Query()
            all_records = self.files_table.all()
            path_str = str(path)

            for record in all_records:
                links = record.get('links', [])
                new_links = [link for link in links if link.get('path') != path_str]

                if len(new_links) != len(links):
                    # Found and removed the link
                    if len(new_links) == 0:
                        self.files_table.remove(File.inode == record['inode'])
                    else:
                        self.files_table.update(
                            {'links': new_links},
                            File.inode == record['inode']
                        )
                    return True

            return False  # Path not found in registry

        except Exception as e:
            log_error(self.logger, f"Failed to unregister by path: {e}")
            return False

    def get_all_links(self, path: Path) -> List[Dict[str, Any]]:
        """
        Get all hardlinks for a file
        
        Args:
            path: Any path to the file
            
        Returns:
            List of link dictionaries with 'path', 'type', 'registered_at'
        """
        try:
            # First try by inode
            inode = self.get_inode(path)
            if inode:
                File = Query()
                record = self.files_table.get(File.inode == inode)
                if record:
                    return record.get('links', [])

            # Fallback: search by path
            File = Query()
            all_records = self.files_table.all()
            path_str = str(path)

            for record in all_records:
                links = record.get('links', [])
                for link in links:
                    if link.get('path') == path_str:
                        return links

            return []  # Not found

        except Exception as e:
            log_error(self.logger, f"Failed to get links: {e}")
            return []

    def get_links_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get full record containing a specific path
        
        Args:
            path: File path to search for
            
        Returns:
            Full record dictionary or None
        """
        try:
            File = Query()
            all_records = self.files_table.all()
            path_str = str(path)

            for record in all_records:
                links = record.get('links', [])
                for link in links:
                    if link.get('path') == path_str:
                        return record

            return None

        except Exception as e:
            log_error(self.logger, f"Failed to get record by path: {e}")
            return None

    def scan_filesystem(
        self,
        directories: List[Path],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Scan filesystem to rebuild registry
        
        Useful for recovery or initial population.
        
        Args:
            directories: List of directories to scan
            progress_callback: Optional callback for progress updates
            
        Returns:
            Statistics dictionary
        """
        stats = {
            'files_scanned': 0,
            'inodes_registered': 0,
            'links_found': 0,
            'errors': 0
        }

        log_info(self.logger, f"Starting filesystem scan: {len(directories)} directories")

        # Group files by inode
        inode_map: Dict[int, List[Path]] = {}

        for directory in directories:
            if not directory.exists():
                log_warning(self.logger, f"Directory not found: {directory}")
                continue

            try:
                for file_path in directory.rglob('*'):
                    if file_path.is_file():
                        stats['files_scanned'] += 1

                        try:
                            inode = file_path.stat().st_ino
                            if inode not in inode_map:
                                inode_map[inode] = []
                            inode_map[inode].append(file_path)
                            stats['links_found'] += 1
                        except (OSError, FileNotFoundError) as e:
                            stats['errors'] += 1
                            log_warning(self.logger, f"Cannot stat file: {file_path}")

                        if progress_callback and stats['files_scanned'] % 100 == 0:
                            progress_callback(stats)

            except Exception as e:
                stats['errors'] += 1
                log_error(self.logger, f"Error scanning {directory}: {e}")

        # Register inodes in database
        now = datetime.utcnow().isoformat()
        File = Query()

        for inode, paths in inode_map.items():
            if len(paths) > 1:  # Only register files with multiple links
                existing = self.files_table.get(File.inode == inode)

                if not existing:
                    links = []
                    for i, path in enumerate(paths):
                        links.append({
                            'path': str(path),
                            'type': 'original' if i == 0 else 'organized',
                            'registered_at': now
                        })

                    try:
                        record = {
                            'inode': inode,
                            'size_bytes': paths[0].stat().st_size,
                            'created_at': now,
                            'last_updated': now,
                            'links': links,
                            'metadata': {}
                        }
                        self.files_table.insert(record)
                        stats['inodes_registered'] += 1
                    except Exception as e:
                        stats['errors'] += 1
                        log_error(self.logger, f"Failed to register inode {inode}: {e}")

        log_success(self.logger, f"Scan complete: {stats['inodes_registered']} inodes registered")
        return stats

    def get_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics
        
        Returns:
            Statistics dictionary
        """
        try:
            all_records = self.files_table.all()

            total_inodes = len(all_records)
            total_links = sum(len(r.get('links', [])) for r in all_records)
            total_size = sum(r.get('size_bytes', 0) for r in all_records)

            # Count by type
            original_count = 0
            organized_count = 0

            for record in all_records:
                for link in record.get('links', []):
                    if link.get('type') == 'original':
                        original_count += 1
                    elif link.get('type') == 'organized':
                        organized_count += 1

            return {
                'total_inodes': total_inodes,
                'total_links': total_links,
                'original_links': original_count,
                'organized_links': organized_count,
                'total_size_bytes': total_size,
                'total_size_gb': round(total_size / (1024**3), 2)
            }

        except Exception as e:
            log_error(self.logger, f"Failed to get stats: {e}")
            return {}

    def get_all_records(self) -> List[Dict[str, Any]]:
        """
        Get all registry records
        
        Returns:
            List of all records
        """
        return self.files_table.all()

    def cleanup_invalid_links(self) -> int:
        """
        Remove links pointing to non-existent files
        
        Returns:
            Number of invalid links removed
        """
        removed_count = 0
        File = Query()
        all_records = self.files_table.all()

        for record in all_records:
            valid_links = []
            for link in record.get('links', []):
                path = Path(link.get('path', ''))
                if path.exists():
                    valid_links.append(link)
                else:
                    removed_count += 1
                    log_info(self.logger, f"Removed invalid link: {path}")

            if len(valid_links) == 0:
                self.files_table.remove(File.inode == record['inode'])
            elif len(valid_links) != len(record.get('links', [])):
                self.files_table.update(
                    {'links': valid_links},
                    File.inode == record['inode']
                )

        log_info(self.logger, f"Cleanup complete: {removed_count} invalid links removed")
        return removed_count

    def close(self):
        """Close database connection"""
        self.db.close()


def log_debug(logger, message):
    """Log debug message"""
    logger.debug(message)
