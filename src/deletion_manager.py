#!/usr/bin/env python3
"""
Deletion Manager for Media Organization System

Orchestrates safe deletion of files in hardlink-based environments.
Provides both trash-based and permanent deletion modes.

Usage:
    from src.deletion import DeletionManager, LinkRegistry, TrashManager
    
    link_registry = LinkRegistry(Path("data/link_registry.json"))
    trash_manager = TrashManager(Path("data/trash"), retention_days=30)
    deletion_manager = DeletionManager(link_registry, trash_manager, database)
    
    # Preview deletion
    preview = await deletion_manager.get_deletion_preview(path)
    
    # Delete to trash (default)
    result = await deletion_manager.delete_to_trash(path, metadata)
    
    # Delete permanently
    result = await deletion_manager.delete_permanent(path, dry_run=False, force=False)
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from rich.prompt import Confirm, Prompt
from rich.console import Console

from src.log_config import get_logger, log_success, log_error, log_info, log_warning
from src.log_formatter import LogSection
from src.link_registry import LinkRegistry
from src.trash_manager import TrashManager


console = Console()


class DeletionResult:
    """Result of a deletion operation"""

    def __init__(
        self,
        success: bool,
        operation_type: str,
        trash_id: Optional[str] = None,
        removed_links: Optional[List[str]] = None,
        error_message: Optional[str] = None
    ):
        self.success = success
        self.operation_type = operation_type  # 'trash', 'permanent', 'dry_run'
        self.trash_id = trash_id
        self.removed_links = removed_links or []
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'operation_type': self.operation_type,
            'trash_id': self.trash_id,
            'removed_links': self.removed_links,
            'error_message': self.error_message
        }


class DeletionManager:
    """
    Deletion orchestrator for hardlink-based environments.
    
    Provides:
    - Preview mode (dry-run)
    - Trash-based deletion (safe, reversible)
    - Permanent deletion (direct, irreversible)
    - Integration with organization database
    """

    def __init__(
        self,
        link_registry: LinkRegistry,
        trash_manager: TrashManager,
        organization_database=None,
        require_confirmation: bool = True,
        default_dry_run: bool = True
    ):
        """
        Initialize Deletion Manager
        
        Args:
            link_registry: Link registry instance
            trash_manager: Trash manager instance
            organization_database: Organization database instance (optional)
            require_confirmation: Require user confirmation for deletions
            default_dry_run: Default to dry-run mode
        """
        self.link_registry = link_registry
        self.trash_manager = trash_manager
        self.organization_database = organization_database
        self.require_confirmation = require_confirmation
        self.default_dry_run = default_dry_run
        self.logger = get_logger(__name__)

        log_info(self.logger, "Deletion Manager initialized")

    async def get_deletion_preview(self, path: Path) -> Dict[str, Any]:
        """
        Get preview of what would be deleted
        
        Args:
            path: File path to preview deletion
            
        Returns:
            Preview dictionary with all affected paths
        """
        preview = {
            'path': str(path),
            'exists': path.exists(),
            'all_links': [],
            'total_links': 0,
            'total_size_bytes': 0,
            'can_delete': False,
            'warning': None
        }

        if not path.exists():
            preview['warning'] = "File does not exist"
            return preview

        # Get all links from registry
        all_links = self.link_registry.get_all_links(path)

        if not all_links:
            # File not in registry, try to find by scanning
            preview['warning'] = "File not in registry - only this file will be deleted"
            preview['all_links'] = [{'path': str(path), 'type': 'unknown'}]
            preview['total_links'] = 1
            preview['can_delete'] = True
        else:
            preview['all_links'] = all_links
            preview['total_links'] = len(all_links)

            # Calculate total size (from first link)
            try:
                first_link = Path(all_links[0]['path'])
                if first_link.exists():
                    preview['total_size_bytes'] = first_link.stat().st_size
            except:
                pass

            preview['can_delete'] = True

        # Format size for display
        size_bytes = preview['total_size_bytes']
        if size_bytes >= 1024**3:
            preview['total_size_display'] = f"{size_bytes / (1024**3):.2f} GB"
        elif size_bytes >= 1024**2:
            preview['total_size_display'] = f"{size_bytes / (1024**2):.2f} MB"
        elif size_bytes >= 1024:
            preview['total_size_display'] = f"{size_bytes / 1024:.2f} KB"
        else:
            preview['total_size_display'] = f"{size_bytes} B"

        return preview

    async def delete_to_trash(
        self,
        path: Path,
        metadata: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> DeletionResult:
        """
        Delete file to trash (safe, reversible)
        
        Args:
            path: File path to delete
            metadata: Optional metadata to store
            dry_run: Preview mode
            
        Returns:
            DeletionResult
        """
        try:
            # Get preview
            preview = await self.get_deletion_preview(path)

            if not preview['can_delete']:
                return DeletionResult(
                    success=False,
                    operation_type='trash',
                    error_message=preview.get('warning', 'Cannot delete')
                )

            if dry_run:
                log_info(self.logger, f"[DRY-RUN] Would move to trash: {path}")
                return DeletionResult(
                    success=True,
                    operation_type='dry_run',
                    removed_links=[link['path'] for link in preview['all_links']]
                )

            # Move to trash
            trash_id = self.trash_manager.move_to_trash(
                primary_path=path,
                all_links=preview['all_links'],
                metadata=metadata
            )

            if not trash_id:
                return DeletionResult(
                    success=False,
                    operation_type='trash',
                    error_message="Failed to move to trash"
                )

            # Unregister from link registry
            self.link_registry.unregister_link(path)

            # Update organization database
            if self.organization_database:
                self._update_organization_database(path, 'deleted_via_trash')

            log_success(self.logger, f"Moved to trash: {path} (ID: {trash_id})")
            return DeletionResult(
                success=True,
                operation_type='trash',
                trash_id=trash_id,
                removed_links=[link['path'] for link in preview['all_links']]
            )

        except Exception as e:
            log_error(self.logger, f"Failed to delete to trash: {e}")
            return DeletionResult(
                success=False,
                operation_type='trash',
                error_message=str(e)
            )

    async def delete_permanent(
        self,
        path: Path,
        dry_run: bool = False,
        force: bool = False
    ) -> DeletionResult:
        """
        Delete file permanently (irreversible)
        
        Args:
            path: File path to delete
            dry_run: Preview mode
            force: Skip confirmation
            
        Returns:
            DeletionResult
        """
        try:
            # Get preview
            preview = await self.get_deletion_preview(path)

            if not preview['can_delete']:
                return DeletionResult(
                    success=False,
                    operation_type='permanent',
                    error_message=preview.get('warning', 'Cannot delete')
                )

            if dry_run:
                log_info(self.logger, f"[DRY-RUN] Would permanently delete: {path}")
                return DeletionResult(
                    success=True,
                    operation_type='dry_run',
                    removed_links=[link['path'] for link in preview['all_links']]
                )

            # Confirmation
            if not force and self.require_confirmation:
                if not self._confirm_permanent_deletion(preview):
                    return DeletionResult(
                        success=False,
                        operation_type='permanent',
                        error_message="User cancelled"
                    )

            # Create backup of organization database
            backup_path = None
            if self.organization_database:
                backup_path = self.organization_database.create_backup()
                if backup_path:
                    log_info(self.logger, f"Database backup created: {backup_path}")

            # Remove all hardlinks
            removed_links = []
            for link in preview['all_links']:
                link_path = Path(link['path'])
                if link_path.exists():
                    try:
                        link_path.unlink()
                        removed_links.append(str(link_path))
                        log_info(self.logger, f"Removed: {link_path}")
                    except Exception as e:
                        log_error(self.logger, f"Failed to remove {link_path}: {e}")
                        return DeletionResult(
                            success=False,
                            operation_type='permanent',
                            removed_links=removed_links,
                            error_message=f"Failed to remove {link_path}: {e}"
                        )

            # Unregister from link registry
            self.link_registry.unregister_link(path)

            # Update organization database
            if self.organization_database:
                self._update_organization_database(path, 'deleted_permanent')

            log_success(self.logger, f"Permanently deleted: {path}")
            return DeletionResult(
                success=True,
                operation_type='permanent',
                removed_links=removed_links
            )

        except Exception as e:
            log_error(self.logger, f"Failed to delete permanently: {e}")
            return DeletionResult(
                success=False,
                operation_type='permanent',
                error_message=str(e)
            )

    def _confirm_permanent_deletion(self, preview: Dict[str, Any]) -> bool:
        """
        Show confirmation prompt for permanent deletion
        
        Args:
            preview: Deletion preview dictionary
            
        Returns:
            True if user confirms
        """
        console.print()
        console.print("[bold red]⚠️  PERMANENT DELETION WARNING[/bold red]")
        console.print()
        console.print("The following files will be [bold red]PERMANENTLY DELETED[/bold red]:")
        console.print()

        for link in preview['all_links']:
            link_path = link.get('path', '')
            console.print(f"  [red]•[/red] {link_path}")

        console.print()
        console.print(f"Total size: [yellow]{preview['total_size_display']}[/yellow]")
        console.print()
        console.print("[bold red]This action CANNOT be undone.[/bold red]")
        console.print("All hard links will be removed and disk space will be freed.")
        console.print()

        # Require typing 'DELETE' to confirm
        response = input("Type 'DELETE' to confirm: ").strip()

        return response.upper() == 'DELETE'

    def _confirm_trash_deletion(self, preview: Dict[str, Any]) -> bool:
        """
        Show confirmation prompt for trash deletion
        
        Args:
            preview: Deletion preview dictionary
            
        Returns:
            True if user confirms
        """
        console.print()
        console.print("[bold yellow]🗑️  Move to Trash[/bold yellow]")
        console.print()
        console.print("The following hard links will be [bold]REMOVED[/bold]:")
        console.print()

        for link in preview['all_links']:
            link_path = link.get('path', '')
            console.print(f"  [yellow]•[/yellow] {link_path}")

        console.print()
        console.print(f"Total size: [cyan]{preview['total_size_display']}[/cyan]")
        console.print()
        console.print(f"A copy will be stored in trash for {self.trash_manager.retention_days} days.")
        console.print()

        return Confirm.ask("Are you sure?", default=False)

    def _update_organization_database(self, path: Path, deletion_type: str):
        """
        Update organization database after deletion
        
        Args:
            path: File path that was deleted
            deletion_type: Type of deletion ('deleted_via_trash' or 'deleted_permanent')
        """
        if not self.organization_database:
            return

        try:
            # Remove from organization database
            # Note: Implementation depends on database structure
            if hasattr(self.organization_database, 'remove_by_path'):
                self.organization_database.remove_by_path(str(path))
            elif hasattr(self.organization_database, 'media_table'):
                from tinydb import Query
                Media = Query()
                self.organization_database.media_table.remove(
                    (Media.original_path == str(path)) |
                    (Media.organized_path == str(path))
                )

            log_info(self.logger, f"Updated organization database: {deletion_type}")

        except Exception as e:
            log_error(self.logger, f"Failed to update organization database: {e}")

    async def restore_from_trash(self, trash_id: str, restore_paths: Optional[List[Path]] = None) -> bool:
        """
        Restore file from trash
        
        Args:
            trash_id: Trash item ID
            restore_paths: Optional custom restore paths
            
        Returns:
            True if successful
        """
        try:
            # Get trash item
            item = self.trash_manager.get_item(trash_id)
            if not item:
                log_error(self.logger, f"Trash item not found: {trash_id}")
                return False

            # Restore
            success = self.trash_manager.restore_from_trash(trash_id, restore_paths)

            if success:
                # Re-register in link registry if we have the paths
                if restore_paths and len(restore_paths) > 1:
                    self.link_registry.register_link(
                        source_path=restore_paths[0],
                        dest_path=restore_paths[1],
                        metadata=item.get('metadata', {})
                    )

                # Update organization database
                if self.organization_database:
                    # Re-add to database (implementation depends on structure)
                    pass

            return success

        except Exception as e:
            log_error(self.logger, f"Failed to restore from trash: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get deletion manager statistics
        
        Returns:
            Statistics dictionary
        """
        registry_stats = self.link_registry.get_stats()
        trash_stats = self.trash_manager.get_stats()

        return {
            'link_registry': registry_stats,
            'trash': trash_stats
        }

    def print_preview(self, preview: Dict[str, Any]):
        """
        Print deletion preview in formatted output
        
        Args:
            preview: Deletion preview dictionary
        """
        console.print()
        console.print("[bold cyan]Deletion Preview[/bold cyan]")
        console.print()

        if preview.get('warning'):
            console.print(f"[yellow]⚠ {preview['warning']}[/yellow]")
            console.print()

        console.print("Files that will be affected:")
        console.print()

        for link in preview['all_links']:
            link_path = link.get('path', '')
            link_type = link.get('type', 'unknown')
            console.print(f"  [cyan]•[/cyan] {link_path} [dim]({link_type})[/dim]")

        console.print()
        console.print(f"Total links: [bold]{preview['total_links']}[/bold]")
        console.print(f"Total size: [bold]{preview['total_size_display']}[/bold]")
        console.print()
