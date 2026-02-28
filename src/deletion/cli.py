#!/usr/bin/env python3
"""
Trash CLI for Media Organization System

Command-line interface for trash and deletion management.
Provides interactive menu and direct commands for:
- Deleting files to trash
- Permanent deletion
- Restoring from trash
- Emptying trash
- Link registry management

Usage:
    media-organizer trash                    # Interactive menu
    media-organizer trash delete <path>      # Delete to trash
    media-organizer trash delete-permanent <path>  # Permanent delete
    media-organizer trash list               # List trash items
    media-organizer trash restore <id>       # Restore from trash
    media-organizer trash empty              # Empty trash
    media-organizer trash status             # Show status
    media-organizer trash lookup <path>      # Lookup links
    media-organizer trash scan               # Scan filesystem
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from datetime import datetime

from src.config import Config
from src.log_config import get_logger, log_success, log_error, log_info, log_warning, set_console_log_level
from src.log_formatter import LogSection
from src.deletion import LinkRegistry, TrashManager, DeletionManager


console = Console()


class TrashCLI:
    """CLI for trash and deletion management"""

    def __init__(self, dry_run: bool = False):
        """Initialize Trash CLI"""
        self.config = Config()
        self.dry_run = dry_run
        self.logger = get_logger(__name__, dry_run=dry_run)

        # Set console log level
        set_console_log_level(logging.INFO if dry_run else logging.WARNING)

        # Initialize components
        self.link_registry = LinkRegistry(self.config.link_registry_path)
        self.trash_manager = TrashManager(self.config.trash_path, self.config.trash_retention_days)
        self.deletion_manager = DeletionManager(
            link_registry=self.link_registry,
            trash_manager=self.trash_manager,
            organization_database=None,  # Will be set if needed
            require_confirmation=self.config.delete_confirmation_required,
            default_dry_run=self.config.delete_dry_run_default
        )

    def show_interactive_menu(self):
        """Show interactive trash menu"""
        while True:
            console.print("\n[bold cyan]🗑️  Trash & Deletion Manager[/bold cyan]")
            console.print("[bold]Select an operation:[/bold]\n")

            options = {
                "1": "Delete file (to trash)",
                "2": "Delete permanent (direct)",
                "3": "List trash items",
                "4": "Restore from trash",
                "5": "Empty trash",
                "6": "Trash status",
                "7": "Scan filesystem (rebuild registry)",
                "8": "Link lookup",
                "0": "Back to main menu"
            }

            for key, value in options.items():
                console.print(f"  [{key}] {value}")

            try:
                choice = Prompt.ask("\nYour choice", choices=list(options.keys()), default="0")

                if choice == "0":
                    console.print("\n[blue]Returning to main menu...[/blue]")
                    return
                elif choice == "1":
                    self._delete_to_trash_interactive()
                elif choice == "2":
                    self._delete_permanent_interactive()
                elif choice == "3":
                    self._list_trash_interactive()
                elif choice == "4":
                    self._restore_from_trash_interactive()
                elif choice == "5":
                    self._empty_trash_interactive()
                elif choice == "6":
                    self._show_status_interactive()
                elif choice == "7":
                    self._scan_filesystem_interactive()
                elif choice == "8":
                    self._lookup_links_interactive()

                # Pause before showing menu again
                if choice != "0":
                    input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                console.print("\n[red]Operation cancelled by user.[/red]")
                return
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    def _delete_to_trash_interactive(self):
        """Interactive delete to trash"""
        console.print("\n[bold cyan]🗑️  Delete File (to Trash)[/bold cyan]\n")

        file_path = Prompt.ask("Enter file path")
        path = Path(file_path)

        if not path.exists():
            console.print(f"[red]✗ File not found: {path}[/red]")
            return

        # Get preview
        preview = asyncio.run(self.deletion_manager.get_deletion_preview(path))
        self.deletion_manager.print_preview(preview)

        if not preview.get('can_delete', False):
            console.print(f"[red]✗ Cannot delete: {preview.get('warning', 'Unknown error')}[/red]")
            return

        # Confirm
        if not self.deletion_manager._confirm_trash_deletion(preview):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        # Execute deletion
        result = asyncio.run(self.deletion_manager.delete_to_trash(
            path=path,
            dry_run=self.dry_run
        ))

        if result.success:
            if self.dry_run:
                console.print(f"\n[green]✓ [DRY-RUN] Would move to trash: {path}[/green]")
            else:
                console.print(f"\n[green]✓ Moved to trash: {path}[/green]")
                console.print(f"  Trash ID: [cyan]{result.trash_id}[/cyan]")
                console.print(f"  Removed {len(result.removed_links)} link(s)")
        else:
            console.print(f"\n[red]✗ Failed: {result.error_message}[/red]")

    def _delete_permanent_interactive(self):
        """Interactive permanent deletion"""
        console.print("\n[bold red]⚠️  Permanent Deletion[/bold red]\n")

        file_path = Prompt.ask("Enter file path")
        path = Path(file_path)

        if not path.exists():
            console.print(f"[red]✗ File not found: {path}[/red]")
            return

        # Get preview
        preview = asyncio.run(self.deletion_manager.get_deletion_preview(path))
        self.deletion_manager.print_preview(preview)

        if not preview.get('can_delete', False):
            console.print(f"[red]✗ Cannot delete: {preview.get('warning', 'Unknown error')}[/red]")
            return

        # Execute deletion (confirmation is shown inside delete_permanent)
        result = asyncio.run(self.deletion_manager.delete_permanent(
            path=path,
            dry_run=self.dry_run,
            force=False
        ))

        if result.success:
            if self.dry_run:
                console.print(f"\n[green]✓ [DRY-RUN] Would permanently delete: {path}[/green]")
            else:
                console.print(f"\n[green]✓ Permanently deleted: {path}[/green]")
                console.print(f"  Removed {len(result.removed_links)} link(s)")
        else:
            console.print(f"\n[red]✗ Failed: {result.error_message}[/red]")

    def _list_trash_interactive(self):
        """List trash items"""
        console.print("\n[bold cyan]📋 Trash Items[/bold cyan]\n")

        items = self.trash_manager.list_items(active_only=True)

        if not items:
            console.print("[yellow]Trash is empty.[/yellow]")
            return

        table = Table(box=None, show_header=True, header_style="bold cyan")
        table.add_column("ID", style="cyan")
        table.add_column("Original Path", style="white")
        table.add_column("Size", style="green")
        table.add_column("Created", style="blue")
        table.add_column("Days Left", style="yellow")

        for item in items:
            table.add_row(
                item.get('trash_id', 'N/A'),
                item.get('original_path', 'N/A')[:60] + "..." if len(item.get('original_path', '')) > 60 else item.get('original_path', 'N/A'),
                item.get('size_display', 'N/A'),
                item.get('created_at', 'N/A')[:10] if item.get('created_at') else 'N/A',
                str(item.get('days_remaining', 'N/A'))
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(items)} item(s)[/dim]")

    def _restore_from_trash_interactive(self):
        """Restore from trash"""
        console.print("\n[bold cyan]📥 Restore from Trash[/bold cyan]\n")

        # First show items
        self._list_trash_interactive()

        trash_id = Prompt.ask("\nEnter trash ID to restore")

        # Get item
        item = self.trash_manager.get_item(trash_id)
        if not item:
            console.print(f"[red]✗ Trash item not found: {trash_id}[/red]")
            return

        console.print(f"\nRestoring: [cyan]{item.get('original_path', 'N/A')}[/cyan]")
        console.print(f"Size: [green]{item.get('size_display', 'N/A')}[/green]")

        if not Confirm.ask("\nConfirm restore?", default=True):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        # Restore
        success = self.trash_manager.restore_from_trash(trash_id)

        if success:
            console.print(f"\n[green]✓ Restored from trash: {trash_id}[/green]")
        else:
            console.print(f"\n[red]✗ Failed to restore: {trash_id}[/red]")

    def _empty_trash_interactive(self):
        """Empty trash"""
        console.print("\n[bold yellow]🗑️  Empty Trash[/bold yellow]\n")

        stats = self.trash_manager.get_stats()
        active_items = stats.get('active_items', 0)

        if active_items == 0:
            console.print("[green]Trash is already empty.[/green]")
            return

        console.print(f"Active items in trash: [bold]{active_items}[/bold]")
        console.print(f"Total size: [bold]{stats.get('total_size_gb', 0):.2f} GB[/bold]")
        console.print()

        mode = Prompt.ask(
            "Empty mode",
            choices=["all", "expired", "cancel"],
            default="all"
        )

        if mode == "cancel":
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        if not Confirm.ask("\nThis action cannot be undone. Confirm?", default=False):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        if mode == "expired":
            removed = self.trash_manager.cleanup_expired()
            console.print(f"\n[green]✓ Removed {removed} expired item(s)[/green]")
        else:
            result = self.trash_manager.empty_trash()
            console.print(f"\n[green]✓ Emptied trash: {result['items_removed']} item(s) removed[/green]")
            console.print(f"  Space freed: {result['space_freed_bytes'] / (1024**3):.2f} GB")

    def _show_status_interactive(self):
        """Show trash status"""
        console.print("\n[bold cyan]📊 Trash & Deletion Status[/bold cyan]\n")

        # Trash stats
        trash_stats = self.trash_manager.get_stats()
        registry_stats = self.link_registry.get_stats()

        # Trash table
        table1 = Table(title="Trash Statistics", box=None, show_header=True, header_style="bold cyan")
        table1.add_column("Metric", style="cyan")
        table1.add_column("Value", style="green")

        table1.add_row("Total Items", str(trash_stats.get('total_items', 0)))
        table1.add_row("Active Items", str(trash_stats.get('active_items', 0)))
        table1.add_row("Restored Items", str(trash_stats.get('restored_items', 0)))
        table1.add_row("Expired Items", str(trash_stats.get('expired_items', 0)))
        table1.add_row("Total Size", f"{trash_stats.get('total_size_gb', 0):.2f} GB")
        table1.add_row("Retention Days", str(trash_stats.get('retention_days', 30)))

        console.print(table1)

        # Registry table
        table2 = Table(title="Link Registry Statistics", box=None, show_header=True, header_style="bold cyan")
        table2.add_column("Metric", style="cyan")
        table2.add_column("Value", style="green")

        table2.add_row("Total Inodes", str(registry_stats.get('total_inodes', 0)))
        table2.add_row("Total Links", str(registry_stats.get('total_links', 0)))
        table2.add_row("Original Links", str(registry_stats.get('original_links', 0)))
        table2.add_row("Organized Links", str(registry_stats.get('organized_links', 0)))
        table2.add_row("Total Size", f"{registry_stats.get('total_size_gb', 0):.2f} GB")

        console.print(table2)

    def _scan_filesystem_interactive(self):
        """Scan filesystem to rebuild registry"""
        console.print("\n[bold cyan]🔍 Scan Filesystem[/bold cyan]\n")

        # Get directories to scan
        download_paths = self.config.get_all_download_paths()
        library_paths = self.config.get_all_library_paths()

        all_paths = list(download_paths.values()) + list(library_paths.values())
        all_paths = [p for p in all_paths if p and p != Path("") and p.exists()]

        if not all_paths:
            console.print("[red]✗ No valid directories to scan.[/red]")
            return

        console.print(f"Directories to scan: [cyan]{len(all_paths)}[/cyan]")
        for path in all_paths[:5]:
            console.print(f"  • {path}")
        if len(all_paths) > 5:
            console.print(f"  ... and {len(all_paths) - 5} more")
        console.print()

        if not Confirm.ask("Start filesystem scan?", default=True):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        # Scan
        def progress_callback(stats):
            console.print(f"\r[dim]Scanned {stats['files_scanned']} files...[/dim]", end="")

        console.print("[dim]Scanning...[/dim]")
        stats = self.link_registry.scan_filesystem(all_paths, progress_callback)

        console.print(f"\r[green]✓ Scan complete![/green]            ")
        console.print(f"  Files scanned: {stats['files_scanned']}")
        console.print(f"  Inodes registered: {stats['inodes_registered']}")
        console.print(f"  Links found: {stats['links_found']}")
        console.print(f"  Errors: {stats['errors']}")

    def _lookup_links_interactive(self):
        """Lookup links for a file"""
        console.print("\n[bold cyan]🔎 Link Lookup[/bold cyan]\n")

        file_path = Prompt.ask("Enter file path")
        path = Path(file_path)

        if not path.exists():
            console.print(f"[red]✗ File not found: {path}[/red]")
            return

        # Get all links
        all_links = self.link_registry.get_all_links(path)

        if not all_links:
            console.print(f"[yellow]⚠ File not in registry.[/yellow]")
            console.print("Only this file would be deleted (no other hardlinks found).")
            return

        # Get inode
        inode = self.link_registry.get_inode(path)
        hardlink_count = self.link_registry.get_hardlink_count(path)

        console.print(f"\n[cyan]Inode:[/cyan] {inode}")
        console.print(f"[cyan]Hardlink count:[/cyan] {hardlink_count}")
        console.print()
        console.print("[bold]All hardlinks:[/bold]")
        console.print()

        for link in all_links:
            link_path = link.get('path', '')
            link_type = link.get('type', 'unknown')
            exists = Path(link_path).exists()
            status = "[green]✓[/green]" if exists else "[red]✗[/red]"
            console.print(f"  {status} {link_path} [dim]({link_type})[/dim]")

        console.print()
        console.print(f"Total: [bold]{len(all_links)}[/bold] link(s)")

    def cleanup(self):
        """Cleanup resources"""
        self.link_registry.close()
        self.trash_manager.close()


# ============================================================================
# CLI Commands (for direct invocation)
# ============================================================================

def trash_delete(path: str, dry_run: bool = False):
    """Delete file to trash"""
    cli = TrashCLI(dry_run=dry_run)
    try:
        result = asyncio.run(cli.deletion_manager.delete_to_trash(
            path=Path(path),
            dry_run=dry_run
        ))
        if result.success:
            log_success(cli.logger, f"Deleted to trash: {path}")
        else:
            log_error(cli.logger, f"Failed: {result.error_message}")
    finally:
        cli.cleanup()


def trash_delete_permanent(path: str, dry_run: bool = False, force: bool = False):
    """Delete file permanently"""
    cli = TrashCLI(dry_run=dry_run)
    try:
        result = asyncio.run(cli.deletion_manager.delete_permanent(
            path=Path(path),
            dry_run=dry_run,
            force=force
        ))
        if result.success:
            log_success(cli.logger, f"Permanently deleted: {path}")
        else:
            log_error(cli.logger, f"Failed: {result.error_message}")
    finally:
        cli.cleanup()


def trash_list(active_only: bool = True):
    """List trash items"""
    cli = TrashCLI()
    try:
        items = cli.trash_manager.list_items(active_only=active_only)
        if not items:
            console.print("[yellow]Trash is empty.[/yellow]")
            return

        table = Table(box=None, show_header=True, header_style="bold cyan")
        table.add_column("ID", style="cyan")
        table.add_column("Original Path", style="white")
        table.add_column("Size", style="green")
        table.add_column("Created", style="blue")
        table.add_column("Days Left", style="yellow")

        for item in items:
            table.add_row(
                item.get('trash_id', 'N/A'),
                item.get('original_path', 'N/A')[:50] + "..." if len(item.get('original_path', '')) > 50 else item.get('original_path', 'N/A'),
                item.get('size_display', 'N/A'),
                item.get('created_at', 'N/A')[:10] if item.get('created_at') else 'N/A',
                str(item.get('days_remaining', 'N/A'))
            )

        console.print(table)
    finally:
        cli.cleanup()


def trash_restore(trash_id: str):
    """Restore item from trash"""
    cli = TrashCLI()
    try:
        success = cli.trash_manager.restore_from_trash(trash_id)
        if success:
            log_success(cli.logger, f"Restored: {trash_id}")
        else:
            log_error(cli.logger, f"Failed to restore: {trash_id}")
    finally:
        cli.cleanup()


def trash_empty(older_than_days: int = None):
    """Empty trash"""
    cli = TrashCLI()
    try:
        result = cli.trash_manager.empty_trash(older_than_days=older_than_days)
        log_success(cli.logger, f"Emptied trash: {result['items_removed']} items removed")
    finally:
        cli.cleanup()


def trash_status():
    """Show trash status"""
    cli = TrashCLI()
    try:
        stats = cli.deletion_manager.get_stats()

        console.print("\n[bold cyan]📊 Trash & Deletion Status[/bold cyan]\n")

        # Trash stats
        table1 = Table(title="Trash Statistics", box=None, show_header=True, header_style="bold cyan")
        table1.add_column("Metric", style="cyan")
        table1.add_column("Value", style="green")

        trash_stats = stats.get('trash', {})
        table1.add_row("Total Items", str(trash_stats.get('total_items', 0)))
        table1.add_row("Active Items", str(trash_stats.get('active_items', 0)))
        table1.add_row("Total Size", f"{trash_stats.get('total_size_gb', 0):.2f} GB")
        table1.add_row("Retention Days", str(trash_stats.get('retention_days', 30)))

        console.print(table1)

        # Registry stats
        registry_stats = stats.get('link_registry', {})
        table2 = Table(title="Link Registry Statistics", box=None, show_header=True, header_style="bold cyan")
        table2.add_column("Metric", style="cyan")
        table2.add_column("Value", style="green")

        table2.add_row("Total Inodes", str(registry_stats.get('total_inodes', 0)))
        table2.add_row("Total Links", str(registry_stats.get('total_links', 0)))
        table2.add_row("Total Size", f"{registry_stats.get('total_size_gb', 0):.2f} GB")

        console.print(table2)
    finally:
        cli.cleanup()


def trash_lookup(path: str):
    """Lookup links for a file"""
    cli = TrashCLI()
    try:
        preview = asyncio.run(cli.deletion_manager.get_deletion_preview(Path(path)))
        cli.deletion_manager.print_preview(preview)
    finally:
        cli.cleanup()


def trash_scan():
    """Scan filesystem to rebuild registry"""
    cli = TrashCLI()
    try:
        config = Config()
        download_paths = config.get_all_download_paths()
        library_paths = config.get_all_library_paths()

        all_paths = list(download_paths.values()) + list(library_paths.values())
        all_paths = [p for p in all_paths if p and p != Path("") and p.exists()]

        if not all_paths:
            console.print("[red]✗ No valid directories to scan.[/red]")
            return

        stats = cli.link_registry.scan_filesystem(all_paths)
        console.print(f"\n[green]✓ Scan complete![/green]")
        console.print(f"  Files scanned: {stats['files_scanned']}")
        console.print(f"  Inodes registered: {stats['inodes_registered']}")
        console.print(f"  Links found: {stats['links_found']}")
        console.print(f"  Errors: {stats['errors']}")
    finally:
        cli.cleanup()
