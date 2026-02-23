"""
Media Organization System - Main Entry Point
CLI interface for organizing media files

Consolidated version - uses simplified module structure.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import List, Optional

import click
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.console import Console

from src.config import Config
from src.log_config import get_logger, set_console_log_level, log_info, log_success, log_error, log_warning
from src.core import (
    Orquestrador, MediaType,
    FileExistenceValidator, FileTypeValidator,
    IncompleteFileValidator, JunkFileValidator
)
from src.detection import MediaClassifier, FileScanner
from src.persistence import OrganizationDatabase, UnorganizedDatabase
from src.organizers import (
    MovieOrganizer, TVOrganizer, MusicOrganizer, BookOrganizer,
    BaseOrganizer
)
from src.utils import ConflictHandler
from src.integrations import FileCompletionValidator


class MediaOrganizerApp:
    """Main application class"""

    def __init__(self, dry_run: bool = False):
        """Initialize application"""
        self.config = Config()
        self.dry_run = dry_run

        # Initialize logger
        self.logger = get_logger(name="MediaOrganizer", dry_run=dry_run)
        
        # Set console log level based on dry_run mode
        if dry_run:
            set_console_log_level(logging.INFO)
        else:
            set_console_log_level(logging.WARNING)

        # Check configuration validity
        is_valid, errors = self.config.is_valid()
        if not is_valid:
            log_error(self.logger, "Configuration is invalid:")
            for error in errors:
                log_error(self.logger, f"  - {error}")
            import sys
            sys.exit(1)

        # Initialize database
        self.database = OrganizationDatabase(
            db_path=self.config.database_path,
            backup_enabled=self.config.database_backup_enabled,
            backup_keep_days=self.config.database_backup_keep_days
        )

        # Initialize conflict handler
        self.conflict_handler = ConflictHandler(
            strategy=self.config.conflict_strategy,
            rename_pattern=self.config.conflict_rename_pattern,
            max_attempts=self.config.conflict_max_attempts
        )

        # Initialize validators
        self.validators = [
            FileExistenceValidator(logger=self.logger),
            FileTypeValidator(
                supported_types=[
                    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
                    '.mp3', '.flac', '.ogg', '.m4a', '.wma', '.aac', '.opus', '.wav', '.m4b',
                    '.epub', '.pdf', '.mobi', '.azw', '.azw3',
                    '.cbz', '.cbr', '.cb7', '.cbt'
                ],
                logger=self.logger
            ),
            IncompleteFileValidator(logger=self.logger),
            JunkFileValidator(logger=self.logger),
        ]

        # Initialize classifier and scanner
        self.classifier = MediaClassifier(logger=self.logger)
        self.scanner = FileScanner(logger=self.logger)

        # Initialize file completion validator
        self.file_completion_validator = FileCompletionValidator(
            min_file_age_seconds=300,
            size_check_duration=5,
            logger=self.logger
        )

        # Initialize organizers
        self.organizadores = {
            MediaType.MOVIE: MovieOrganizer(
                config=self.config,
                database=self.database,
                conflict_handler=self.conflict_handler,
                logger=self.logger,
                dry_run=self.dry_run
            ),
            MediaType.TV_SHOW: TVOrganizer(
                config=self.config,
                database=self.database,
                conflict_handler=self.conflict_handler,
                logger=self.logger,
                dry_run=self.dry_run,
                media_subtype='tv'
            ),
            MediaType.ANIME: TVOrganizer(
                config=self.config,
                database=self.database,
                conflict_handler=self.conflict_handler,
                logger=self.logger,
                dry_run=self.dry_run,
                media_subtype='anime'
            ),
            MediaType.DORAMA: TVOrganizer(
                config=self.config,
                database=self.database,
                conflict_handler=self.conflict_handler,
                logger=self.logger,
                dry_run=self.dry_run,
                media_subtype='dorama'
            ),
            MediaType.MUSIC: MusicOrganizer(
                config=self.config,
                database=self.database,
                conflict_handler=self.conflict_handler,
                logger=self.logger,
                dry_run=self.dry_run
            ),
            MediaType.BOOK: BookOrganizer(
                config=self.config,
                database=self.database,
                conflict_handler=self.conflict_handler,
                logger=self.logger,
                dry_run=self.dry_run,
                book_type='book'
            ),
            MediaType.COMIC: BookOrganizer(
                config=self.config,
                database=self.database,
                conflict_handler=self.conflict_handler,
                logger=self.logger,
                dry_run=self.dry_run,
                book_type='comic'
            ),
        }

        # Initialize orchestrator
        self.orchestrator = Orquestrador(
            validators=self.validators,
            organizadores=self.organizadores,
            classifier=self.classifier,
            scanner=self.scanner,
            database=self.database,
            file_completion_validator=self.file_completion_validator,
            logger=self.logger
        )

        if dry_run:
            self.logger.info(
                "⚠ Running in DRY-RUN mode (no files will be modified)")

    async def organize_directory(self, directory: Path):
        """Organize all files in a directory"""
        if not directory.exists() or not directory.is_dir():
            self.logger.error(f"Directory not found: {directory}")
            return

        processed_count = await self.orchestrator.organizar_arquivos(
            diretorio_origem=directory,
            validar_completude_arquivo=True
        )
        self.logger.info(f"Processed {len(processed_count)} files in {directory}")
        return len(processed_count)

    def show_stats(self):
        """Show organization statistics"""
        stats = self.orchestrator.get_stats()

        # First table: Organization Statistics
        table1 = Table(title="📊 Organization Statistics")
        table1.add_column("Metric", style="cyan")
        table1.add_column("Value", style="green")

        table1.add_row("Total Files Organized", str(
            stats.get('total_files_organized', 0)))
        table1.add_row("Movies", str(stats.get('movies', 0)))
        table1.add_row("Series", str(stats.get('series', 0)))
        table1.add_row("Anime", str(stats.get('animes', 0)))
        table1.add_row("Doramas", str(stats.get('doramas', 0)))
        table1.add_row("Music Tracks", str(stats.get('music_tracks', 0)))
        table1.add_row("Books", str(stats.get('books', 0)))
        table1.add_row("Comics", str(stats.get('comics', 0)))
        table1.add_row("Failed Operations", str(
            stats.get('failed_operations', 0)))

        console = Console()
        console.print(table1)


    def _get_mapping_stats(self):
        """Get statistics - manual mapping is no longer used"""
        # Since we removed manual mapping, return empty stats
        return {
            'movies': 0,
            'tv_series': 0,
            'anime': 0,
            'dorama': 0,
            'total': 0
        }

    def cleanup(self):
        """Cleanup and save state"""
        # Close orchestrator resources
        if hasattr(self.orchestrator, 'cleanup'):
            self.orchestrator.cleanup()
        
        # Close database
        if hasattr(self, 'database'):
            self.database.close()


@click.group()
@click.option('--dry-run', is_flag=True, help='Simulate operations without modifying files')
@click.pass_context
def cli(ctx, dry_run):
    """Media Organization System - Organize your media files automatically"""
    ctx.ensure_object(dict)
    ctx.obj['DRY_RUN'] = dry_run


@cli.command()
@click.pass_context
def organize(ctx):
    """Organize media files - Interactive menu to select directory"""
    dry_run = ctx.obj.get('DRY_RUN', False)
    app = MediaOrganizerApp(dry_run=dry_run)

    try:
        console = Console()
        console.print("\n[bold cyan]Media Organization[/bold cyan]\n")

        # Create menu options
        options = {
            "1": ("Movies", app.config.download_path_movies),
            "2": ("TV Shows", app.config.download_path_tv),
            "3": ("Anime", app.config.download_path_animes),
            "4": ("Doramas", app.config.download_path_doramas),
            "5": ("Music", app.config.download_path_music),
            "6": ("Books", app.config.download_path_books),
            "7": ("Comics", app.config.download_path_comics),
            "0": ("All directories", None),
        }

        # Display menu
        console.print("[bold]Select directory to organize:[/bold]")
        for key, (name, path) in options.items():
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
                if name != "0":  # Skip the "all" option
                    _, path = path_info
                    if path and path.exists():
                        processed = asyncio.run(app.orchestrator.organizar_diretorio(path))
                        total_processed += processed
                        console.print(f"  Processed {processed} files in {name}")

            console.print(
                f"\n[bold green]✓ Successfully organized {total_processed} file(s)[/bold green]")
        elif choice == "1":
            # Submenu for selecting specific download paths
            console.print("\n[bold cyan]Select Media Type to Organize[/bold cyan]\n")
            
            # Create submenu options for all configured download paths
            submenu_options = {
                "1": ("Movies", app.config.download_path_movies),
                "2": ("TV Shows", app.config.download_path_tv),
                "3": ("Anime", app.config.download_path_animes),
                "4": ("Doramas", app.config.download_path_doramas),
                "5": ("Music", app.config.download_path_music),
                "6": ("Books", app.config.download_path_books),
                "7": ("Comics", app.config.download_path_comics),
                "0": ("Back to main menu", None),
            }
            
            # Display submenu
            console.print("[bold]Select media type to organize:[/bold]")
            for key, (name, path) in submenu_options.items():
                if path:
                    exists = "✓" if path.exists() else "✗"
                    console.print(f"  [{key}] {name} {exists}")
                else:
                    console.print(f"  [{key}] {name}")
            
            submenu_choice = Prompt.ask("\nYour choice", choices=list(
                submenu_options.keys()), default="0")
            
            if submenu_choice != "0":
                name, path = submenu_options[submenu_choice]
                console.print(f"\n[cyan]→ Organizing {name}: {path}[/cyan]\n")
                
                if path and path.exists():
                    asyncio.run(app.organize_directory(path))
                else:
                    console.print(f"[red]✗ Directory does not exist: {path}[/red]")
                    return
            else:
                # Back to main menu
                console.print("\n[blue]Returning to main menu...[/blue]")
                return
        else:
            # Organize selected directory
            name, path = options[choice]
            console.print(f"\n[cyan]→ Organizing {name}: {path}[/cyan]\n")

            if not path.exists():
                console.print(f"[red]✗ Directory does not exist: {path}[/red]")
                return

            asyncio.run(app.organize_directory(path))
        
        app.show_stats()

    finally:
        app.cleanup()


@cli.command()
def unorganized():
    """Show list of unorganized files"""
    console = Console()
    
    # Load unorganized files
    unorganized_path = Path("data/unorganized.json")
    if not unorganized_path.exists():
        console.print("[yellow]No unorganized files found.[/yellow]")
        return
    
    try:
        with open(unorganized_path, 'r', encoding='utf-8') as f:
            unorganized_data = json.load(f)
        
        unorganized_files = unorganized_data.get('unorganized_files', [])
        
        if not unorganized_files:
            console.print("[green]No unorganized files found.[/green]")
            return
        
        console.print(f"\n[bold cyan]Unorganized Files ({len(unorganized_files)} files)[/bold cyan]\n")
        
        for i, item in enumerate(unorganized_files, 1):
            file_path = item.get('file_path', 'Unknown')
            reason = item.get('reason', 'No reason provided')
            console.print(f"{i:3d}. {file_path}")
            console.print(f"     Reason: {reason}")
            console.print()
    
    except Exception as e:
        console.print(f"[red]Error reading unorganized files: {e}[/red]")


@cli.command()
def stats():
    """Show organization statistics"""
    app = MediaOrganizerApp()

    app.show_stats()
    app.cleanup()


@cli.command()
def test():
    """Test configuration and connectivity"""
    console = Console()
    console.print(
        "\n[bold cyan]Testing Media Organization System[/bold cyan]\n")

    app = MediaOrganizerApp()

    # Test configuration
    console.print("✓ Configuration loaded", style="green")

    # Test database
    try:
        stats = app.orchestrator.get_stats()
        console.print(
            f"✓ Database accessible ({stats.get('total_files_organized', 0)} files tracked)", style="green")
    except Exception as e:
        console.print(f"✗ Database error: {e}", style="red")

    console.print("\n[bold green]System is ready![/bold green]\n")
    app.cleanup()


@cli.command()
@click.pass_context
def process_new_media(ctx):
    """
    Process new media from downloads and qBittorrent (for scheduled execution)
    """
    console = Console()
    console.print("\n[bold cyan]Processing New Media[/bold cyan]\n")

    dry_run = ctx.obj.get('DRY_RUN', False)
    app = MediaOrganizerApp(dry_run=dry_run)

    try:
        # Process all download folders with qBittorrent validation
        total_processed = 0

        # Process all configured download paths
        download_paths = [
            app.config.download_path_movies,
            app.config.download_path_tv,
            app.config.download_path_animes,
            app.config.download_path_doramas,
            app.config.download_path_music,
            app.config.download_path_books,
            app.config.download_path_comics,
        ]

        for path in download_paths:
            if path and path.exists():
                processed = asyncio.run(app.orchestrator.organizar_diretorio(path))
                total_processed += processed

        if total_processed > 0:
            console.print(
                f"\n[bold green]✓ Successfully organized {total_processed} file(s)[/bold green]")
        else:
            console.print("\n[yellow]No new media files to organize[/yellow]")

    finally:
        app.cleanup()


@cli.command()
@click.pass_context
def daemon(ctx):
    """
    Run media organizer in daemon mode (continuous execution with interval)

    Executes process-new-media repeatedly with configured CHECK_INTERVAL.
    Use run-daemon.sh to start in background with nohup.
    """
    import time
    from datetime import datetime

    app = MediaOrganizerApp()
    check_interval = app.config.check_interval

    console = Console()
    console.print("\n[bold cyan]Media Organizer - Daemon Mode[/bold cyan]\n")
    console.print(
        f"Check interval: {check_interval} seconds ({check_interval // 60} minutes)")
    console.print("Press Ctrl+C to stop\n")

    cycle_count = 0

    try:
        while True:
            cycle_count += 1
            start_time = datetime.now()

            console.print(
                f"\n[bold cyan]═══ Cycle {cycle_count} - {start_time.strftime('%d/%m/%Y %H:%M:%S')} ═══[/bold cyan]\n")

            try:
                # Process all download folders with qBittorrent validation
                total_processed = 0

                # Process all configured download paths
                download_paths = [
                    app.config.download_path_movies,
                    app.config.download_path_tv,
                    app.config.download_path_animes,
                    app.config.download_path_doramas,
                    app.config.download_path_music,
                    app.config.download_path_books,
                    app.config.download_path_comics,
                ]

                for path in download_paths:
                    if path and path.exists():
                        processed = asyncio.run(app.orchestrator.organizar_diretorio(path))
                        total_processed += processed

                if total_processed > 0:
                    console.print(
                        f"\n[green]✓ Organized {total_processed} file(s) this cycle[/green]")
                else:
                    console.print("\n[dim]No new media found[/dim]")

                # Calculate cycle duration
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                console.print(
                    f"\n[dim]Cycle completed in {duration:.1f}s[/dim]")

                # Wait for next check
                console.print(
                    f"[dim]Waiting {check_interval // 60} minutes until next check...[/dim]")
                time.sleep(check_interval)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                app.logger.error(f"Error in daemon cycle: {e}")
                console.print(f"\n[red]✗ Cycle error: {e}[/red]")
                console.print(
                    f"[dim]Waiting {check_interval // 60} minutes before retry...[/dim]")
                time.sleep(check_interval)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠ Daemon stopped by user[/yellow]")
    finally:
        app.cleanup()


if __name__ == "__main__":
    cli()