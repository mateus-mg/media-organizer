"""
Media Organization System - Main entry point.

Current scope:
- Music
- Books
- Comics
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import Dict

import click
from rich.console import Console
from rich.table import Table

from src.cli_manager import CLIManager
from src.config import Config
from src.core import (
    FileExistenceValidator,
    FileTypeValidator,
    IncompleteFileValidator,
    JunkFileValidator,
    MediaType,
    Orquestrador,
)
from src.detection import FileScanner, MediaClassifier
from src.integrations import FileCompletionValidator
from src.log_config import get_logger, set_console_log_level
from src.media_constants import SUPPORTED_MEDIA_EXTS
from src.metadata import enrich_book_metadata_with_online_sources
from src.organizers import BookOrganizer, LyricsOrganizer, MusicOrganizer, RenamerOrganizer
from src.persistence import format_datetime_br
from src.persistence import OrganizationDatabase
from src.utils import ConflictHandler


class MediaOrganizerApp:
    """Main application class."""

    def __init__(self, dry_run: bool = False):
        self.config = Config()
        self.dry_run = dry_run

        self.logger = get_logger(name="MediaOrganizer", dry_run=dry_run)
        set_console_log_level(logging.INFO if dry_run else logging.WARNING)

        is_valid, errors = self.config.is_valid()
        if not is_valid:
            for error in errors:
                self.logger.error(f"Configuration error: {error}")
            raise SystemExit(1)

        self.database = OrganizationDatabase(
            db_path=self.config.database_path,
            backup_enabled=self.config.database_backup_enabled,
            backup_keep_days=self.config.database_backup_keep_days,
        )

        self.conflict_handler = ConflictHandler(
            strategy=self.config.conflict_strategy,
            rename_pattern=self.config.conflict_rename_pattern,
            max_attempts=self.config.conflict_max_attempts,
        )

        self.validators = [
            FileExistenceValidator(logger=self.logger),
            FileTypeValidator(
                supported_types=sorted(SUPPORTED_MEDIA_EXTS),
                logger=self.logger,
            ),
            IncompleteFileValidator(logger=self.logger),
            JunkFileValidator(logger=self.logger),
        ]

        self.classifier = MediaClassifier(logger=self.logger)
        self.scanner = FileScanner(logger=self.logger)

        self.file_completion_validator = FileCompletionValidator(
            min_file_age_seconds=300,
            size_check_duration=5,
            logger=self.logger,
        )

        self.organizadores = {
            MediaType.MUSIC: MusicOrganizer(
                config=self.config,
                database=self.database,
                conflict_handler=self.conflict_handler,
                logger=self.logger,
                dry_run=self.dry_run,
            ),
            MediaType.LYRICS: LyricsOrganizer(
                config=self.config,
                database=self.database,
                conflict_handler=self.conflict_handler,
                logger=self.logger,
                dry_run=self.dry_run,
            ),
            MediaType.BOOK: BookOrganizer(
                config=self.config,
                database=self.database,
                conflict_handler=self.conflict_handler,
                logger=self.logger,
                dry_run=self.dry_run,
                book_type="book",
            ),
            MediaType.COMIC: BookOrganizer(
                config=self.config,
                database=self.database,
                conflict_handler=self.conflict_handler,
                logger=self.logger,
                dry_run=self.dry_run,
                book_type="comic",
            ),
            MediaType.RENAMER: RenamerOrganizer(
                config=self.config,
                database=self.database,
                conflict_handler=self.conflict_handler,
                logger=self.logger,
                dry_run=self.dry_run,
            ),
        }

        self.orchestrator = Orquestrador(
            validators=self.validators,
            organizadores=self.organizadores,
            classifier=self.classifier,
            scanner=self.scanner,
            database=self.database,
            file_completion_validator=self.file_completion_validator,
            logger=self.logger,
        )

    async def organize_directory(
        self,
        directory: Path,
        validate_completion: bool = True,
        source_label: str | None = None,
        progress_unit: str = "files",
    ) -> int:
        if not directory.exists() or not directory.is_dir():
            self.logger.error(f"Directory not found: {directory}")
            return 0

        processed = await self.orchestrator.organizar_arquivos(
            diretorio_origem=directory,
            validar_completude_arquivo=validate_completion,
            source_label=source_label,
            progress_unit=progress_unit,
        )
        return len(processed)

    def rename_files_batch(self, directory: Path, metadata: Dict):
        renamer = self.organizadores.get(MediaType.RENAMER)
        if renamer:
            return renamer.rename_batch(directory, metadata)
        return {"processed": 0, "renamed": 0, "failed": 0, "skipped": 0}

    def show_stats(self):
        stats = self.database.get_stats()

        table = Table(title="Organization Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Files Organized", str(
            stats.get("total_files_organized", 0)))
        table.add_row("Music Tracks", str(stats.get("music_tracks", 0)))
        table.add_row("Lyrics Files", str(stats.get("lyrics_files", 0)))
        table.add_row("Books", str(stats.get("books", 0)))
        table.add_row("Comics", str(stats.get("comics", 0)))
        table.add_row("Failed Operations", str(
            stats.get("failed_operations", 0)))

        Console().print(table)

    def cleanup(self):
        if hasattr(self, "database"):
            self.database.close()


@click.group()
@click.option("--dry-run", is_flag=True, help="Simulate operations without modifying files")
@click.pass_context
def cli(ctx, dry_run):
    """Media Organization System."""
    ctx.ensure_object(dict)
    ctx.obj["DRY_RUN"] = dry_run


@cli.command()
def organize():
    """Open organize interactive menu."""
    CLIManager().show_organize_menu()


@cli.command()
def interactive():
    """Open full interactive menu."""
    CLIManager().show_interactive_menu()


@cli.command()
def stats():
    """Show organization statistics."""
    app = MediaOrganizerApp()
    try:
        app.show_stats()
    finally:
        app.cleanup()


@cli.command()
def test():
    """Test configuration and database access."""
    console = Console()
    app = MediaOrganizerApp()
    try:
        stats_data = app.database.get_stats()
        console.print("Configuration loaded", style="green")
        console.print(
            f"Database accessible ({stats_data.get('total_files_organized', 0)} files tracked)",
            style="green",
        )
    finally:
        app.cleanup()


@cli.command()
@click.pass_context
def process_new_media(ctx):
    """Process new files from configured download folders."""
    dry_run = ctx.obj.get("DRY_RUN", False)
    app = MediaOrganizerApp(dry_run=dry_run)

    try:
        total_processed = 0
        download_paths = [
            ("Music", app.config.download_path_music, "tracks"),
            ("Books", app.config.download_path_books, "books"),
            ("Comics", app.config.download_path_comics, "comics"),
        ]

        for label, path, unit in download_paths:
            if path and path.exists():
                app.logger.info("Starting %s cycle from %s", label, path)
                processed = asyncio.run(
                    app.organize_directory(
                        path,
                        source_label=label,
                        progress_unit=unit,
                    )
                )
                total_processed += processed
                app.logger.info(
                    "%s cycle finished: %s %s processed",
                    label,
                    processed,
                    unit,
                )

        if total_processed > 0:
            Console().print(
                f"Successfully organized {total_processed} file(s)", style="green")
        else:
            Console().print("No new media files to organize", style="yellow")
    finally:
        app.cleanup()


@cli.command("preview-music-metadata")
@click.option(
    "--path",
    "music_path",
    type=click.Path(path_type=Path),
    default=Path("/home/mateus/Music"),
    show_default=True,
    help="Music directory to simulate metadata enrichment and organization",
)
def preview_music_metadata(music_path: Path):
    """Run music metadata enrichment in dry-run mode (no file/database changes)."""
    app = MediaOrganizerApp(dry_run=True)

    try:
        if not music_path.exists() or not music_path.is_dir():
            Console().print(f"Invalid directory: {music_path}", style="red")
            return

        processed = asyncio.run(
            app.organize_directory(
                music_path,
                validate_completion=False,
                source_label="Music",
                progress_unit="tracks",
            )
        )
        Console().print(
            f"Dry-run completed for {processed} file(s) in {music_path}",
            style="cyan",
        )
        Console().print(
            "No metadata tags, hardlinks, or database entries were written.",
            style="green",
        )
    finally:
        app.cleanup()


@cli.command("backfill-book-covers")
@click.option(
    "--limit",
    type=int,
    default=0,
    show_default=True,
    help="Limit number of books to process (0 = all)",
)
@click.pass_context
def backfill_book_covers(ctx, limit: int):
    """Backfill book covers using existing DB metadata (title/author) with Google Books."""
    dry_run = ctx.obj.get("DRY_RUN", False)
    app = MediaOrganizerApp(dry_run=dry_run)

    report = {
        "dry_run": dry_run,
        "limit": limit,
        "processed": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "reasons": {},
        "details": [],
    }

    def _count_reason(reason: str) -> None:
        report["reasons"][reason] = report["reasons"].get(reason, 0) + 1

    async def _run() -> None:
        book_organizer = app.organizadores[MediaType.BOOK]
        records = app.database.media_table.all()

        book_records = []
        for record in records:
            metadata = record.get("metadata") or {}
            media_type = str(metadata.get("media_type") or "").lower()
            media_subtype = str(metadata.get("media_subtype") or "").lower()
            if media_type == "book" or media_subtype == "book":
                book_records.append(record)

        if limit > 0:
            book_records = book_records[:limit]

        for record in book_records:
            report["processed"] += 1

            organized_path = Path(record.get("organized_path") or "")
            metadata = dict(record.get("metadata") or {})
            ext = organized_path.suffix.lower()

            detail = {
                "path": str(organized_path),
                "updated": False,
                "reason": "",
            }

            if ext not in {".epub", ".pdf"}:
                detail["reason"] = "unsupported_extension"
                report["skipped"] += 1
                _count_reason("unsupported_extension")
                report["details"].append(detail)
                continue

            if not organized_path.exists():
                detail["reason"] = "file_not_found"
                report["skipped"] += 1
                _count_reason("file_not_found")
                report["details"].append(detail)
                continue

            title = str(metadata.get("title") or "").strip()
            author = str(metadata.get("author") or "").strip()
            if not title or not author or author.lower() == "unknown author":
                detail["reason"] = "missing_title_or_author"
                report["skipped"] += 1
                _count_reason("missing_title_or_author")
                report["details"].append(detail)
                continue

            has_cover = book_organizer._book_has_embedded_cover(organized_path)
            if has_cover is True:
                detail["reason"] = "already_has_cover"
                report["skipped"] += 1
                _count_reason("already_has_cover")
                report["details"].append(detail)
                continue

            if has_cover is None:
                detail["reason"] = "unknown_cover_state"
                report["skipped"] += 1
                _count_reason("unknown_cover_state")
                report["details"].append(detail)
                continue

            try:
                enriched = await enrich_book_metadata_with_online_sources(
                    file_path=organized_path,
                    existing_metadata={"title": title, "author": author},
                    logger=app.logger,
                    use_google_books=app.config.enrich_book_metadata_google_books,
                    google_books_min_match_score=app.config.book_cover_min_match_score,
                    google_books_api_key=app.config.google_books_api_key,
                    include_cover_url=True,
                )
            except Exception as exc:
                detail["reason"] = "enrichment_error"
                detail["error"] = str(exc)
                report["errors"] += 1
                _count_reason("enrichment_error")
                report["details"].append(detail)
                continue

            cover_url = str(enriched.get("cover_image_url") or "").strip()
            if not cover_url:
                detail["reason"] = "no_cover_url_found"
                report["skipped"] += 1
                _count_reason("no_cover_url_found")
                report["details"].append(detail)
                continue

            writable_metadata = dict(metadata)
            writable_metadata["cover_image_url"] = cover_url

            if ext == ".epub":
                write_ok = book_organizer._write_epub_metadata(
                    organized_path, writable_metadata)
            else:
                write_ok = book_organizer._write_pdf_metadata(
                    organized_path, writable_metadata)

            if not write_ok:
                detail["reason"] = "write_failed"
                report["errors"] += 1
                _count_reason("write_failed")
                report["details"].append(detail)
                continue

            detail["updated"] = True
            detail["reason"] = "updated"
            detail["cover_url"] = cover_url
            report["updated"] += 1
            _count_reason("updated")
            report["details"].append(detail)

            if not dry_run:
                file_hash = record.get("file_hash")
                original_path = record.get("original_path")
                org_path = record.get("organized_path")
                if file_hash and original_path and org_path:
                    app.database.adicionar_midia(
                        file_hash=file_hash,
                        original_path=original_path,
                        organized_path=org_path,
                        metadata=writable_metadata,
                    )
                else:
                    # Fallback for unexpected incomplete rows
                    app.database.media_table.update(
                        {
                            "metadata": writable_metadata,
                            "last_checked": format_datetime_br(),
                        },
                        doc_ids=[record.doc_id],
                    )

    try:
        asyncio.run(_run())
    finally:
        out_path = Path("data/book_cover_backfill_report.json")
        out_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        Console().print(
            f"Backfill concluido | processados={report['processed']} | atualizados={report['updated']} | pulados={report['skipped']} | erros={report['errors']}",
            style="cyan",
        )
        Console().print(f"Relatorio: {out_path}", style="green")
        app.cleanup()


@cli.command("backfill-book-years")
@click.option(
    "--limit",
    type=int,
    default=0,
    show_default=True,
    help="Limit number of books to process (0 = all)",
)
@click.pass_context
def backfill_book_years(ctx, limit: int):
    """Backfill missing `(YYYY)` suffix in original source book filenames."""
    dry_run = ctx.obj.get("DRY_RUN", False)
    app = MediaOrganizerApp(dry_run=dry_run)

    report = {
        "dry_run": dry_run,
        "limit": limit,
        "processed": 0,
        "renamed": 0,
        "skipped": 0,
        "errors": 0,
        "reasons": {},
        "details": [],
    }

    def _count_reason(reason: str) -> None:
        report["reasons"][reason] = report["reasons"].get(reason, 0) + 1

    def _normalize_year(value) -> int | None:
        if isinstance(value, int):
            return value if 1000 <= value <= 2100 else None
        if isinstance(value, str):
            import re

            match = re.search(r"(\d{4})", value)
            if match:
                year = int(match.group(1))
                return year if 1000 <= year <= 2100 else None
        return None

    records = app.database.media_table.all()
    book_records = []
    for record in records:
        metadata = record.get("metadata") or {}
        media_type = str(metadata.get("media_type") or "").lower()
        media_subtype = str(metadata.get("media_subtype") or "").lower()
        if media_type == "book" or media_subtype == "book":
            book_records.append(record)

    if limit > 0:
        book_records = book_records[:limit]

    for record in book_records:
        report["processed"] += 1

        original_path = Path(record.get("original_path") or "")
        metadata = dict(record.get("metadata") or {})
        detail = {
            "path": str(original_path),
            "renamed": False,
            "reason": "",
        }

        if not original_path.exists() or not original_path.is_file():
            detail["reason"] = "file_not_found"
            report["skipped"] += 1
            _count_reason("file_not_found")
            report["details"].append(detail)
            continue

        if original_path.suffix.lower() not in {".epub", ".pdf", ".mobi", ".azw", ".azw3"}:
            detail["reason"] = "unsupported_extension"
            report["skipped"] += 1
            _count_reason("unsupported_extension")
            report["details"].append(detail)
            continue

        stem = original_path.stem
        import re

        if re.search(r"\(\d{4}\)\s*$", stem):
            detail["reason"] = "already_has_year"
            report["skipped"] += 1
            _count_reason("already_has_year")
            report["details"].append(detail)
            continue

        year = _normalize_year(metadata.get("year"))
        if not year:
            detail["reason"] = "missing_valid_year_metadata"
            report["skipped"] += 1
            _count_reason("missing_valid_year_metadata")
            report["details"].append(detail)
            continue

        new_name = f"{stem} ({year}){original_path.suffix}"
        target_path = original_path.with_name(new_name)

        if target_path.exists():
            detail["reason"] = "target_already_exists"
            detail["target"] = str(target_path)
            report["skipped"] += 1
            _count_reason("target_already_exists")
            report["details"].append(detail)
            continue

        if dry_run:
            detail["renamed"] = True
            detail["reason"] = "would_rename"
            detail["target"] = str(target_path)
            report["renamed"] += 1
            _count_reason("would_rename")
            report["details"].append(detail)
            continue

        try:
            original_path.rename(target_path)
            app.database.media_table.update(
                {
                    "original_path": str(target_path),
                    "last_checked": format_datetime_br(),
                    "metadata": metadata,
                },
                doc_ids=[record.doc_id],
            )

            detail["renamed"] = True
            detail["reason"] = "renamed"
            detail["target"] = str(target_path)
            report["renamed"] += 1
            _count_reason("renamed")
            report["details"].append(detail)
        except Exception as exc:
            detail["reason"] = "rename_error"
            detail["error"] = str(exc)
            report["errors"] += 1
            _count_reason("rename_error")
            report["details"].append(detail)

    out_path = Path("data/book_year_backfill_report.json")
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    Console().print(
        f"Backfill de ano concluido | processados={report['processed']} | renomeados={report['renamed']} | pulados={report['skipped']} | erros={report['errors']}",
        style="cyan",
    )
    Console().print(f"Relatorio: {out_path}", style="green")
    app.cleanup()


if __name__ == "__main__":
    cli()
