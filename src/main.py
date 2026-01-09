#!/usr/bin/env python3
"""
Media Organization System - Main Entry Point
CLI interface for organizing media files
"""

from src.organizers.book import BookOrganizer
from src.organizers.music import MusicOrganizer
from src.organizers.tv import TVOrganizer
from src.organizers.movie import MovieOrganizer
from src.metadata.parsers import detect_media_type
from src.metadata.tmdb_client import TMDBClient
from src.utils.validators import validate_video_file, validate_audio_file, validate_book_file
from src.utils.logger import get_logger
from src.utils.conflict_handler import ConflictHandler
from src.rate_limiter import RateLimiter
from src.database import OrganizationDatabase
from src.config import Config
from src.monitors.torrent_monitor import TorrentProcessor
from typing import List, Optional
import sys
import asyncio
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


console = Console()


class MediaOrganizerApp:
    """Main application class"""

    def __init__(self, dry_run: bool = False):
        """Initialize application"""
        self.config = Config()
        self.dry_run = dry_run

        # Initialize logger
        self.logger = get_logger(
            config=self.config,
            dry_run=dry_run
        )

        # Check configuration validity
        is_valid, errors = self.config.is_valid()
        if not is_valid:
            self.logger.error("Configuration is invalid:")
            for error in errors:
                self.logger.error(f"  - {error}")
            sys.exit(1)

        # Initialize database
        self.database = OrganizationDatabase(
            db_path=self.config.database_path,
            backup_enabled=self.config.database_backup_enabled,
            backup_keep_days=self.config.database_backup_keep_days
        )

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            max_concurrent_file_ops=self.config.max_concurrent_file_ops,
            max_concurrent_api_calls=self.config.max_concurrent_api_calls,
            tmdb_rate_limit=self.config.tmdb_rate_limit_per_second,
            file_op_delay_ms=self.config.file_op_delay_ms
        )

        # Initialize conflict handler
        self.conflict_handler = ConflictHandler(
            strategy=self.config.conflict_strategy,
            rename_pattern=self.config.conflict_rename_pattern,
            max_attempts=self.config.conflict_max_attempts
        )

        # Initialize TMDB client (optional)
        self.tmdb_client = None
        if self.config.tmdb_api_key and self.config.tmdb_api_key != "your_api_key_here":
            self.tmdb_client = TMDBClient(
                api_key=self.config.tmdb_api_key,
                use_fallback=self.config.tmdb_use_fallback_parsing
            )

            # Load cache
            cache_file = self.config.database_path.parent / "tmdb_cache.json"
            self.tmdb_client.load_cache(cache_file)

        # Initialize organizers
        self._init_organizers()

        self.logger.info("✓ Media Organization System initialized")
        if dry_run:
            self.logger.info(
                "⚠ Running in DRY-RUN mode (no files will be modified)")

    def _init_organizers(self):
        """Initialize all organizers"""
        organizer_args = {
            'config': self.config,
            'database': self.database,
            'rate_limiter': self.rate_limiter,
            'conflict_handler': self.conflict_handler,
            'logger': self.logger,
            'dry_run': self.dry_run
        }

        self.movie_organizer = MovieOrganizer(
            **organizer_args,
            tmdb_client=self.tmdb_client
        )

        self.tv_organizer = TVOrganizer(
            **organizer_args,
            tmdb_client=self.tmdb_client,
            media_subtype='series'
        )

        self.anime_organizer = TVOrganizer(
            **organizer_args,
            tmdb_client=self.tmdb_client,
            media_subtype='anime'
        )

        self.dorama_organizer = TVOrganizer(
            **organizer_args,
            tmdb_client=self.tmdb_client,
            media_subtype='dorama'
        )

        self.music_organizer = MusicOrganizer(**organizer_args)

        self.book_organizer = BookOrganizer(**organizer_args, book_type='book')

        # Initialize optional modules
        self.torrent_processor: Optional[TorrentProcessor] = None

    async def organize_file(self, file_path: Path):
        """Organize a single file"""
        # Detect media type
        media_type = detect_media_type(file_path)

        self.logger.info(
            f"Processing: {file_path.name} (detected: {media_type})")

        # Select appropriate organizer
        if media_type == 'movie':
            result = await self.movie_organizer.organize(file_path)
        elif media_type == 'tv':
            result = await self.tv_organizer.organize(file_path)
        elif media_type == 'anime':
            result = await self.anime_organizer.organize(file_path)
        elif media_type == 'dorama':
            result = await self.dorama_organizer.organize(file_path)
        elif media_type == 'music':
            result = await self.music_organizer.organize(file_path)
        elif media_type in ['book', 'comic', 'audiobook']:
            result = await self.book_organizer.organize(file_path)
        else:
            self.logger.warning(
                f"Unknown media type, skipping: {file_path.name}")
            return

        # Log result
        if result.success:
            self.logger.success(f"✓ Organized: {file_path.name}")
        elif result.skipped:
            self.logger.info(
                f"↷ Skipped - Already organized: {file_path.name}")
        else:
            self.logger.error(
                f"✗ Failed: {file_path.name} ({result.error_message})")

    async def organize_directory(self, directory: Path):
        """Organize all files in a directory"""
        if not directory.exists() or not directory.is_dir():
            self.logger.error(f"Directory not found: {directory}")
            return

        # Find all media files
        media_files = []
        extensions = [
            # Video
            '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm',
            # Audio
            '.mp3', '.flac', '.m4a', '.ogg', '.opus', '.aac', '.wav',
            # Books
            '.epub', '.pdf', '.mobi', '.azw3',
            # Comics
            '.cbz', '.cbr', '.cb7', '.cbt'
        ]
        for ext in extensions:
            media_files.extend(directory.rglob(f'*{ext}'))

        self.logger.info(f"Found {len(media_files)} media files to process")

        # Process files
        for file_path in media_files:
            await self.organize_file(file_path)

    def show_stats(self):
        """Show organization statistics"""
        stats = self.database.get_stats()

        table = Table(title="Organization Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Files Organized", str(
            stats.get('total_files_organized', 0)))
        table.add_row("Movies", str(stats.get('movies_organized', 0)))
        table.add_row("Series", str(stats.get('series_organized', 0)))
        table.add_row("Anime", str(stats.get('animes_organized', 0)))
        table.add_row("Doramas", str(stats.get('doramas_organized', 0)))
        table.add_row("Music Tracks", str(stats.get('music_organized', 0)))
        table.add_row("Books", str(stats.get('books_organized', 0)))
        table.add_row("Failed Operations", str(
            stats.get('failed_operations', 0)))

        console.print(table)

    def cleanup(self):
        """Cleanup and save state"""
        # Save TMDB cache
        if self.tmdb_client:
            cache_file = self.config.database_path.parent / "tmdb_cache.json"
            self.tmdb_client.save_cache(cache_file)

        # Close database
        self.database.close()

    def _is_file_stable(self, file_path: Path, wait_seconds: int = 5) -> bool:
        """
        Check if file size is stable (not changing).
        Used to detect if a file is still being downloaded.

        Args:
            file_path: Path to file to check
            wait_seconds: Seconds to wait between checks (default: 5)

        Returns:
            True if file size is stable, False if still changing
        """
        import time

        try:
            # Skip check for very small files (likely complete)
            initial_size = file_path.stat().st_size
            if initial_size < 1024 * 1024:  # < 1MB
                return True

            # Wait and check again
            time.sleep(wait_seconds)

            if not file_path.exists():
                return False

            final_size = file_path.stat().st_size

            # File is stable if size hasn't changed
            return initial_size == final_size

        except Exception:
            # If any error, consider unstable
            return False

    def process_new_media(self) -> int:
        """Process new media files from download folders"""
        self.logger.info("Scanning download folders for new media...")

        # Initialize qBittorrent processor if enabled
        qbit_processor = None
        completed_torrent_files = set()

        if self.config.qbittorrent_enabled:
            try:
                self.logger.info("Checking qBittorrent...")
                qbit_processor = TorrentProcessor(
                    host=self.config.qbittorrent_host,
                    username=self.config.qbittorrent_username,
                    password=self.config.qbittorrent_password,
                    min_progress=self.config.qbittorrent_min_progress,
                    path_mapping=self.config.qbittorrent_path_mapping,
                    ignored_categories=self.config.qbittorrent_ignored_categories
                )

                # Get completed torrent files for validation
                completed_torrents = qbit_processor.get_completed_torrents()
                for torrent in completed_torrents:
                    completed_torrent_files.update(torrent.files)

                self.logger.info(
                    f"Found {len(completed_torrents)} completed torrents in qBittorrent")
            except Exception as e:
                self.logger.warning(
                    f"qBittorrent unavailable, will process all files: {e}")

        # Scan download folders independently
        media_files = self.scan_download_folders()
        self.logger.info(
            f"Found {len(media_files)} media files in download folders")

        # Process each file
        total_processed = 0
        for file_path in media_files:
            try:
                # Check if already organized
                if self.database.is_file_organized(str(file_path)):
                    self.logger.debug(
                        f"Skipping already organized: {file_path.name}")
                    continue

                # For books: check if there's a better format available
                media_type = detect_media_type(file_path)
                if media_type == 'book':
                    better_format = self._find_better_book_format(file_path)
                    if better_format:
                        self.logger.info(
                            f"Found better format ({better_format.suffix.upper()}) for {file_path.name}, "
                            f"skipping {file_path.suffix.upper()}"
                        )
                        continue

                # Check if file is ready to process
                is_ready = False
                skip_reason = None

                if qbit_processor and completed_torrent_files:
                    # Check if this file is from a completed torrent
                    if file_path in completed_torrent_files:
                        # File is from a completed torrent, ready to process
                        is_ready = True
                        self.logger.debug(
                            f"File from completed torrent: {file_path.name}")
                    else:
                        # Not in qBittorrent completed torrents
                        # Check if file is stable (not being downloaded manually)
                        if self._is_file_stable(file_path):
                            is_ready = True
                            self.logger.debug(
                                f"Manual download, file is stable: {file_path.name}")
                        else:
                            skip_reason = "File size is changing (download in progress)"
                else:
                    # qBittorrent not enabled or no torrents found
                    # Check file stability
                    if self._is_file_stable(file_path):
                        is_ready = True
                    else:
                        skip_reason = "File size is changing (download in progress)"

                # Process file if ready
                if is_ready:
                    asyncio.run(self.organize_file(file_path))
                    total_processed += 1
                elif skip_reason:
                    self.logger.debug(
                        f"↷ Skipped - {skip_reason}: {file_path.name}")

            except Exception as e:
                self.logger.error(f"Error processing {file_path.name}: {e}")

        return total_processed

    def is_incomplete_file(self, file_path: Path) -> bool:
        """Check if file is incomplete (still downloading)"""
        # Check for incomplete file extensions
        incomplete_extensions = {'.part', '.tmp',
                                 '.!qB', '.crdownload', '.download'}
        if file_path.suffix.lower() in incomplete_extensions:
            return True

        # Check for zero-size files
        try:
            if file_path.stat().st_size == 0:
                return True
        except:
            return True

        return False

    def is_junk_file(self, file_path: Path) -> bool:
        """Check if file is junk/promotional content to ignore"""
        filename = file_path.name.upper()

        # Exact name matches (case-insensitive)
        junk_names = {
            'BLUDV.MP4', 'BLUDV.TV.MP4', 'BLUDV.COM.MP4',
            '1XBET.MP4', '1XBET.COM.MP4',
            'SAMPLE.MP4', 'SAMPLE.MKV', 'SAMPLE.AVI',
            'TRAILER.MP4', 'TRAILER.MKV'
        }

        if filename in junk_names:
            return True

        # Pattern matches for promotional content
        junk_patterns = [
            'BLUDV', '1XBET', 'SAMPLE',
            'WWW.', '.COM_PROMO', '_PROMO_',
            'DINHEIRO_LIVRE', 'ACESSE'
        ]

        # Check if filename contains promotional patterns
        for pattern in junk_patterns:
            if pattern in filename:
                # Additional check: if file is small (< 100MB), likely promotional
                try:
                    if file_path.stat().st_size < 100 * 1024 * 1024:  # 100MB
                        return True
                except:
                    pass

        return False

    def _find_better_book_format(self, file_path: Path) -> Optional[Path]:
        """
        Check if there's a better ebook format available in the same folder

        Priority order (best to worst):
        1. EPUB - Best for e-readers, reflowable text
        2. MOBI/AZW3 - Good but Amazon proprietary  
        3. PDF - Last, not reflowable

        Args:
            file_path: Current file being processed

        Returns:
            Path to better format if found, None otherwise
        """
        # Define format priority (lower number = better)
        FORMAT_PRIORITY = {
            '.epub': 1,
            '.mobi': 2,
            '.azw3': 2,
            '.azw': 2,
            '.pdf': 3
        }

        current_ext = file_path.suffix.lower()

        # If current format is not in priority list, don't skip
        if current_ext not in FORMAT_PRIORITY:
            return None

        current_priority = FORMAT_PRIORITY[current_ext]

        # Get base name without number prefix
        import re
        base_name = file_path.stem
        base_name = re.sub(r'^\d+\s*-\s*', '', base_name)

        # Check for better formats in the same folder
        for sibling in file_path.parent.iterdir():
            if sibling == file_path or not sibling.is_file():
                continue

            sibling_ext = sibling.suffix.lower()
            if sibling_ext not in FORMAT_PRIORITY:
                continue

            # Check if it's the same book (same base name)
            sibling_base = sibling.stem
            sibling_base = re.sub(r'^\d+\s*-\s*', '', sibling_base)

            if sibling_base == base_name:
                sibling_priority = FORMAT_PRIORITY[sibling_ext]

                # If sibling has better priority (lower number), return it
                if sibling_priority < current_priority:
                    return sibling

        return None

    def scan_download_folders(self) -> List[Path]:
        """Scan all download folders for media files, ordered by priority"""
        media_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',  # Video
            '.mp3', '.flac', '.ogg', '.m4a', '.wma', '.aac', '.opus', '.wav',  # Audio
            '.epub', '.pdf', '.mobi', '.azw3',  # Books
            '.cbz', '.cbr', '.cb7', '.cbt'  # Comics
        }

        # Define folders with their priorities
        folders_with_priority = [
            (self.config.download_path_movies,
             self.config.processing_priority_movies),
            (self.config.download_path_tv, self.config.processing_priority_tv),
            (self.config.download_path_animes,
             self.config.processing_priority_animes),
            (self.config.download_path_doramas,
             self.config.processing_priority_doramas),
            (self.config.download_path_music,
             self.config.processing_priority_music),
            (self.config.download_path_books,
             self.config.processing_priority_books),
            (self.config.download_path_audiobooks,
             self.config.processing_priority_books),  # Same as books
            (self.config.download_path_comics,
             self.config.processing_priority_books),  # Same as books
        ]

        # Sort by priority (lower number = higher priority)
        folders_with_priority.sort(key=lambda x: x[1])

        # Scan folders in priority order
        media_files = []
        for folder, priority in folders_with_priority:
            if not folder or not folder.exists():
                continue

            for ext in media_extensions:
                for file_path in folder.rglob(f'*{ext}'):
                    # Skip incomplete files
                    if self.is_incomplete_file(file_path):
                        continue

                    # Skip hidden files
                    if file_path.name.startswith('.'):
                        continue

                    # Skip junk/promotional files
                    if self.is_junk_file(file_path):
                        self.logger.debug(
                            f"Skipping junk file: {file_path.name}")
                        continue

                    media_files.append(file_path)

        return media_files

    def find_media_files(self, folder: Path) -> list:
        """Find media files in folder"""
        media_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',  # Video
            '.mp3', '.flac', '.ogg', '.m4a', '.wma', '.aac',  # Audio
            '.epub', '.pdf', '.mobi', '.azw3', '.cbz', '.cbr'  # Books/Comics
        }

        media_files = []
        for ext in media_extensions:
            media_files.extend(folder.rglob(f'*{ext}'))

        return media_files


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
    from rich.prompt import Prompt

    dry_run = ctx.obj.get('DRY_RUN', False)
    app = MediaOrganizerApp(dry_run=dry_run)

    try:
        console.print("\n[bold cyan]Media Organization[/bold cyan]\n")

        # Create menu options
        options = {
            "1": ("Movies", app.config.download_path_movies),
            "2": ("TV Shows", app.config.download_path_tv),
            "3": ("Anime", app.config.download_path_animes),
            "4": ("Doramas", app.config.download_path_doramas),
            "5": ("Music", app.config.download_path_music),
            "6": ("Books", app.config.download_path_books),
            "7": ("Audiobooks", app.config.download_path_audiobooks),
            "8": ("Comics", app.config.download_path_comics),
            "0": ("All directories", None),
        }

        # Display menu
        console.print("[bold]Select directory to organize:[/bold]")
        for key, (name, path) in options.items():
            if key == "0":
                console.print(f"  [{key}] {name}")
            else:
                exists = "✓" if path and path.exists() else "✗"
                console.print(f"  [{key}] {name} {exists}")

        # Get user choice
        choice = Prompt.ask("\nYour choice", choices=list(
            options.keys()), default="0")

        if choice == "0":
            # Organize all directories
            console.print("\n[cyan]→ Organizing all directories...[/cyan]\n")
            total_organized = app.process_new_media()
            console.print(
                f"\n[bold green]✓ Successfully organized {total_organized} file(s)[/bold green]")
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
def stats():
    """Show organization statistics"""
    app = MediaOrganizerApp()
    app.show_stats()
    app.cleanup()


@cli.command()
def test():
    """Test configuration and connectivity"""
    console.print(
        "\n[bold cyan]Testing Media Organization System[/bold cyan]\n")

    app = MediaOrganizerApp()

    # Test configuration
    console.print("✓ Configuration loaded", style="green")

    # Test database
    try:
        stats = app.database.get_stats()
        console.print(
            f"✓ Database accessible ({stats.get('total_files_organized', 0)} files tracked)", style="green")
    except Exception as e:
        console.print(f"✗ Database error: {e}", style="red")

    # Test TMDB
    if app.tmdb_client:
        try:
            test_id = app.tmdb_client.search_movie("Inception", 2010)
            if test_id:
                console.print(
                    f"✓ TMDB API working (test query returned ID: {test_id})", style="green")
            else:
                console.print(
                    "⚠ TMDB API connected but no results", style="yellow")
        except Exception as e:
            console.print(f"✗ TMDB API error: {e}", style="red")
    else:
        console.print("⚠ TMDB API not configured", style="yellow")

    console.print("\n[bold green]System is ready![/bold green]\n")
    app.cleanup()


@cli.command()
@click.pass_context
def process_new_media(ctx):
    """Process new media from downloads and qBittorrent (for scheduled execution)"""
    console.print("\n[bold cyan]Processing New Media[/bold cyan]\n")

    dry_run = ctx.obj.get('DRY_RUN', False)
    app = MediaOrganizerApp(dry_run=dry_run)

    try:
        # Use new architecture: scan folders and validate with qBittorrent
        total_organized = app.process_new_media()

        if total_organized > 0:
            console.print(
                f"\n[bold green]✓ Successfully organized {total_organized} file(s)[/bold green]")
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
                total_organized = app.process_new_media()

                if total_organized > 0:
                    console.print(
                        f"\n[green]✓ Organized {total_organized} file(s) this cycle[/green]")
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


if __name__ == '__main__':
    cli()
