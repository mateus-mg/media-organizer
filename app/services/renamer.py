#!/usr/bin/env python3
"""Standalone Renamer CLI for music, books, and comics."""

import sys
from pathlib import Path

from rich.console import Console

from app.main import MediaOrganizerApp

console = Console()


class RenamerCLI:
    """Command-line interface for renaming supported media files."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def run(self):
        while True:
            console.print("\n[bold cyan]Renamer[/bold cyan]")
            console.print("[bold]Select media type:[/bold]\n")
            console.print("  [1] Music (## - Track.ext)")
            console.print("  [2] Books (Author - Title (Year).ext)")
            console.print("  [3] Comics (Series #Issue.ext)")
            console.print(
                f"  [4] Dry-run: [{'ON' if self.dry_run else 'OFF'}]")
            console.print("  [0] Exit")

            choice = input("\nYour choice [1/2/3/4/0] (0): ").strip() or "0"
            if choice == "0":
                return
            if choice == "4":
                self.dry_run = not self.dry_run
                continue
            if choice not in {"1", "2", "3"}:
                console.print("[red]Invalid option[/red]")
                continue

            folder = Path(input("Enter folder path: ").strip())
            if not folder.exists() or not folder.is_dir():
                console.print(f"[red]Invalid folder path: {folder}[/red]")
                continue

            metadata = None
            if choice == "1":
                track_num = int(input("Track number [1]: ").strip() or "1")
                title = input("Track title: ").strip()
                metadata = {"type": "music",
                            "title": title, "track": track_num}
            elif choice == "2":
                author = input("Author: ").strip()
                title = input("Title: ").strip()
                year = int(input("Year [2024]: ").strip() or "2024")
                metadata = {"type": "book", "title": title,
                            "author": author, "year": year}
            elif choice == "3":
                series = input("Series name: ").strip()
                issue = int(input("Issue number [1]: ").strip() or "1")
                metadata = {"type": "comic", "title": series, "issue": issue}

            if not metadata:
                continue

            app = MediaOrganizerApp(dry_run=self.dry_run)
            try:
                stats = app.rename_files_batch(folder, metadata)
                console.print("\n[bold cyan]Results:[/bold cyan]")
                console.print(
                    f"  Processed: [green]{stats['processed']}[/green]")
                console.print(
                    f"  Renamed:   [green]{stats['renamed']}[/green]")
                console.print(
                    f"  Skipped:   [yellow]{stats['skipped']}[/yellow]")
                console.print(f"  Failed:    [red]{stats['failed']}[/red]")
            finally:
                app.cleanup()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Rename supported media files")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate changes without modifying files")
    args = parser.parse_args()

    cli = RenamerCLI(dry_run=args.dry_run)

    try:
        cli.run()
    except KeyboardInterrupt:
        console.print("\nRenamer interrupted")
        sys.exit(0)
    except Exception as exc:
        console.print(f"\n[red]Error: {exc}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
