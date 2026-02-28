#!/usr/bin/env python3
"""
Trash Manager for Media Organization System

Manages a trash system with retention policy for safe deletion
of files in hardlink-based environments.

Usage:
    from src.deletion import TrashManager
    
    trash = TrashManager(Path("data/trash"), retention_days=30)
    trash_id = trash.move_to_trash(file_path, all_links, metadata)
    trash.restore_from_trash(trash_id)
    trash.empty_trash()
"""

import json
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from tinydb import TinyDB, Query

from src.log_config import get_logger, log_success, log_error, log_info, log_warning
from src.log_formatter import LogSection


class TrashManager:
    """
    Trash manager with retention policy.
    
    Provides:
    - Safe move of files to trash (preserving one copy)
    - Restoration of trashed items
    - Automatic cleanup of old items
    - Statistics and monitoring
    """

    def __init__(self, trash_path: Path, retention_days: int = 30):
        """
        Initialize Trash Manager
        
        Args:
            trash_path: Path to trash directory
            retention_days: Days to keep items in trash
        """
        self.trash_path = trash_path
        self.retention_days = retention_days
        self.logger = get_logger(__name__)

        # Create directories
        self.trash_path.mkdir(parents=True, exist_ok=True)
        self.files_path = trash_path / "files"
        self.files_path.mkdir(parents=True, exist_ok=True)

        # Initialize index database
        self.index_path = trash_path / "index.json"
        self.db = TinyDB(str(self.index_path), indent=2, ensure_ascii=False)
        self.items_table = self.db.table('items')

        log_info(self.logger, f"Trash Manager initialized: {trash_path} (retention: {retention_days} days)")

    def move_to_trash(
        self,
        primary_path: Path,
        all_links: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Move file to trash, removing all hardlinks
        
        Args:
            primary_path: Primary file path to preserve in trash
            all_links: List of all hardlink paths (from LinkRegistry)
            metadata: Optional metadata to store
            
        Returns:
            Trash ID if successful, None otherwise
        """
        try:
            # Generate unique trash ID
            trash_id = str(uuid.uuid4())[:8]
            trash_item_path = self.files_path / trash_id

            # Create trash item directory
            trash_item_path.mkdir(parents=True, exist_ok=True)

            now = datetime.utcnow().isoformat()

            # Copy the primary file to trash
            preserved_path = None
            if primary_path.exists():
                preserved_path = trash_item_path / primary_path.name
                try:
                    shutil.copy2(primary_path, preserved_path)
                    log_info(self.logger, f"Copied to trash: {primary_path.name}")
                except Exception as e:
                    log_error(self.logger, f"Failed to copy file to trash: {e}")
                    shutil.rmtree(trash_item_path)
                    return None

            # Remove all original hardlinks
            removed_links = []
            for link in all_links:
                link_path = Path(link.get('path', ''))
                if link_path.exists():
                    try:
                        link_path.unlink()
                        removed_links.append(str(link_path))
                        log_info(self.logger, f"Removed link: {link_path}")
                    except Exception as e:
                        log_error(self.logger, f"Failed to remove link {link_path}: {e}")

            # Save links manifest
            manifest = {
                'trash_id': trash_id,
                'created_at': now,
                'original_links': all_links,
                'removed_links': removed_links,
                'preserved_path': str(preserved_path) if preserved_path else None,
                'metadata': metadata or {}
            }

            manifest_path = trash_item_path / "links.json"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)

            # Calculate expiration date
            expires_at = (datetime.utcnow() + timedelta(days=self.retention_days)).isoformat()

            # Add to index
            item_record = {
                'trash_id': trash_id,
                'created_at': now,
                'expires_at': expires_at,
                'original_path': str(primary_path),
                'preserved_path': str(preserved_path) if preserved_path else None,
                'removed_links_count': len(removed_links),
                'size_bytes': preserved_path.stat().st_size if preserved_path and preserved_path.exists() else 0,
                'metadata': metadata or {},
                'status': 'active'
            }

            self.items_table.insert(item_record)

            log_success(self.logger, f"Moved to trash: {primary_path.name} (ID: {trash_id})")
            return trash_id

        except Exception as e:
            log_error(self.logger, f"Failed to move to trash: {e}")
            return None

    def restore_from_trash(self, trash_id: str, restore_paths: Optional[List[Path]] = None) -> bool:
        """
        Restore item from trash
        
        Args:
            trash_id: Trash item ID
            restore_paths: Optional list of paths to restore to (uses original paths if not provided)
            
        Returns:
            True if successful
        """
        try:
            Item = Query()
            record = self.items_table.get(Item.trash_id == trash_id)

            if not record:
                log_error(self.logger, f"Trash item not found: {trash_id}")
                return False

            if record.get('status') != 'active':
                log_error(self.logger, f"Trash item not active: {trash_id} (status: {record.get('status')})")
                return False

            # Load manifest
            manifest_path = self.files_path / trash_id / "links.json"
            if not manifest_path.exists():
                log_error(self.logger, f"Manifest not found for: {trash_id}")
                return False

            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)

            # Get preserved file from trash
            preserved_path = Path(manifest.get('preserved_path', ''))
            if not preserved_path or not preserved_path.exists():
                log_error(self.logger, f"Preserved file not found: {preserved_path}")
                return False

            # Determine restore paths
            original_links = manifest.get('original_links', [])
            
            if restore_paths is None:
                # Use original paths from manifest
                restore_paths = [Path(link['path']) for link in original_links if link.get('type') == 'original']
            
            if not restore_paths:
                log_error(self.logger, "No restore paths specified")
                return False

            # Restore file to each path
            restored_count = 0
            for dest_path in restore_paths:
                try:
                    # Create parent directories
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy file
                    shutil.copy2(preserved_path, dest_path)
                    restored_count += 1
                    log_info(self.logger, f"Restored to: {dest_path}")
                except Exception as e:
                    log_error(self.logger, f"Failed to restore to {dest_path}: {e}")

            if restored_count == 0:
                return False

            # Update index
            self.items_table.update(
                {
                    'status': 'restored',
                    'restored_at': datetime.utcnow().isoformat(),
                    'restored_count': restored_count
                },
                Item.trash_id == trash_id
            )

            log_success(self.logger, f"Restored {restored_count} file(s) from trash: {trash_id}")
            return True

        except Exception as e:
            log_error(self.logger, f"Failed to restore from trash: {e}")
            return False

    def empty_trash(self, older_than_days: Optional[int] = None) -> Dict[str, Any]:
        """
        Empty trash
        
        Args:
            older_than_days: Only remove items older than this (None = all items)
            
        Returns:
            Statistics dictionary
        """
        stats = {
            'items_removed': 0,
            'space_freed_bytes': 0,
            'errors': 0
        }

        Item = Query()
        all_items = self.items_table.all()

        cutoff_date = None
        if older_than_days is not None:
            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

        for item in all_items:
            try:
                trash_id = item.get('trash_id', '')
                created_at_str = item.get('created_at', '')
                
                # Parse created_at
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                except (ValueError, TypeError):
                    created_at = None

                # Check if should be removed
                if cutoff_date and created_at:
                    if created_at >= cutoff_date:
                        continue  # Not old enough

                # Remove trash item directory
                item_path = self.files_path / trash_id
                if item_path.exists():
                    # Calculate size before removal
                    try:
                        size = sum(f.stat().st_size for f in item_path.rglob('*') if f.is_file())
                        stats['space_freed_bytes'] += size
                    except:
                        pass

                    shutil.rmtree(item_path)
                    stats['items_removed'] += 1
                    log_info(self.logger, f"Removed from trash: {trash_id}")

                # Remove from index
                self.items_table.remove(Item.trash_id == trash_id)

            except Exception as e:
                stats['errors'] += 1
                log_error(self.logger, f"Failed to remove trash item: {e}")

        log_success(self.logger, f"Empty trash complete: {stats['items_removed']} items removed")
        return stats

    def list_items(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        List items in trash
        
        Args:
            active_only: Only show active (not restored/expired) items
            
        Returns:
            List of item dictionaries
        """
        try:
            if active_only:
                Item = Query()
                items = self.items_table.search(Item.status == 'active')
            else:
                items = self.items_table.all()

            # Add human-readable info
            result = []
            for item in items:
                display_item = item.copy()
                
                # Calculate days remaining
                expires_at_str = item.get('expires_at', '')
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    days_remaining = (expires_at - datetime.utcnow()).days
                    display_item['days_remaining'] = max(0, days_remaining)
                except:
                    display_item['days_remaining'] = None

                # Format size
                size_bytes = item.get('size_bytes', 0)
                if size_bytes >= 1024**3:
                    display_item['size_display'] = f"{size_bytes / (1024**3):.2f} GB"
                elif size_bytes >= 1024**2:
                    display_item['size_display'] = f"{size_bytes / (1024**2):.2f} MB"
                elif size_bytes >= 1024:
                    display_item['size_display'] = f"{size_bytes / 1024:.2f} KB"
                else:
                    display_item['size_display'] = f"{size_bytes} B"

                result.append(display_item)

            return result

        except Exception as e:
            log_error(self.logger, f"Failed to list trash items: {e}")
            return []

    def get_item(self, trash_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific trash item
        
        Args:
            trash_id: Trash item ID
            
        Returns:
            Item dictionary or None
        """
        try:
            Item = Query()
            return self.items_table.get(Item.trash_id == trash_id)
        except Exception as e:
            log_error(self.logger, f"Failed to get item: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get trash statistics
        
        Returns:
            Statistics dictionary
        """
        try:
            items = self.items_table.all()

            total_items = len(items)
            active_items = sum(1 for i in items if i.get('status') == 'active')
            restored_items = sum(1 for i in items if i.get('status') == 'restored')
            
            total_size = sum(i.get('size_bytes', 0) for i in items if i.get('status') == 'active')

            # Check for expired items
            now = datetime.utcnow()
            expired_items = 0
            for item in items:
                expires_at_str = item.get('expires_at', '')
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if expires_at < now and item.get('status') == 'active':
                        expired_items += 1
                except:
                    pass

            return {
                'total_items': total_items,
                'active_items': active_items,
                'restored_items': restored_items,
                'expired_items': expired_items,
                'total_size_bytes': total_size,
                'total_size_gb': round(total_size / (1024**3), 2),
                'retention_days': self.retention_days
            }

        except Exception as e:
            log_error(self.logger, f"Failed to get stats: {e}")
            return {}

    def cleanup_expired(self) -> int:
        """
        Remove expired items from trash
        
        Returns:
            Number of items removed
        """
        now = datetime.utcnow()
        Item = Query()
        all_items = self.items_table.search(Item.status == 'active')

        removed_count = 0
        for item in all_items:
            expires_at_str = item.get('expires_at', '')
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at < now:
                    trash_id = item.get('trash_id', '')
                    
                    # Remove directory
                    item_path = self.files_path / trash_id
                    if item_path.exists():
                        shutil.rmtree(item_path)
                    
                    # Remove from index
                    self.items_table.remove(Item.trash_id == trash_id)
                    removed_count += 1
                    log_info(self.logger, f"Removed expired item: {trash_id}")
            except Exception as e:
                log_error(self.logger, f"Failed to cleanup expired item: {e}")

        log_info(self.logger, f"Cleanup complete: {removed_count} expired items removed")
        return removed_count

    def close(self):
        """Close database connection"""
        self.db.close()
