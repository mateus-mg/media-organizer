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
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

import click
from rich.console import Console
from rich.table import Table

from app.cli import CLIManager
from app.config import Config
from app.core import (
    FileExistenceValidator,
    FileTypeValidator,
    IncompleteFileValidator,
    JunkFileValidator,
    MediaType,
    Orquestrador,
)
from app.core.detection import FileScanner, MediaClassifier
from app.features import FilenameSuggestionEngine, iter_preview_lines
from app.validators import FileCompletionValidator
from app.logging import get_logger, set_console_log_level
from app.config.constants import SUPPORTED_MEDIA_EXTS
from app.metadata import enrich_book_metadata_with_online_sources
from app.services import ArtworkOrganizer, BookOrganizer, LyricsOrganizer, MusicOrganizer, RenamerOrganizer
from app.infrastructure.database import format_datetime_br
from app.infrastructure import OrganizationDatabase
from app.utils.helpers import ConflictHandler


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw not in (None, "") else int(default)
    except Exception:
        value = int(default)
    return max(minimum, value)


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
            min_file_age_seconds=_env_int(
                "FILE_COMPLETION_MIN_AGE_SECONDS", 300, minimum=0),
            size_check_duration=_env_int(
                "FILE_COMPLETION_SIZE_CHECK_DURATION_SECONDS", 5, minimum=0),
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
            MediaType.ARTWORK: ArtworkOrganizer(
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
        if hasattr(self, "organizadores"):
            for organizer in self.organizadores.values():
                if hasattr(organizer, "close"):
                    organizer.close()
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


@cli.command("music-genre-backfill")
@click.option(
    "--execute",
    is_flag=True,
    help="Apply updates to file tags (default is dry-run preview).",
)
@click.pass_context
def music_genre_backfill(ctx, execute: bool):
    """Admin-only music genre backfill for already organized tracks."""
    from app.services.organizers import MusicOrganizer

    console = Console()
    cli_dry_run = bool(ctx.obj.get("DRY_RUN", False))
    effective_dry_run = True
    if execute and not cli_dry_run:
        effective_dry_run = False

    if execute and cli_dry_run:
        console.print(
            "--execute ignored because global --dry-run is enabled",
            style="yellow",
        )

    app = None
    try:
        app = MediaOrganizerApp(dry_run=effective_dry_run)
        music_organizer = MusicOrganizer(
            config=app.config,
            database=app.database,
            conflict_handler=None,
            logger=app.logger,
            dry_run=effective_dry_run,
        )

        report = asyncio.run(
            music_organizer.backfill_music_genres(dry_run=effective_dry_run))

        mode = "DRY RUN" if effective_dry_run else "EXECUTE"
        console.print(f"Music genre backfill finished ({mode})", style="cyan")
        console.print(f"Processed: {report.get('total_tracks_processed', 0)}")
        console.print(
            f"MusicBrainz: {report.get('tracks_enriched_from_musicbrainz', 0)}")
        console.print(
            f"Last.fm: {report.get('tracks_enriched_from_lastfm', 0)}")
        console.print(
            f"Skipped (already has genre): {report.get('tracks_skipped_already_has_genre', 0)}")
        console.print(
            f"No genre found: {report.get('tracks_with_no_genre_found', 0)}")
        console.print(f"Errors: {report.get('tracks_with_file_errors', 0)}")
    finally:
        if app is not None:
            app.cleanup()


@cli.command("backup-integrity")
@click.option("--cleanup", is_flag=True, help="Run cleanup for old backups after integrity report")
def backup_integrity(cleanup):
    """Check backup integrity and optionally clean old backups."""
    console = Console()
    app = MediaOrganizerApp()

    def _collect_backup_status(backup_dir: Path, keep_days: int):
        prefix_to_label = {
            "organization_": "organization",
            "invalid_music_genres_": "invalid_genres",
            "suspect_music_genres_": "suspect_genres",
            "link_registry_": "link_registry",
            "artist_genre_cache_": "artist_genre_cache",
            "genre_exceptions_": "genre_exceptions",
            "musical_keywords_": "musical_keywords",
            "genre_guard_cycle_report_": "genre_guard_cycle_report",
            "genre_guard_decisions_latest_": "genre_guard_decisions_latest",
            "genre_guard_rule_suggestions_": "genre_guard_rule_suggestions",
            "trash_index_": "trash_index",
        }
        cutoff = datetime.now() - timedelta(days=keep_days)
        status = {}

        for prefix, label in prefix_to_label.items():
            files = sorted(backup_dir.glob(
                f"{prefix}*.json")) if backup_dir.exists() else []
            parsed = []
            invalid_names = []

            for file_path in files:
                timestamp_str = file_path.stem.replace(prefix, "")
                try:
                    ts = datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S")
                    parsed.append((file_path, ts))
                except ValueError:
                    invalid_names.append(file_path.name)

            old_count = sum(1 for _, ts in parsed if ts < cutoff)
            latest = max((ts for _, ts in parsed), default=None)
            status[label] = {
                "total": len(files),
                "old": old_count,
                "invalid_names": invalid_names,
                "latest": latest,
            }

        return status

    try:
        backup_dir = app.database.backup_dir
        keep_days = app.database.backup_keep_days

        before = _collect_backup_status(backup_dir, keep_days)

        table = Table(title="Backup Integrity")
        table.add_column("Artifact", style="cyan")
        table.add_column("Total", style="green")
        table.add_column(f"Old (>{keep_days}d)", style="yellow")
        table.add_column("Invalid Names", style="red")
        table.add_column("Latest", style="white")

        for artifact, values in before.items():
            latest_str = values["latest"].strftime(
                "%Y-%m-%d %H:%M:%S") if values["latest"] else "-"
            invalid_str = str(len(values["invalid_names"]))
            table.add_row(
                artifact,
                str(values["total"]),
                str(values["old"]),
                invalid_str,
                latest_str,
            )

        console.print(table)

        if cleanup:
            app.database.cleanup_old_backups()
            after = _collect_backup_status(backup_dir, keep_days)

            cleanup_table = Table(title="Backup Cleanup Result")
            cleanup_table.add_column("Artifact", style="cyan")
            cleanup_table.add_column("Removed", style="green")
            cleanup_table.add_column("Remaining", style="white")

            for artifact, values in before.items():
                removed = max(values["total"] -
                              after.get(artifact, {}).get("total", 0), 0)
                remaining = after.get(artifact, {}).get("total", 0)
                cleanup_table.add_row(artifact, str(removed), str(remaining))

            console.print(cleanup_table)

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

                if label == "Music":
                    music_org = app.organizadores.get(MediaType.MUSIC)
                    if music_org is not None and hasattr(music_org, "clean_invalid_genres_in_directory"):
                        preclean_report = music_org.clean_invalid_genres_in_directory(
                            path,
                            dry_run=dry_run,
                        )
                        app.logger.info(
                            "Music pre-clean finished: processed=%d updated=%d removed_genres=%d errors=%d",
                            preclean_report.get("processed", 0),
                            preclean_report.get("updated", 0),
                            preclean_report.get("removed_genre_values", 0),
                            preclean_report.get("errors", 0),
                        )

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

                if label == "Music":
                    music_org = app.organizadores.get(MediaType.MUSIC)
                    if music_org is not None and hasattr(music_org, "reprocess_db_tracks_with_invalid_genres"):
                        db_reprocess_report = music_org.reprocess_db_tracks_with_invalid_genres(
                            dry_run=dry_run,
                        )
                        app.logger.info(
                            "Music DB invalid-genre recheck finished: scanned=%d flagged=%d db_updates=%d reprocessed=%d updated=%d removed_genres=%d errors=%d",
                            db_reprocess_report.get(
                                "music_records_scanned", 0),
                            db_reprocess_report.get(
                                "tracks_flagged_invalid_genres", 0),
                            db_reprocess_report.get("db_metadata_updates", 0),
                            db_reprocess_report.get("tracks_reprocessed", 0),
                            db_reprocess_report.get("tracks_updated", 0),
                            db_reprocess_report.get("removed_genre_values", 0),
                            db_reprocess_report.get("file_errors", 0),
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
    default=Path(os.getenv("PREVIEW_MUSIC_METADATA_PATH",
                 str(Path.home() / "Music"))),
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
    default=_env_int("BOOK_BACKFILL_LIMIT_DEFAULT", 0, minimum=0),
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
        out_path = Path(os.getenv(
            "BOOK_COVER_BACKFILL_REPORT_PATH",
            "data/book_cover_backfill_report.json",
        ))
        out_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        Console().print(
            f"Backfill completed | processed={report['processed']} | updated={report['updated']} | skipped={report['skipped']} | errors={report['errors']}",
            style="cyan",
        )
        Console().print(f"Report: {out_path}", style="green")
        app.cleanup()


@cli.command("backfill-book-years")
@click.option(
    "--limit",
    type=int,
    default=_env_int("BOOK_BACKFILL_LIMIT_DEFAULT", 0, minimum=0),
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

    out_path = Path(os.getenv(
        "BOOK_YEAR_BACKFILL_REPORT_PATH",
        "data/book_year_backfill_report.json",
    ))
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    Console().print(
        f"Year backfill completed | processed={report['processed']} | renamed={report['renamed']} | skipped={report['skipped']} | errors={report['errors']}",
        style="cyan",
    )
    Console().print(f"Report: {out_path}", style="green")
    app.cleanup()


@cli.command("suggest-filenames")
@click.option(
    "--root",
    "root_path",
    type=click.Path(path_type=Path, exists=True,
                    file_okay=False, dir_okay=True),
    required=True,
    help="Root directory to analyze recursively",
)
@click.option(
    "--media",
    "media_filter",
    type=click.Choice(["all", "books", "comics"], case_sensitive=False),
    default="all",
    show_default=True,
    help="Limit suggestions by media type",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=Path(os.getenv(
        "FILENAME_SUGGESTIONS_REPORT_PATH",
        "data/filename_suggestions_report.json",
    )),
    show_default=True,
    help="Path to write JSON report",
)
@click.option(
    "--preview-limit",
    type=int,
    default=_env_int("FILENAME_PREVIEW_LIMIT_DEFAULT", 30, minimum=0),
    show_default=True,
    help="How many suggestions to print in terminal preview",
)
def suggest_filenames(
    root_path: Path,
    media_filter: str,
    output_path: Path,
    preview_limit: int,
):
    """Suggest ideal filenames for books and comics under a root folder."""
    logger = get_logger(name="FilenameSuggestions", dry_run=True)
    classifier = MediaClassifier(logger=logger)
    engine = FilenameSuggestionEngine(classifier=classifier)

    report = engine.suggest_for_root(
        root_path=root_path,
        media_filter=media_filter.lower(),
    )
    engine.save_report(report, output_path)

    console = Console()
    console.print(
        (
            f"Suggestions generated | scanned={report['total_files_scanned']} | "
            f"considered={report['total_suggestions']} | changed={report['changed_suggestions']}"
        ),
        style="cyan",
    )
    console.print(f"Report: {output_path}", style="green")

    for line in iter_preview_lines(report, limit=max(0, preview_limit)):
        console.print(line)


@cli.command("edit-filename-suggestion")
@click.option(
    "--report",
    "report_path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    required=True,
    help="JSON report generated by suggest-filenames",
)
@click.option(
    "--index",
    type=int,
    required=True,
    help="Suggestion index in report['suggestions']",
)
@click.option(
    "--new-name",
    required=True,
    help="Manual corrected filename suggestion",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Output path for updated report (default: overwrite input report)",
)
def edit_filename_suggestion(
    report_path: Path,
    index: int,
    new_name: str,
    output_path: Path | None,
):
    """Edit one suggestion in a report to increase precision manually."""
    engine = FilenameSuggestionEngine()
    report = engine.load_report(report_path)

    try:
        updated = engine.update_report_suggestion(
            report=report,
            index=index,
            new_name=new_name,
        )
    except (IndexError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    learned = engine.learn_from_report(updated, only_manual=True)

    final_output = output_path or report_path
    engine.save_report(updated, final_output)

    console = Console()
    console.print(
        (
            f"Suggestion updated | index={index} | "
            f"changed={updated['changed_suggestions']} | unchanged={updated['unchanged_suggestions']}"
        ),
        style="cyan",
    )
    console.print(
        (
            "Learning updated | "
            f"exact={learned['exact_overrides']} | "
            f"comic_aliases={learned['comic_series_aliases']} | "
            f"book_aliases={learned['book_author_aliases']}"
        ),
        style="green",
    )
    console.print(f"Report: {final_output}", style="green")


@cli.command("apply-filename-suggestions")
@click.option(
    "--report",
    "report_path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    required=True,
    help="JSON report generated by suggest-filenames",
)
@click.option(
    "--execute",
    is_flag=True,
    help="Apply renames on disk (default is dry-run)",
)
@click.option(
    "--preview-limit",
    type=int,
    default=_env_int("FILENAME_PREVIEW_LIMIT_DEFAULT", 30, minimum=0),
    show_default=True,
    help="How many apply results to print in terminal preview",
)
def apply_filename_suggestions(report_path: Path, execute: bool, preview_limit: int):
    """Apply filename suggestions from a JSON report."""
    engine = FilenameSuggestionEngine()
    report = engine.load_report(report_path)
    result = engine.apply_report(report=report, dry_run=not execute)

    output_path = Path(os.getenv(
        "FILENAME_SUGGESTIONS_APPLY_REPORT_PATH",
        "data/filename_suggestions_apply_report.json",
    ))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    console = Console()
    mode = "EXECUTE" if execute else "DRY-RUN"
    console.print(
        (
            f"Apply suggestions ({mode}) | processed={result['processed']} | "
            f"renamed={result['renamed']} | skipped={result['skipped']} | errors={result['errors']}"
        ),
        style="cyan",
    )
    console.print(f"Report: {output_path}", style="green")

    for item in result.get("details", [])[:max(0, preview_limit)]:
        old = item.get("original_path", "")
        new = item.get("target_path", item.get("suggested_name", ""))
        status = item.get("status", "")
        console.print(f"[{status}] {old} => {new}")


if __name__ == "__main__":
    cli()
