#!/usr/bin/env python3
"""CLI Manager for Media Organization System."""

import asyncio
import logging
import os
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

from src.config import Config
from src.log_config import get_logger, log_error, set_console_log_level

console = Console()


class CLIManager:
    """Main CLI manager for the active media scope."""

    def __init__(self):
        self.script_dir = Path(os.getenv("SCRIPT_PATH", os.getcwd()))
        self.logs_dir = self.script_dir / "logs"
        self.data_dir = self.script_dir / "data"
        self.logs_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)

        self.logger = get_logger(__name__)
        self.config = Config()

    def show_interactive_menu(self):
        while True:
            console.print("\n[bold cyan]Media Organizer System[/bold cyan]")
            console.print("[bold]Select an operation:[/bold]\n")

            options = {
                "1": "Organize media files",
                "2": "System information",
                "3": "Exit",
            }

            for key, value in options.items():
                console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            choice = Prompt.ask(
                "\n[bold]Your choice[/bold]", choices=list(options.keys()), default="3")

            if choice == "1":
                self.show_organize_menu()
            elif choice == "2":
                self.show_system_info_menu()
            elif choice == "3":
                break

    def show_system_info_menu(self):
        while True:
            console.print("\n[bold cyan]System Information[/bold cyan]")
            console.print("[bold]Select an operation:[/bold]\n")

            options = {
                "1": "View system status",
                "2": "View unorganized files",
                "3": "View organization logs",
                "4": "View statistics",
                "5": "Return to main menu",
            }

            for key, value in options.items():
                console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            choice = Prompt.ask(
                "\n[bold]Your choice[/bold]", choices=list(options.keys()), default="5")

            if choice == "1":
                self.show_status_interactive()
            elif choice == "2":
                self.view_unorganized_interactive()
            elif choice == "3":
                self.view_logs_interactive()
            elif choice == "4":
                self.view_stats_interactive()
            elif choice == "5":
                break

    def show_organize_menu(self):
        from src.main import MediaOrganizerApp

        while True:
            console.print("\n[bold cyan]Organize Media Files[/bold cyan]")
            console.print("[bold]Select directory to organize:[/bold]\n")

            options = {
                "1": "Music",
                "2": "Books",
                "3": "Comics",
                "4": "All directories",
                "5": "Return to main menu",
            }

            for key, value in options.items():
                console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            choice = Prompt.ask(
                "\n[bold]Your choice[/bold]", choices=list(options.keys()), default="5")

            if choice == "5":
                break

            app = MediaOrganizerApp(dry_run=False)
            # Interactive runs should stream progress to terminal.
            set_console_log_level(logging.INFO)
            try:
                if choice == "4":
                    total_processed = 0
                    dir_options = [
                        ("Music", self.config.download_path_music, "tracks"),
                        ("Books", self.config.download_path_books, "books"),
                        ("Comics", self.config.download_path_comics, "comics"),
                    ]

                    for name, path, unit in dir_options:
                        if path and path.exists():
                            processed = asyncio.run(
                                app.organize_directory(
                                    path,
                                    source_label=name,
                                    progress_unit=unit,
                                )
                            )
                            total_processed += processed
                            console.print(
                                f"  Processed {processed} files in {name}")

                    console.print(
                        f"\n[bold green]Successfully organized {total_processed} file(s)[/bold green]")
                else:
                    dir_map = {
                        "1": ("Music", self.config.download_path_music),
                        "2": ("Books", self.config.download_path_books),
                        "3": ("Comics", self.config.download_path_comics),
                    }

                    name, path = dir_map.get(choice, (None, None))
                    if not path:
                        console.print("[red]Invalid option[/red]")
                        continue

                    if not path.exists():
                        console.print(
                            f"[red]Directory does not exist: {path}[/red]")
                        continue

                    console.print(
                        f"\n[cyan]Organizing {name}: {path}[/cyan]\n")
                    unit = "tracks" if name == "Music" else name.lower()
                    asyncio.run(
                        app.organize_directory(
                            path,
                            source_label=name,
                            progress_unit=unit,
                        )
                    )
                    app.show_stats()
            finally:
                app.cleanup()
                # Restore default non-dry-run console verbosity outside execution windows.
                set_console_log_level(logging.WARNING)

    def show_status_interactive(self):
        console.print("\n[bold cyan]System Status[/bold cyan]")

        try:
            import shutil

            total, used, free = shutil.disk_usage("/")
            console.print(f"Total: {total / (1024**3):.2f} GB")
            console.print(f"Used: {used / (1024**3):.2f} GB")
            console.print(f"Free: {free / (1024**3):.2f} GB")
        except Exception as exc:
            log_error(self.logger, f"Error getting system status: {exc}")

    def view_unorganized_interactive(self):
        from src.persistence import UnorganizedDatabase

        console.print("\n[bold cyan]Unorganized Files[/bold cyan]")

        try:
            unorganized_db = UnorganizedDatabase(Path("data/unorganized.json"))
            unorganized_data = unorganized_db.get_unorganized_files()

            if not unorganized_data:
                console.print("[green]No unorganized files found.[/green]")
                return

            console.print(
                f"\n[bold]Unorganized Files ({len(unorganized_data)} files):[/bold]")
            for index, item in enumerate(unorganized_data, 1):
                file_path = item.get("file_path", "Unknown")
                reason = item.get("reason", item.get(
                    "error", "No reason provided"))
                console.print(f"{index:3d}. {file_path}")
                console.print(f"     Reason: {reason}")
        except Exception as exc:
            log_error(self.logger, f"Error viewing unorganized files: {exc}")

    def view_logs_interactive(self):
        console.print("\n[bold cyan]Organization Logs[/bold cyan]")

        log_file = self.logs_dir / "organizer.log"
        if not log_file.exists():
            console.print("[yellow]No log file found.[/yellow]")
            return

        try:
            with open(log_file, "r", encoding="utf-8") as file_handle:
                lines = file_handle.readlines()[-50:]

            for line in lines:
                console.print(line.rstrip())
        except Exception as exc:
            console.print(f"[red]Error reading log file: {exc}[/red]")

    def view_stats_interactive(self):
        from src.main import MediaOrganizerApp

        console.print("\n[bold cyan]System Statistics[/bold cyan]")

        try:
            app = MediaOrganizerApp()
            stats = app.database.get_stats()

            console.print("\n[bold]Organization Stats:[/bold]")
            for key, value in stats.items():
                console.print(f"  {key}: {value}")

            app.cleanup()
        except Exception as exc:
            log_error(self.logger, f"Error viewing stats: {exc}")
