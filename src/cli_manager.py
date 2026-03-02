#!/usr/bin/env python3
"""
CLI Manager for Media Organization System

Follows the same patterns as control-panel:
- Icons only in menu titles (not in options)
- Bold cyan for option numbers
- Consistent prompt style
- Return to main menu option in all submenus
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
            console.print("[bold]Select an operation:[/bold]\n")

            # Options with submenus first, then other options
            options = {
                "1": "Organize media files",
                "2": "Rename media files",
                "3": "View menu",
                "4": "Trash & Deletion",
                "5": "Subtitle Downloader",
                "6": "Exit"
            }

            for key, value in options.items():
                console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            try:
                choice = Prompt.ask("\n[bold]Your choice[/bold]", choices=list(
                    options.keys()), default="6")

                if choice == '1':
                    self.show_organize_menu()
                elif choice == '2':
                    self.show_renamer_menu()
                elif choice == '3':
                    self.show_view_menu()
                elif choice == '4':
                    self.show_trash_menu()
                elif choice == '5':
                    self.show_subtitle_menu()
                elif choice == '6':
                    console.print("[green]Exiting... Goodbye![/green]")
                    break

                # Pause before showing the menu again
                input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                console.print("\n[red]Operation cancelled by user.[/red]")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    def show_view_menu(self):
        """Show view submenu"""
        while True:
            console.print("\n[bold cyan]📋 View Menu[/bold cyan]")
            console.print("[bold]Select an operation:[/bold]\n")

            options = {
                "1": "View system status",
                "2": "View unorganized files",
                "3": "View organization logs",
                "4": "View statistics",
                "5": "Return to main menu"
            }

            for key, value in options.items():
                console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            try:
                choice = Prompt.ask("\n[bold]Your choice[/bold]", choices=list(
                    options.keys()), default="5")

                if choice == '1':
                    self.show_status_interactive()
                elif choice == '2':
                    self.view_unorganized_interactive()
                elif choice == '3':
                    self.view_logs_interactive()
                elif choice == '4':
                    self.view_stats_interactive()
                elif choice == '5':
                    break

                # Pause before showing the menu again
                input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                console.print("\n[red]Operation cancelled by user.[/red]")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    def show_organize_menu(self):
        """Show organize media submenu"""
        from src.main import MediaOrganizerApp

        while True:
            console.print("\n[bold cyan]📂 Organize Media Files[/bold cyan]")
            console.print("[bold]Select directory to organize:[/bold]\n")

            options = {
                "1": "Movies",
                "2": "TV Shows",
                "3": "Anime",
                "4": "Doramas",
                "5": "Music",
                "6": "Books",
                "7": "Comics",
                "8": "All directories",
                "9": "Return to main menu"
            }

            for key, value in options.items():
                console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            try:
                choice = Prompt.ask("\n[bold]Your choice[/bold]", choices=list(
                    options.keys()), default="9")

                if choice == "9":
                    break

                app = MediaOrganizerApp(dry_run=False)

                if choice == "8":
                    # Organize all directories
                    console.print("\n[cyan]→ Organizing all directories...[/cyan]\n")

                    total_processed = 0
                    dir_options = {
                        "1": ("Movies", self.config.download_path_movies),
                        "2": ("TV Shows", self.config.download_path_tv),
                        "3": ("Anime", self.config.download_path_animes),
                        "4": ("Doramas", self.config.download_path_doramas),
                        "5": ("Music", self.config.download_path_music),
                        "6": ("Books", self.config.download_path_books),
                        "7": ("Comics", self.config.download_path_comics),
                    }

                    for key, (name, path) in dir_options.items():
                        if path and path.exists():
                            resultados = asyncio.run(app.orchestrator.organizar_arquivos(path))
                            processed = len(resultados)
                            total_processed += processed
                            console.print(f"  Processed {processed} files in {name}")

                    console.print(
                        f"\n[bold green]✓ Successfully organized {total_processed} file(s)[/bold green]")
                else:
                    # Organize selected directory
                    dir_map = {
                        "1": ("Movies", self.config.download_path_movies),
                        "2": ("TV Shows", self.config.download_path_tv),
                        "3": ("Anime", self.config.download_path_animes),
                        "4": ("Doramas", self.config.download_path_doramas),
                        "5": ("Music", self.config.download_path_music),
                        "6": ("Books", self.config.download_path_books),
                        "7": ("Comics", self.config.download_path_comics),
                    }

                    name, path = dir_map.get(choice, (None, None))

                    if path:
                        console.print(f"\n[cyan]→ Organizing {name}: {path}[/cyan]\n")

                        if not path.exists():
                            console.print(f"[red]✗ Directory does not exist: {path}[/red]")
                            continue

                        asyncio.run(app.organize_directory(path))
                        app.show_stats()
                    else:
                        console.print(f"[red]✗ Invalid option[/red]")

                app.cleanup()

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    def show_renamer_menu(self):
        """Show renamer submenu"""
        from src.main import MediaOrganizerApp
        from src.config import Config

        config = Config()
        dry_run = False

        while True:
            console.print("\n[bold cyan]📝 Rename Media Files[/bold cyan]")
            console.print("[bold]Select media type:[/bold]\n")

            options = {
                "1": "Movies (Title (Year).ext)",
                "2": "TV Shows (Serie.S01E01.ext)",
                "3": "Anime (Anime.S01E01.ext)",
                "4": "Doramas (Dorama.S01E01.ext)",
                "5": "Music (## - Track.ext)",
                "6": "Books (Author - Title (Year).ext)",
                "7": "Comics (Series #Issue.ext)",
                "8": f"Dry-run: [{'ON' if dry_run else 'OFF'}]",
                "9": "Return to main menu"
            }

            for key, value in options.items():
                if key == "8":
                    status = "ON" if dry_run else "OFF"
                    color = "yellow" if dry_run else "green"
                    console.print(f"  [bold cyan][{key}][/bold cyan]  [{color}]{value}[/{color}]")
                else:
                    console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            try:
                choice = Prompt.ask("\n[bold]Your choice[/bold]", choices=list(
                    options.keys()), default="9")

                if choice == "9":
                    break
                elif choice == "8":
                    dry_run = not dry_run
                    console.print(f"[green]Dry-run turned {'ON' if dry_run else 'OFF'}[/green]")
                    continue

                # Get folder path
                folder_str = input("Enter folder path: ").strip()
                folder = Path(folder_str)

                if not folder.exists():
                    console.print(f"[red]✗ Folder does not exist: {folder}[/red]")
                    continue

                if not folder.is_dir():
                    console.print(f"[red]✗ Path is not a directory: {folder}[/red]")
                    continue

                app = MediaOrganizerApp(dry_run=dry_run)
                stats = {'processed': 0, 'renamed': 0, 'failed': 0, 'skipped': 0}

                # Get metadata based on type
                metadata = None
                if choice == "1":  # Movies
                    title = input("Movie title: ").strip()
                    year = int(input("Year [2024]: ").strip() or "2024")
                    metadata = {'type': 'movie', 'title': title, 'year': year}
                elif choice == "2":  # TV Shows
                    series = input("Series name: ").strip()
                    season = int(input("Season [1]: ").strip() or "1")
                    metadata = {'type': 'tv', 'title': series, 'season': season}
                elif choice == "3":  # Anime
                    anime = input("Anime name: ").strip()
                    season = int(input("Season [1]: ").strip() or "1")
                    metadata = {'type': 'anime', 'title': anime, 'season': season}
                elif choice == "4":  # Doramas
                    dorama = input("Dorama name: ").strip()
                    season = int(input("Season [1]: ").strip() or "1")
                    metadata = {'type': 'dorama', 'title': dorama, 'season': season}
                elif choice == "5":  # Music
                    track_num = int(input("Track number [1]: ").strip() or "1")
                    title = input("Track title: ").strip()
                    metadata = {'type': 'music', 'title': title, 'track': track_num}
                elif choice == "6":  # Books
                    author = input("Author: ").strip()
                    title = input("Title: ").strip()
                    year = int(input("Year [2024]: ").strip() or "2024")
                    metadata = {'type': 'book', 'title': title, 'author': author, 'year': year}
                elif choice == "7":  # Comics
                    series = input("Series name: ").strip()
                    issue = int(input("Issue number [1]: ").strip() or "1")
                    metadata = {'type': 'comic', 'title': series, 'issue': issue}

                if metadata:
                    console.print(f"\n[cyan]→ Renaming {metadata['type']} files in {folder}...[/cyan]\n")
                    stats = app.rename_files_batch(folder, metadata)

                    # Display results
                    console.print("\n[bold cyan]📊 Results:[/bold cyan]")
                    console.print(f"  Processed: [green]{stats['processed']}[/green]")
                    console.print(f"  Renamed:   [green]{stats['renamed']}[/green]")
                    console.print(f"  Skipped:   [yellow]{stats['skipped']}[/yellow]")
                    console.print(f"  Failed:    [red]{stats['failed']}[/red]")

                app.cleanup()

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

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
        console.print("\n[bold cyan]📜 Organization Logs[/bold cyan]")

        try:
            log_file = self.logs_dir / "media_organizer.log"
            if not log_file.exists():
                console.print("[yellow]No log file found.[/yellow]")
                return

            console.print("\nNumber of lines options:")
            console.print("  [1] 10")
            console.print("  [2] 20")
            console.print("  [3] 50")
            console.print("  [4] 100")
            lines_choice = input("Your choice [1-4] (3): ").strip() or "3"
            lines_map = {"1": 10, "2": 20, "3": 50, "4": 100}
            lines = lines_map.get(lines_choice, 50)

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

    def show_trash_menu(self):
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
                    "9": "Return to main menu"
                }

                for key, value in options.items():
                    console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

                choice = Prompt.ask("\n[bold]Your choice[/bold]", choices=list(
                    options.keys()), default="9")

                if choice == "9":
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

                if choice != "9":
                    input("\nPress Enter to continue...")

        finally:
            trash_cli.cleanup()

    def show_subtitle_menu(self):
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
                "9": "Return to main menu"
            }

            for key, value in options.items():
                console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            choice = Prompt.ask("\n[bold]Your choice[/bold]", choices=list(
                options.keys()), default="9")

            if choice == "9":
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

            if choice != "9":
                input("\nPress Enter to continue...")

    def show_menu(self):
        """Show main menu with help information"""
        help_text = Text()
        help_text.append("Available commands:\n", style="bold cyan")
        help_text.append("  organize                          - Organize media files\n")
        help_text.append("  renamer                           - Rename media files\n")
        help_text.append("  scan                              - Scan for new files\n")
        help_text.append("  status                            - Show system status\n")
        help_text.append("  unorganized                       - View unorganized files\n")
        help_text.append("  logs                              - Show organization logs\n")
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
# Helper functions for main.py integration
# ============================================================================

def show_trash_menu():
    """Show trash & deletion manager submenu"""
    cli = CLIManager()
    cli.show_trash_menu()


def show_subtitle_menu():
    """Show subtitle downloader submenu"""
    cli = CLIManager()
    cli.show_subtitle_menu()


def show_renamer_menu():
    """Show renamer submenu"""
    cli = CLIManager()
    cli.show_renamer_menu()
