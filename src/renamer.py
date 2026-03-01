#!/usr/bin/env python3
"""
Renamer - Media File Renamer for Media Organizer System

Standalone CLI application for renaming media files to standardized patterns.
Integrates natively with Media Organizer System.

Supported patterns:
- Movies: Title (Year).ext
- TV Shows: Series.S01E01.ext
- Anime: Anime.S01E01.ext
- Doramas: Drama.S01E01.ext
- Music: ## - Track.ext
- Books: Author - Title (Year).ext
- Comics: Series #Issue.ext
- Subtitles: Series.S01E01.lang.ext

Usage:
    python -m src.renamer              # Interactive mode
    python -m src.renamer --dry-run    # Preview changes
    ./run.sh renamer                   # Via run.sh
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Optional

from rich.console import Console
from rich.prompt import Prompt, Confirm

from src.config import Config
from src.main import MediaOrganizerApp
from src.log_config import get_logger


console = Console()


class RenamerCLI:
    """
    Command-line interface for Renamer.
    
    Provides interactive menu for renaming media files
    using the integrated RenamerOrganizer.
    """
    
    def __init__(self, dry_run: bool = False):
        """Initialize RenamerCLI"""
        self.dry_run = dry_run
        self.config = Config()
        self.logger = get_logger("RenamerCLI")
        self.app: Optional[MediaOrganizerApp] = None
    
    def run(self):
        """Main entry point - run interactive menu"""
        console.print("\n[bold cyan]📝 Renamer - Media File Renamer[/bold cyan]")
        console.print("[dim]Integrated with Media Organizer System[/dim]\n")
        
        self._show_main_menu()
    
    def _show_main_menu(self):
        """Show main renamer menu"""
        while True:
            console.print("\n[bold cyan]📝 Renamer - Rename Media Files[/bold cyan]")
            console.print("[bold]Select media type:[/bold]\n")
            
            options = {
                "1": "Movies (Title (Year).ext)",
                "2": "TV Shows (Serie.S01E01.ext)",
                "3": "Anime (Anime.S01E01.ext)",
                "4": "Doramas (Dorama.S01E01.ext)",
                "5": "Music (## - Track.ext)",
                "6": "Books (Author - Title (Year).ext)",
                "7": "Comics (Series #Issue.ext)",
                "8": f"Dry-run: [{'ON' if self.dry_run else 'OFF'}]",
                "0": "Back to main menu"
            }
            
            for key, value in options.items():
                if key == "8":
                    color = "yellow" if self.dry_run else "green"
                    console.print(f"  [{key}] [{color}]{value}[/{color}]")
                else:
                    console.print(f"  [{key}] {value}")
            
            choice = Prompt.ask(
                "\nYour choice",
                choices=list(options.keys()),
                default="0"
            )
            
            if choice == "0":
                console.print("\n[blue]Returning to main menu...[/blue]")
                return
            elif choice == "8":
                self.dry_run = not self.dry_run
                console.print(f"[green]Dry-run turned {'ON' if self.dry_run else 'OFF'}[/green]")
                continue
            
            self._handle_rename_choice(choice)
    
    def _handle_rename_choice(self, choice: str):
        """Handle rename operation based on user choice"""
        # Get folder path
        folder_str = Prompt.ask("Enter folder path")
        folder = Path(folder_str)
        
        if not folder.exists():
            console.print(f"[red]✗ Folder does not exist: {folder}[/red]")
            return
        
        if not folder.is_dir():
            console.print(f"[red]✗ Path is not a directory: {folder}[/red]")
            return
        
        # Initialize app
        self.app = MediaOrganizerApp(dry_run=self.dry_run)
        stats = {'processed': 0, 'renamed': 0, 'failed': 0, 'skipped': 0}
        
        # Get metadata based on type
        metadata = self._get_metadata_for_type(choice)
        if not metadata:
            return
        
        # Execute rename
        console.print(f"\n[cyan]→ Renaming {metadata['type']} files in {folder}...[/cyan]\n")
        
        try:
            stats = self.app.rename_files_batch(folder, metadata)
            self._show_results(stats)
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")
            self.logger.error(f"Rename failed: {e}")
        finally:
            self.app.cleanup()
    
    def _get_metadata_for_type(self, choice: str) -> Optional[Dict]:
        """Get metadata dictionary based on media type choice"""
        try:
            if choice == "1":  # Movies
                title = Prompt.ask("Movie title")
                year = int(Prompt.ask("Year", default=str(_get_current_year())))
                return {'type': 'movie', 'title': title, 'year': year}
            
            elif choice == "2":  # TV Shows
                series = Prompt.ask("Series name")
                season = int(Prompt.ask("Season", default="1"))
                return {'type': 'tv', 'title': series, 'season': season}
            
            elif choice == "3":  # Anime
                anime = Prompt.ask("Anime name")
                season = int(Prompt.ask("Season", default="1"))
                return {'type': 'anime', 'title': anime, 'season': season}
            
            elif choice == "4":  # Doramas
                dorama = Prompt.ask("Dorama name")
                season = int(Prompt.ask("Season", default="1"))
                return {'type': 'dorama', 'title': dorama, 'season': season}
            
            elif choice == "5":  # Music
                track_num = int(Prompt.ask("Track number", default="1"))
                title = Prompt.ask("Track title")
                return {'type': 'music', 'title': title, 'track': track_num}
            
            elif choice == "6":  # Books
                author = Prompt.ask("Author")
                title = Prompt.ask("Title")
                year = int(Prompt.ask("Year", default=str(_get_current_year())))
                return {'type': 'book', 'title': title, 'author': author, 'year': year}
            
            elif choice == "7":  # Comics
                series = Prompt.ask("Series name")
                issue = int(Prompt.ask("Issue number", default="1"))
                return {'type': 'comic', 'title': series, 'issue': issue}
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled[/yellow]")
            return None
        except ValueError as e:
            console.print(f"[red]✗ Invalid input: {e}[/red]")
            return None
        
        return None
    
    def _show_results(self, stats: Dict):
        """Display rename results"""
        console.print("\n[bold cyan]📊 Results:[/bold cyan]")
        
        total = stats['processed']
        renamed = stats['renamed']
        skipped = stats['skipped']
        failed = stats['failed']
        
        # Progress bar
        if total > 0:
            success_rate = ((renamed + skipped) / total) * 100
            console.print(f"\n[dim]Success rate: {success_rate:.1f}%[/dim]")
        
        console.print(f"  Processed: [green]{total}[/green]")
        console.print(f"  Renamed:   [green]{renamed}[/green]")
        console.print(f"  Skipped:   [yellow]{skipped}[/yellow]")
        console.print(f"  Failed:    [red]{failed}[/red]")
        
        if self.dry_run:
            console.print("\n[yellow]⚠ DRY-RUN MODE - No files were modified[/yellow]")


def _get_current_year() -> int:
    """Get current year"""
    from datetime import datetime
    return datetime.now().year


def main():
    """Main entry point for renamer CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Rename media files to standardized patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.renamer                 # Interactive mode
  python -m src.renamer --dry-run       # Preview changes
  python -m src.renamer --type movie    # Direct mode (future)
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate changes without modifying files'
    )
    
    parser.add_argument(
        '--type',
        choices=['movie', 'tv', 'anime', 'dorama', 'music', 'book', 'comic'],
        help='Media type (future: direct mode)'
    )
    
    parser.add_argument(
        '--path',
        type=Path,
        help='Folder path (future: direct mode)'
    )
    
    parser.add_argument(
        '--title',
        type=str,
        help='Title/name (future: direct mode)'
    )
    
    parser.add_argument(
        '--season',
        type=int,
        help='Season number for TV/Anime/Dorama (future: direct mode)'
    )
    
    parser.add_argument(
        '--year',
        type=int,
        help='Year for movies/books (future: direct mode)'
    )
    
    args = parser.parse_args()
    
    # Initialize and run
    cli = RenamerCLI(dry_run=args.dry_run)
    
    try:
        cli.run()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠ Renamer interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    main()
