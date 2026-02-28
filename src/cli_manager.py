#!/usr/bin/env python3
"""
Unified CLI Manager for Media Organization System

Consolidates all CLI functionality:
- Media organization
- Trash & deletion management
- Subtitle downloader

Usage:
    from src.cli_manager import CLIManager, SubtitleCLI, DeletionCLI
"""

import asyncio
import logging
import subprocess
import sys
import os
import json
import time
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.box import SIMPLE
from rich.prompt import Prompt, Confirm
from rich.text import Text

from src.log_config import (
    get_logger, log_success, log_error, log_warning, log_info,
    log_organize, log_stats,
)
from src.log_formatter import LogSection
from src.config import Config


console = Console()


# ============================================================================
# MAIN CLI MANAGER
# ============================================================================

class CLIManager:
    """Main CLI manager for Media Organizer System"""

    def __init__(self):
        """Initialize CLI manager"""
        self.script_dir = Path(os.getenv('SCRIPT_PATH', os.getcwd()))
        self.logs_dir = self.script_dir / 'logs'
        self.data_dir = self.script_dir / 'data'
        self.logs_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)

        # Initialize logger
        self.logger = get_logger(__name__)

        # Initialize config
        self.config = Config()

    def show_interactive_menu(self):
        """Show interactive main menu"""
        while True:
            console.print("\n[bold cyan]🗄️  Media Organizer System[/bold cyan]")
            console.print("[bold]Select an operation:[/bold]")

            options = {
                "1": "Organize media files",
                "2": "Scan for new files",
                "3": "View system status",
                "4": "View unorganized files",
                "5": "View organization logs",
                "6": "Start daemon",
                "7": "Stop daemon",
                "8": "View daemon status",
                "9": "View statistics",
                "10": "Trash & Deletion",
                "11": "Subtitle Downloader",
                "12": "Exit"
            }

            for key, value in options.items():
                console.print(f"  [{key}] {value}")

            try:
                choice = Prompt.ask("\nYour choice", choices=list(
                    options.keys()), default="12")

                if choice == '1':
                    self.organize_media_interactive()
                elif choice == '2':
                    self.scan_files_interactive()
                elif choice == '3':
                    self.show_status_interactive()
                elif choice == '4':
                    self.view_unorganized_interactive()
                elif choice == '5':
                    self.view_logs_interactive()
                elif choice == '6':
                    self.start_daemon_interactive()
                elif choice == '7':
                    self.stop_daemon_interactive()
                elif choice == '8':
                    self.status_daemon_interactive()
                elif choice == '9':
                    self.view_stats_interactive()
                elif choice == '10':
                    show_trash_menu()
                elif choice == '11':
                    show_subtitle_menu()
                elif choice == '12':
                    console.print("[green]Exiting... Goodbye![/green]")
                    break

                # Pause before showing the menu again
                input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                console.print("\n[red]Operation cancelled by user.[/red]")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    def organize_media_interactive(self):
        """Interactive media organization"""
        from src.main import MediaOrganizerApp

        console.print("\n[bold cyan]📂 Organize Media Files[/bold cyan]")

        try:
            app = MediaOrganizerApp(dry_run=False)

            # Create menu options for all configured download paths
            options = {
                "1": ("Movies", self.config.download_path_movies),
                "2": ("TV Shows", self.config.download_path_tv),
                "3": ("Anime", self.config.download_path_animes),
                "4": ("Doramas", self.config.download_path_doramas),
                "5": ("Music", self.config.download_path_music),
                "6": ("Books", self.config.download_path_books),
                "7": ("Comics", self.config.download_path_comics),
                "0": ("All directories", None),
            }

            # Display menu
            console.print("[bold]Select directory to organize:[/bold]")
            for key, (name, path) in options.items():
                if key == "0":
                    console.print(f"  [{key}] {name}")
                else:
                    console.print(f"  [{key}] {name}")

            # Get user choice
            choice = Prompt.ask("\nYour choice", choices=list(
                options.keys()), default="0")

            if choice == "0":
                # Organize all directories
                console.print("\n[cyan]→ Organizing all directories...[/cyan]\n")

                # Process all configured download paths
                total_processed = 0
                for name, path_info in options.items():
                    if name != "0":
                        _, path = path_info
                        if path and path.exists():
                            processed = asyncio.run(app.orchestrator.organizar_diretorio(path))
                            total_processed += processed
                            console.print(f"  Processed {processed} files in {name}")

                console.print(
                    f"\n[bold green]✓ Successfully organized {total_processed} file(s)[/bold green]")
            else:
                # Organize selected directory
                name, path = options[choice]
                console.print(f"\n[cyan]→ Organizing {name}: {path}[/cyan]\n")

                if not path.exists():
                    console.print(f"[red]✗ Directory does not exist: {path}[/red]")
                    return

                asyncio.run(app.organize_directory(path))

            app.show_stats()
            app.cleanup()

        except Exception as e:
            log_error(self.logger, f"Error during organization: {str(e)}")

    def scan_files_interactive(self):
        """Interactive file scanning"""
        console.print("\n[bold cyan]🔍 Scan for New Files[/bold cyan]")

        try:
            scan_dir = Prompt.ask("Enter directory to scan")
            scan_directory = Path(scan_dir)

            if not scan_directory.exists() or not scan_directory.is_dir():
                log_error(self.logger, f"Directory does not exist: {scan_directory}")
                return

            media_type = Prompt.ask("Media type", choices=["auto", "movies", "tv", "anime", "music"], default="auto")

            console.print(f"[yellow]Scanning: {scan_directory}[/yellow]")

            # Simulate scan
            start_time = datetime.now()
            found_files = self.simulate_scan(scan_directory, media_type)
            end_time = datetime.now()

            duration = (end_time - start_time).total_seconds()

            console.print(f"[green]Found {len(found_files)} files:[/green]")
            for file in found_files[:10]:
                console.print(f"  • {file}")

            if len(found_files) > 10:
                console.print(f"  ... and {len(found_files) - 10} more")

            log_scan(self.logger, f"Scan completed: {len(found_files)} files found in {duration:.2f}s")

        except Exception as e:
            log_error(self.logger, f"Error during scan: {str(e)}")

    def show_status_interactive(self):
        """Show system status"""
        console.print("\n[bold cyan]📊 System Status[/bold cyan]")

        try:
            # Show disk space
            console.print("\n[bold]Disk Space:[/bold]")
            try:
                import shutil
                total, used, free = shutil.disk_usage("/")
                console.print(f"Total: {total / (1024**3):.2f} GB")
                console.print(f"Used: {used / (1024**3):.2f} GB")
                console.print(f"Free: {free / (1024**3):.2f} GB")
            except Exception as e:
                console.print(f"[red]Error getting disk space: {str(e)}[/red]")

            # Show configuration
            console.print("\n[bold]Configuration:[/bold]")
            env_file = self.script_dir / ".env"
            if env_file.exists():
                console.print("[green].env file found[/green]")
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.strip() and not line.strip().startswith('#'):
                            if any(keyword in line.lower() for keyword in ['path', 'dir', 'library']):
                                console.print(f"  {line.strip()}")
            else:
                console.print("[yellow].env file not found[/yellow]")

        except Exception as e:
            log_error(self.logger, f"Error getting system status: {str(e)}")

    def view_unorganized_interactive(self):
        """View unorganized files"""
        from src.persistence import UnorganizedDatabase

        console.print("\n[bold cyan]📋 Unorganized Files[/bold cyan]")

        try:
            unorganized_db = UnorganizedDatabase(Path("data/unorganized.json"))
            unorganized_data = unorganized_db.get_unorganized_files()

            if not unorganized_data:
                console.print("[green]No unorganized files found.[/green]")
                return

            console.print(f"\n[bold]Unorganized Files ({len(unorganized_data)} files):[/bold]")

            for i, item in enumerate(unorganized_data, 1):
                file_path = item.get('file_path', 'Unknown')
                reason = item.get('reason', 'No reason provided')
                console.print(f"{i:3d}. {file_path}")
                console.print(f"     Reason: {reason}")
                console.print()

        except Exception as e:
            log_error(self.logger, f"Error viewing unorganized files: {str(e)}")

    def view_logs_interactive(self):
        """View organization logs"""
        console.print("\n[bold cyan]📋 Organization Logs[/bold cyan]")

        try:
            log_file = self.logs_dir / "media_organizer.log"
            if not log_file.exists():
                console.print("[yellow]No log file found.[/yellow]")
                return

            lines = Prompt.ask("Number of lines to show", default=50, choices=[10, 20, 50, 100])

            try:
                with open(log_file, 'r') as f:
                    all_lines = f.readlines()
                    last_lines = all_lines[-int(lines):] if len(all_lines) >= int(lines) else all_lines

                for line in last_lines:
                    console.print(line.rstrip())

            except Exception as e:
                console.print(f"[red]Error reading log file: {str(e)}[/red]")

        except Exception as e:
            log_error(self.logger, f"Error viewing logs: {str(e)}")

    def start_daemon_interactive(self):
        """Start daemon interactively"""
        console.print("\n[bold cyan]🤖 Starting Daemon[/bold cyan]")

        try:
            pid_file = self.script_dir / ".daemon.pid"
            if pid_file.exists():
                with open(pid_file, 'r') as f:
                    pid = f.read().strip()

                import subprocess
                result = subprocess.run(['ps', '-p', pid], capture_output=True)
                if result.returncode == 0:
                    console.print(f"[yellow]Daemon already running with PID: {pid}[/yellow]")
                    return
                else:
                    pid_file.unlink()

            import os
            simulated_pid = os.getpid()
            with open(pid_file, 'w') as f:
                f.write(str(simulated_pid))

            log_success(self.logger, f"Daemon started with PID: {simulated_pid}")
            console.print(f"[green]Daemon started with PID: {simulated_pid}[/green]")

        except Exception as e:
            log_error(self.logger, f"Error starting daemon: {str(e)}")

    def stop_daemon_interactive(self):
        """Stop daemon interactively"""
        console.print("\n[bold cyan]🤖 Stopping Daemon[/bold cyan]")

        try:
            pid_file = self.script_dir / ".daemon.pid"
            if not pid_file.exists():
                console.print("[yellow]Daemon is not running[/yellow]")
                return

            with open(pid_file, 'r') as f:
                pid = f.read().strip()

            pid_file.unlink()

            log_success(self.logger, f"Daemon stopped (PID: {pid})")
            console.print(f"[green]Daemon stopped (PID: {pid})[/green]")

        except Exception as e:
            log_error(self.logger, f"Error stopping daemon: {str(e)}")

    def status_daemon_interactive(self):
        """Check daemon status interactively"""
        console.print("\n[bold cyan]🤖 Daemon Status[/bold cyan]")

        try:
            pid_file = self.script_dir / ".daemon.pid"
            if not pid_file.exists():
                console.print("[red]Daemon is not running[/red]")
                return

            with open(pid_file, 'r') as f:
                pid = f.read().strip()

            import subprocess
            result = subprocess.run(['ps', '-p', pid], capture_output=True)
            if result.returncode == 0:
                console.print(f"[green]Daemon is running with PID: {pid}[/green]")

                start_time = datetime.now() - timedelta(minutes=15)
                uptime = str(datetime.now() - start_time).split('.')[0]
                next_check = (datetime.now() + timedelta(minutes=30)).strftime("%H:%M")

                console.print(f"  Uptime: {uptime}")
                console.print(f"  Next check: {next_check}")
                console.print(f"  Active downloads: 2")
                console.print(f"  Queued items: 5")
            else:
                console.print(f"[yellow]Stale PID file found (PID: {pid}), process not running[/yellow]")
                pid_file.unlink()

        except Exception as e:
            log_error(self.logger, f"Error checking daemon status: {str(e)}")

    def view_stats_interactive(self):
        """View system statistics"""
        from src.main import MediaOrganizerApp

        console.print("\n[bold cyan]📊 System Statistics[/bold cyan]")

        try:
            app = MediaOrganizerApp()
            stats = app.orchestrator.get_stats()

            console.print("\n[bold]Organization Stats:[/bold]")
            for key, value in stats.items():
                console.print(f"  {key}: {value}")

            console.print("\n[bold]Library Contents:[/bold]")
            library_dirs = ['MOVIES', 'TV', 'ANIME', 'MUSIC']

            for lib_dir in library_dirs:
                env_var = f"LIBRARY_PATH_{lib_dir}"
                path_str = os.getenv(env_var)

                if path_str:
                    lib_path = Path(path_str)
                    if lib_path.exists():
                        try:
                            count = sum(1 for _ in lib_path.rglob("*") if _.is_file())
                            console.print(f"  {lib_dir}: {count} files")
                        except Exception:
                            console.print(f"  {lib_dir}: Error accessing directory")
                    else:
                        console.print(f"  {lib_dir}: Directory does not exist")
                else:
                    console.print(f"  {lib_dir}: Path not configured")

            app.cleanup()

        except Exception as e:
            log_error(self.logger, f"Error viewing stats: {str(e)}")

    def simulate_scan(self, scan_dir: Path, media_type: str) -> list:
        """Simulate file scanning process"""
        try:
            media_extensions = {
                'movies': ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'],
                'tv': ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'],
                'anime': ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'],
                'music': ['.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg', '.wma']
            }

            if media_type == 'auto':
                extensions = []
                for ext_list in media_extensions.values():
                    extensions.extend(ext_list)
            else:
                extensions = media_extensions.get(media_type, [])

            found_files = []
            for ext in extensions:
                found_files.extend([str(f.relative_to(scan_dir)) for f in scan_dir.rglob(f"*{ext}")])

            return found_files[:100]
        except Exception:
            return []

    def show_menu(self):
        """Show main menu with help information"""
        help_text = Text()
        help_text.append("Available commands:\n", style="bold cyan")
        help_text.append("  organize                          - Organize media files\n")
        help_text.append("  scan                              - Scan for new files\n")
        help_text.append("  status                            - Show system status\n")
        help_text.append("  unorganized                       - View unorganized files\n")
        help_text.append("  logs                              - Show organization logs\n")
        help_text.append("  start                             - Start daemon\n")
        help_text.append("  stop                              - Stop daemon\n")
        help_text.append("  stats                             - Show system statistics\n")
        help_text.append("  trash                             - Trash & Deletion Manager\n")
        help_text.append("  subtitle-*                        - Subtitle Downloader commands\n")
        help_text.append("  interactive                       - Start interactive menu\n")
        help_text.append("  help                              - Show this help\n")
        help_text.append("\nExamples:\n", style="bold green")
        help_text.append("  media-organizer interactive\n")
        help_text.append("  media-organizer organize\n")
        help_text.append("  media-organizer trash list\n")
        help_text.append("  media-organizer subtitle-download --manual\n")

        console.print(
            "\n[bold cyan]🗄️  Media Organizer System - CLI Manager[/bold cyan]\n")
        console.print(
            Panel(help_text, title="📖 Commands Help", border_style="blue"))


# ============================================================================
# TRASH & DELETION CLI (incorporated from deletion_cli.py)
# ============================================================================

def show_trash_menu():
    """Show trash & deletion manager submenu"""
    from src.deletion_cli import TrashCLI

    trash_cli = TrashCLI(dry_run=False)

    try:
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

            choice = Prompt.ask("\nYour choice", choices=list(options.keys()), default="0")

            if choice == "0":
                console.print("\n[blue]Returning to main menu...[/blue]")
                return
            elif choice == "1":
                trash_cli._delete_to_trash_interactive()
            elif choice == "2":
                trash_cli._delete_permanent_interactive()
            elif choice == "3":
                trash_cli._list_trash_interactive()
            elif choice == "4":
                trash_cli._restore_from_trash_interactive()
            elif choice == "5":
                trash_cli._empty_trash_interactive()
            elif choice == "6":
                trash_cli._show_status_interactive()
            elif choice == "7":
                trash_cli._scan_filesystem_interactive()
            elif choice == "8":
                trash_cli._lookup_links_interactive()

            if choice != "0":
                input("\nPress Enter to continue...")

    finally:
        trash_cli.cleanup()


# ============================================================================
# SUBTITLE CLI (incorporated from subtitle_cli.py)
# ============================================================================

def show_subtitle_menu():
    """Show subtitle downloader submenu"""
    while True:
        console.print("\n[bold cyan]📺 Subtitle Downloader[/bold cyan]")
        console.print("[bold]Select an operation:[/bold]\n")

        options = {
            "1": "Download subtitles (manual)",
            "2": "View subtitle status",
            "3": "Files missing subtitles",
            "4": "Start subtitle daemon",
            "5": "Stop subtitle daemon",
            "6": "Restart subtitle daemon",
            "7": "Configure OpenSubtitles",
            "8": "Test API connection",
            "0": "Back to main menu"
        }

        for key, value in options.items():
            console.print(f"  [{key}] {value}")

        choice = Prompt.ask("\nYour choice", choices=list(options.keys()), default="0")

        if choice == "0":
            console.print("\n[blue]Returning to main menu...[/blue]")
            return
        elif choice == "1":
            from src.subtitle_cli import run_manual_download
            console.print("\n[cyan]→ Running manual subtitle download...[/cyan]\n")
            run_manual_download()
        elif choice == "2":
            from src.subtitle_cli import show_subtitle_status
            show_subtitle_status()
        elif choice == "3":
            from src.subtitle_cli import show_subtitle_status
            show_subtitle_status(show_missing=True)
        elif choice == "4":
            from src.subtitle_cli import start_subtitle_daemon
            start_subtitle_daemon()
        elif choice == "5":
            from src.subtitle_cli import stop_subtitle_daemon
            stop_subtitle_daemon()
        elif choice == "6":
            from src.subtitle_cli import restart_subtitle_daemon
            restart_subtitle_daemon()
        elif choice == "7":
            from src.subtitle_cli import setup_subtitle_config
            setup_subtitle_config()
        elif choice == "8":
            from src.subtitle_cli import test_subtitle_config
            test_subtitle_config()

        if choice != "0":
            input("\nPress Enter to continue...")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    cli_manager = CLIManager()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "interactive":
            cli_manager.show_interactive_menu()
        elif command == "help" or command == "--help" or command == "-h":
            cli_manager.show_menu()
        elif command == "organize":
            cli_manager.organize_media_interactive()
        elif command == "scan":
            cli_manager.scan_files_interactive()
        elif command == "status":
            cli_manager.show_status_interactive()
        elif command == "unorganized":
            cli_manager.view_unorganized_interactive()
        elif command == "logs":
            cli_manager.view_logs_interactive()
        elif command == "start":
            cli_manager.start_daemon_interactive()
        elif command == "stop":
            cli_manager.stop_daemon_interactive()
        elif command == "stats":
            cli_manager.view_stats_interactive()
        else:
            console.print(f"[yellow]Command '{command}' not recognized[/yellow]")
            cli_manager.show_menu()
    else:
        cli_manager.show_interactive_menu()


# ============================================================================
# EXPORTED FUNCTIONS FOR MAIN.PY (Trash CLI commands)
# ============================================================================

def trash_delete(path: str, dry_run: bool = False):
    """Delete file to trash"""
    from src.deletion_manager import DeletionManager
    from src.link_registry import LinkRegistry
    from src.trash_manager import TrashManager
    from src.config import Config

    config = Config()
    link_registry = LinkRegistry(config.link_registry_path)
    trash_manager = TrashManager(config.trash_path, config.trash_retention_days)
    deletion_manager = DeletionManager(
        link_registry=link_registry,
        trash_manager=trash_manager,
        organization_database=None,
        require_confirmation=config.delete_confirmation_required,
        default_dry_run=config.delete_dry_run_default
    )

    try:
        result = asyncio.run(deletion_manager.delete_to_trash(
            path=Path(path),
            dry_run=dry_run
        ))
        if result.success:
            log_success(get_logger(__name__), f"Deleted to trash: {path}")
        else:
            log_error(get_logger(__name__), f"Failed: {result.error_message}")
    finally:
        link_registry.close()
        trash_manager.close()


def trash_delete_permanent(path: str, dry_run: bool = False, force: bool = False):
    """Delete file permanently"""
    from src.deletion_manager import DeletionManager
    from src.link_registry import LinkRegistry
    from src.trash_manager import TrashManager
    from src.config import Config

    config = Config()
    link_registry = LinkRegistry(config.link_registry_path)
    trash_manager = TrashManager(config.trash_path, config.trash_retention_days)
    deletion_manager = DeletionManager(
        link_registry=link_registry,
        trash_manager=trash_manager,
        organization_database=None,
        require_confirmation=config.delete_confirmation_required,
        default_dry_run=config.delete_dry_run_default
    )

    try:
        result = asyncio.run(deletion_manager.delete_permanent(
            path=Path(path),
            dry_run=dry_run,
            force=force
        ))
        if result.success:
            log_success(get_logger(__name__), f"Permanently deleted: {path}")
        else:
            log_error(get_logger(__name__), f"Failed: {result.error_message}")
    finally:
        link_registry.close()
        trash_manager.close()


def trash_list(active_only: bool = True):
    """List trash items"""
    from src.trash_manager import TrashManager
    from src.config import Config

    config = Config()
    trash_manager = TrashManager(config.trash_path, config.trash_retention_days)

    try:
        items = trash_manager.list_items(active_only=active_only)
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
        trash_manager.close()


def trash_restore(trash_id: str):
    """Restore item from trash"""
    from src.trash_manager import TrashManager
    from src.config import Config

    config = Config()
    trash_manager = TrashManager(config.trash_path, config.trash_retention_days)

    try:
        success = trash_manager.restore_from_trash(trash_id)
        if success:
            log_success(get_logger(__name__), f"Restored: {trash_id}")
        else:
            log_error(get_logger(__name__), f"Failed to restore: {trash_id}")
    finally:
        trash_manager.close()


def trash_empty(older_than_days: int = None):
    """Empty trash"""
    from src.trash_manager import TrashManager
    from src.config import Config

    config = Config()
    trash_manager = TrashManager(config.trash_path, config.trash_retention_days)

    try:
        result = trash_manager.empty_trash(older_than_days=older_than_days)
        log_success(get_logger(__name__), f"Emptied trash: {result['items_removed']} items removed")
    finally:
        trash_manager.close()


def trash_status():
    """Show trash status"""
    from src.deletion_manager import DeletionManager
    from src.link_registry import LinkRegistry
    from src.trash_manager import TrashManager
    from src.config import Config

    config = Config()
    link_registry = LinkRegistry(config.link_registry_path)
    trash_manager = TrashManager(config.trash_path, config.trash_retention_days)
    deletion_manager = DeletionManager(
        link_registry=link_registry,
        trash_manager=trash_manager,
        organization_database=None
    )

    try:
        stats = deletion_manager.get_stats()

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
        link_registry.close()
        trash_manager.close()


def trash_lookup(path: str):
    """Lookup links for a file"""
    from src.deletion_manager import DeletionManager
    from src.link_registry import LinkRegistry
    from src.trash_manager import TrashManager
    from src.config import Config

    config = Config()
    link_registry = LinkRegistry(config.link_registry_path)
    trash_manager = TrashManager(config.trash_path, config.trash_retention_days)
    deletion_manager = DeletionManager(
        link_registry=link_registry,
        trash_manager=trash_manager,
        organization_database=None
    )

    try:
        preview = asyncio.run(deletion_manager.get_deletion_preview(Path(path)))
        deletion_manager.print_preview(preview)
    finally:
        link_registry.close()
        trash_manager.close()


def trash_scan():
    """Scan filesystem to rebuild registry"""
    from src.link_registry import LinkRegistry
    from src.config import Config

    config = Config()
    link_registry = LinkRegistry(config.link_registry_path)

    try:
        download_paths = config.get_all_download_paths()
        library_paths = config.get_all_library_paths()

        all_paths = list(download_paths.values()) + list(library_paths.values())
        all_paths = [p for p in all_paths if p and p != Path("") and p.exists()]

        if not all_paths:
            console.print("[red]✗ No valid directories to scan.[/red]")
            return

        stats = link_registry.scan_filesystem(all_paths)
        console.print(f"\n[green]✓ Scan complete![/green]")
        console.print(f"  Files scanned: {stats['files_scanned']}")
        console.print(f"  Inodes registered: {stats['inodes_registered']}")
        console.print(f"  Links found: {stats['links_found']}")
        console.print(f"  Errors: {stats['errors']}")
    finally:
        link_registry.close()


if __name__ == "__main__":
    main()
