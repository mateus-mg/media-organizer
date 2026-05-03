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
from typing import Any, Awaitable, Callable, Dict, List

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
from app.services import ArtworkOrganizer, BookOrganizer, LyricsOrganizer, MusicOrganizer, RenamerOrganizer, PlaylistService
from app.infrastructure.database import format_datetime_br
from app.infrastructure import OrganizationDatabase
from app.infrastructure import NavidromeClient
from app.utils.helpers import ConflictHandler, log_cycle_stage, run_logged_cycle


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


@cli.command("navidrome-test")
def navidrome_test():
    """Test connection to Navidrome Subsonic API."""
    console = Console()
    config = Config()

    if not config.navidrome_enabled:
        console.print("NAVIDROME_ENABLED=false", style="yellow")
        return

    client = NavidromeClient(config)
    try:
        client.ping()
        playlists = client.get_playlists()
        console.print("Navidrome connection successful", style="green")
        console.print(f"Playlists visible: {len(playlists)}", style="cyan")
    except Exception as exc:
        console.print(f"Navidrome connection failed: {exc}", style="red")
        raise SystemExit(1)
    finally:
        client.close()


@cli.command("navidrome-playlists")
def navidrome_playlists():
    """List playlists available in Navidrome."""
    console = Console()
    config = Config()

    if not config.navidrome_enabled:
        console.print("NAVIDROME_ENABLED=false", style="yellow")
        return

    client = NavidromeClient(config)
    try:
        playlists = client.get_playlists()
        if not playlists:
            console.print("No playlists found.", style="yellow")
            return

        table = Table(title="Navidrome Playlists")
        table.add_column("Name", style="cyan")
        table.add_column("ID", style="green")
        table.add_column("Songs", style="magenta")
        table.add_column("Owner", style="yellow")

        for playlist in playlists:
            table.add_row(
                str(playlist.get("name", "")),
                str(playlist.get("id", "")),
                str(playlist.get("songCount", 0)),
                str(playlist.get("owner", "")),
            )

        console.print(table)
    except Exception as exc:
        console.print(f"Could not list playlists: {exc}", style="red")
        raise SystemExit(1)
    finally:
        client.close()


@cli.command("navidrome-sync-simple")
@click.option("--name", required=True, help="Playlist name in Navidrome")
@click.option("--artist", default="", help="Artist filter (contains)")
@click.option("--genre", default="", help="Genre filter (contains)")
@click.option("--album", default="", help="Album filter (contains)")
@click.option("--limit", default=0, type=int, help="Max tracks (0 = no limit)")
@click.option("--public", "is_public", is_flag=True, help="Create/update as public playlist")
@click.option(
    "--mode",
    type=click.Choice(["recreate", "incremental"], case_sensitive=False),
    default="incremental",
    show_default=True,
    help="Sync strategy: recreate playlist or apply incremental diff",
)
@click.option(
    "--preview-diff",
    is_flag=True,
    help="Preview additions/removals without applying remote/local changes",
)
def navidrome_sync_simple(name: str, artist: str, genre: str, album: str, limit: int, is_public: bool, mode: str, preview_diff: bool):
    """Sync a simple playlist from organization.json using metadata filters."""
    console = Console()
    config = Config()

    if not config.navidrome_enabled:
        console.print("NAVIDROME_ENABLED=false", style="yellow")
        return

    service = PlaylistService(config)
    try:
        report = service.sync_simple_playlist_from_organization(
            name=name,
            public=is_public,
            artist_filter=artist,
            genre_filter=genre,
            album_filter=album,
            limit=max(0, int(limit)),
            mode=(mode or "incremental").lower(),
            preview_only=bool(preview_diff),
        )
        if preview_diff:
            console.print(
                f"Simple playlist preview generated ({(mode or 'incremental').lower()})", style="green")
        else:
            console.print(
                f"Simple playlist synced ({(mode or 'incremental').lower()})", style="green")
        console.print(
            f"Matched={report.get('matched_records', 0)} | Resolved={report.get('resolved_count', 0)} | Unresolved={report.get('unresolved_count', 0)}",
            style="cyan",
        )

        preview = report.get("preview") or {}
        if preview:
            add_count = int(preview.get("to_add_count", 0) or 0)
            remove_count = int(preview.get("to_remove_count", 0) or 0)
            console.print(
                f"Diff: add={add_count} | remove={remove_count} | existing={preview.get('existing_song_count', 0)} | target={preview.get('target_song_count', 0)}",
                style="magenta",
            )
            if preview_diff:
                if add_count == 0 and remove_count == 0:
                    console.print(
                        "Summary: no adjustments needed, playlist is already aligned with filters.",
                        style="magenta",
                    )
                else:
                    console.print(
                        f"Summary: would add {add_count} track(s) and remove {remove_count} track(s) to align with current filters.",
                        style="magenta",
                    )
                add_samples = preview.get("to_add_song_ids", [])
                remove_samples = preview.get("to_remove_song_ids", [])
                if add_samples:
                    console.print("Sample IDs to add:", style="magenta")
                    for song_id in add_samples[:10]:
                        console.print(f"+ {song_id}")
                if remove_samples:
                    console.print("Sample IDs to remove:", style="magenta")
                    for song_id in remove_samples[:10]:
                        console.print(f"- {song_id}")

        unresolved_paths = report.get("unresolved_paths", [])
        if unresolved_paths:
            console.print("Unresolved examples:", style="yellow")
            for path in unresolved_paths[:10]:
                console.print(f"- {path}")
    except Exception as exc:
        console.print(f"Sync failed: {exc}", style="red")
        raise SystemExit(1)


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


@cli.command("music-metadata-normalize-albums")
@click.option(
    "--execute",
    is_flag=True,
    help="Apply album metadata normalization (default is dry-run preview).",
)
@click.pass_context
def music_metadata_normalize_albums(ctx, execute: bool):
    """Audit and normalize album identity metadata across organized music tracks."""
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

        report = music_organizer.reprocess_db_tracks_with_album_identity(
            dry_run=effective_dry_run,
        )

        mode = "DRY RUN" if effective_dry_run else "EXECUTE"
        console.print(
            f"Album metadata normalization finished ({mode})", style="cyan")
        console.print(
            f"Scanned tracks: {report.get('music_records_scanned', 0)}")
        console.print(
            f"Album groups scanned: {report.get('album_groups_scanned', 0)}")
        console.print(
            f"Groups with variants: {report.get('album_groups_with_variants', 0)}")
        console.print(f"Files skipped: {report.get('files_skipped', 0)}")
        console.print(f"Files updated: {report.get('tracks_updated', 0)}")
        console.print(f"Errors: {report.get('file_errors', 0)}")

        groups = report.get("groups") or []
        if groups:
            table = Table(title="Album Metadata Variants")
            table.add_column("Artist", style="cyan")
            table.add_column("Album", style="green")
            table.add_column("Years", style="magenta")
            table.add_column("Album Variants", style="yellow")
            table.add_column("Artist Variants", style="blue")
            table.add_column("Tracks", style="white")
            for group in groups[:20]:
                table.add_row(
                    str(group.get("artist", "")),
                    str(group.get("album", "")),
                    ", ".join(str(year)
                              for year in group.get("years", [])) or "-",
                    str(len(group.get("album_variants", []))),
                    str(len(group.get("album_artist_variants", []))),
                    str(group.get("tracks", 0)),
                )
            console.print(table)
            if len(groups) > 20:
                console.print(
                    f"Showing first 20 of {len(groups)} variant group(s)", style="yellow")
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

    def _run_music_preclean(path: Path) -> None:
        log_cycle_stage(app.logger, "Music | PRE-CLEAN START")
        music_org = app.organizadores.get(MediaType.MUSIC)
        if music_org is None:
            log_cycle_stage(app.logger, "Music | PRE-CLEAN END")
            return
        if hasattr(music_org, "clean_invalid_genres_in_directory"):
            preclean_report = music_org.clean_invalid_genres_in_directory(
                path,
                dry_run=dry_run,
            )
            app.logger.info(
                "Music pre-clean finished: files-processed=%d files-updated=%d genres-removed=%d errors=%d",
                preclean_report.get("processed", 0),
                preclean_report.get("updated", 0),
                preclean_report.get("removed_genre_values", 0),
                preclean_report.get("errors", 0),
            )
        log_cycle_stage(app.logger, "Music | PRE-CLEAN END")

    def _run_music_db_recheck() -> None:
        log_cycle_stage(app.logger, "Music | DB RECHECK START")
        music_org = app.organizadores.get(MediaType.MUSIC)
        if music_org is None:
            log_cycle_stage(app.logger, "Music | DB RECHECK END")
            return
        if hasattr(music_org, "reprocess_db_tracks_with_invalid_genres"):
            db_reprocess_report = music_org.reprocess_db_tracks_with_invalid_genres(
                dry_run=dry_run,
            )
            app.logger.info(
                "Music DB invalid-genre recheck finished: scanned=%d invalid-found=%d normalization-needed=%d db-updates=%d files-reprocessed=%d files-updated=%d genres-removed=%d errors=%d",
                db_reprocess_report.get("music_records_scanned", 0),
                db_reprocess_report.get("tracks_flagged_invalid_genres", 0),
                db_reprocess_report.get(
                    "tracks_flagged_genre_normalization", 0),
                db_reprocess_report.get("db_metadata_updates", 0),
                db_reprocess_report.get("tracks_reprocessed", 0),
                db_reprocess_report.get("tracks_updated", 0),
                db_reprocess_report.get("removed_genre_values", 0),
                db_reprocess_report.get("file_errors", 0),
            )
        if hasattr(music_org, "reprocess_db_tracks_with_album_identity"):
            album_reprocess_report = music_org.reprocess_db_tracks_with_album_identity(
                dry_run=dry_run,
            )
            app.logger.info(
                "Music DB album-identity recheck finished: scanned=%d groups=%d groups-with-variants=%d files-updated=%d files-skipped=%d errors=%d",
                album_reprocess_report.get("music_records_scanned", 0),
                album_reprocess_report.get("album_groups_scanned", 0),
                album_reprocess_report.get("album_groups_with_variants", 0),
                album_reprocess_report.get("tracks_updated", 0),
                album_reprocess_report.get("files_skipped", 0),
                album_reprocess_report.get("file_errors", 0),
            )
        log_cycle_stage(app.logger, "Music | DB RECHECK END")

    try:
        total_processed = 0
        download_paths = [
            ("Music", app.config.download_path_music, "tracks"),
            ("Books", app.config.download_path_books, "books"),
            ("Comics", app.config.download_path_comics, "comics"),
        ]

        for label, path, unit in download_paths:
            if path and path.exists():
                processed = run_logged_cycle(
                    logger=app.logger,
                    label=label,
                    run_organization=lambda p=path, l=label, u=unit: asyncio.run(
                        app.organize_directory(
                            p,
                            source_label=l,
                            progress_unit=u,
                        )
                    ),
                    on_pre_organization=(
                        (lambda p=path: _run_music_preclean(p))
                        if label == "Music"
                        else None
                    ),
                    on_post_organization=(
                        _run_music_db_recheck if label == "Music" else None
                    ),
                    on_cycle_start=(
                        lambda p=path, l=label: app.logger.info(
                            "Starting %s cycle from %s", l, p
                        )
                    ),
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


def _collect_book_records_for_backfill(app: MediaOrganizerApp, limit: int) -> List[Dict[str, Any]]:
    records = app.database.media_table.all()
    book_records: List[Dict[str, Any]] = []
    for record in records:
        metadata = record.get("metadata") or {}
        media_type = str(metadata.get("media_type") or "").lower()
        media_subtype = str(metadata.get("media_subtype") or "").lower()
        if media_type == "book" or media_subtype == "book":
            book_records.append(record)

    if limit > 0:
        return book_records[:limit]
    return book_records


def _new_backfill_report(dry_run: bool, limit: int, success_key: str) -> Dict[str, Any]:
    return {
        "dry_run": dry_run,
        "limit": limit,
        "processed": 0,
        success_key: 0,
        "skipped": 0,
        "errors": 0,
        "reasons": {},
        "details": [],
    }


def _count_backfill_reason(report: Dict[str, Any], reason: str) -> None:
    report["reasons"][reason] = report["reasons"].get(reason, 0) + 1


def _write_backfill_report(report: Dict[str, Any], env_var: str, default_path: str) -> Path:
    out_path = Path(os.getenv(env_var, default_path))
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


async def _run_book_backfill_engine(
    app: MediaOrganizerApp,
    *,
    limit: int,
    dry_run: bool,
    success_key: str,
    strategy: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Generic engine for book backfill flows with pluggable record strategy."""
    report = _new_backfill_report(
        dry_run=dry_run, limit=limit, success_key=success_key)
    records = _collect_book_records_for_backfill(app, limit)

    for record in records:
        report["processed"] += 1
        outcome = await strategy(record)

        status = str(outcome.get("status") or "skipped").lower()
        reason = str(outcome.get("reason") or "unknown")
        detail = dict(outcome.get("detail") or {})
        if "reason" not in detail:
            detail["reason"] = reason

        if status == "success":
            report[success_key] += 1
        elif status == "error":
            report["errors"] += 1
        else:
            report["skipped"] += 1

        _count_backfill_reason(report, reason)
        report["details"].append(detail)

    return report


def _normalize_year_value(value: Any) -> int | None:
    if isinstance(value, int):
        return value if 1000 <= value <= 2100 else None
    if isinstance(value, str):
        match = re.search(r"(\d{4})", value)
        if match:
            year = int(match.group(1))
            return year if 1000 <= year <= 2100 else None
    return None


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
    report = _new_backfill_report(
        dry_run=dry_run, limit=limit, success_key="updated")

    async def _run() -> Dict[str, Any]:
        book_organizer = app.organizadores[MediaType.BOOK]

        async def _strategy(record: Dict[str, Any]) -> Dict[str, Any]:
            organized_path = Path(record.get("organized_path") or "")
            metadata = dict(record.get("metadata") or {})
            ext = organized_path.suffix.lower()

            detail = {
                "path": str(organized_path),
                "updated": False,
            }

            if ext not in {".epub", ".pdf"}:
                return {
                    "status": "skipped",
                    "reason": "unsupported_extension",
                    "detail": detail,
                }

            if not organized_path.exists():
                return {
                    "status": "skipped",
                    "reason": "file_not_found",
                    "detail": detail,
                }

            title = str(metadata.get("title") or "").strip()
            author = str(metadata.get("author") or "").strip()
            if not title or not author or author.lower() == "unknown author":
                return {
                    "status": "skipped",
                    "reason": "missing_title_or_author",
                    "detail": detail,
                }

            has_cover = book_organizer._book_has_embedded_cover(organized_path)
            if has_cover is True:
                return {
                    "status": "skipped",
                    "reason": "already_has_cover",
                    "detail": detail,
                }

            if has_cover is None:
                return {
                    "status": "skipped",
                    "reason": "unknown_cover_state",
                    "detail": detail,
                }

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
                detail["error"] = str(exc)
                return {
                    "status": "error",
                    "reason": "enrichment_error",
                    "detail": detail,
                }

            cover_url = str(enriched.get("cover_image_url") or "").strip()
            if not cover_url:
                return {
                    "status": "skipped",
                    "reason": "no_cover_url_found",
                    "detail": detail,
                }

            writable_metadata = dict(metadata)
            writable_metadata["cover_image_url"] = cover_url

            if ext == ".epub":
                write_ok = book_organizer._write_epub_metadata(
                    organized_path, writable_metadata)
            else:
                write_ok = book_organizer._write_pdf_metadata(
                    organized_path, writable_metadata)

            if not write_ok:
                return {
                    "status": "error",
                    "reason": "write_failed",
                    "detail": detail,
                }

            detail["updated"] = True
            detail["cover_url"] = cover_url

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

            return {
                "status": "success",
                "reason": "updated",
                "detail": detail,
            }

        return await _run_book_backfill_engine(
            app,
            limit=limit,
            dry_run=dry_run,
            success_key="updated",
            strategy=_strategy,
        )

    try:
        report = asyncio.run(_run())
    finally:
        out_path = _write_backfill_report(
            report,
            "BOOK_COVER_BACKFILL_REPORT_PATH",
            "data/book_cover_backfill_report.json",
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
    report = _new_backfill_report(
        dry_run=dry_run, limit=limit, success_key="renamed")

    async def _run() -> Dict[str, Any]:
        async def _strategy(record: Dict[str, Any]) -> Dict[str, Any]:
            original_path = Path(record.get("original_path") or "")
            metadata = dict(record.get("metadata") or {})
            detail = {
                "path": str(original_path),
                "renamed": False,
            }

            if not original_path.exists() or not original_path.is_file():
                return {
                    "status": "skipped",
                    "reason": "file_not_found",
                    "detail": detail,
                }

            if original_path.suffix.lower() not in {".epub", ".pdf", ".mobi", ".azw", ".azw3"}:
                return {
                    "status": "skipped",
                    "reason": "unsupported_extension",
                    "detail": detail,
                }

            stem = original_path.stem

            if re.search(r"\(\d{4}\)\s*$", stem):
                return {
                    "status": "skipped",
                    "reason": "already_has_year",
                    "detail": detail,
                }

            year = _normalize_year_value(metadata.get("year"))
            if not year:
                return {
                    "status": "skipped",
                    "reason": "missing_valid_year_metadata",
                    "detail": detail,
                }

            new_name = f"{stem} ({year}){original_path.suffix}"
            target_path = original_path.with_name(new_name)

            if target_path.exists():
                detail["target"] = str(target_path)
                return {
                    "status": "skipped",
                    "reason": "target_already_exists",
                    "detail": detail,
                }

            if dry_run:
                detail["renamed"] = True
                detail["target"] = str(target_path)
                return {
                    "status": "success",
                    "reason": "would_rename",
                    "detail": detail,
                }

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
                detail["target"] = str(target_path)
                return {
                    "status": "success",
                    "reason": "renamed",
                    "detail": detail,
                }
            except Exception as exc:
                detail["error"] = str(exc)
                return {
                    "status": "error",
                    "reason": "rename_error",
                    "detail": detail,
                }

        return await _run_book_backfill_engine(
            app,
            limit=limit,
            dry_run=dry_run,
            success_key="renamed",
            strategy=_strategy,
        )

    try:
        report = asyncio.run(_run())
    finally:
        out_path = _write_backfill_report(
            report,
            "BOOK_YEAR_BACKFILL_REPORT_PATH",
            "data/book_year_backfill_report.json",
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


@cli.command("analyze-genres")
@click.option("--suggest", is_flag=True, help="Sugerir grupos baseado na biblioteca")
@click.option("--library-path", type=click.Path(), help="Caminho da biblioteca")
def analyze_genres(suggest, library_path):
    """Analisa generos da biblioteca e sugere agrupamentos."""
    if not suggest:
        click.echo("Use --suggest para analisar a biblioteca")
        return

    config = Config()
    db_path = Path(library_path) if library_path else config.database_path

    try:
        with open(db_path, "r", encoding="utf-8") as f:
            db = json.load(f)

        genres = set()
        media_records = db.get("media", {})
        for item in media_records.values():
            metadata = item.get("metadata") or {}
            media_type = str(metadata.get("media_type") or "").lower()
            if media_type == "music":
                genre = metadata.get("genre")
                if genre:
                    for g in str(genre).split(","):
                        stripped = g.strip().lower()
                        if stripped:
                            genres.add(stripped)

        if not genres:
            click.echo("Nenhum genero encontrado na biblioteca")
            return

        from app.features.smart_playlists.expansion import GenreExpander
        expander = GenreExpander()

        groups = {}
        for genre in sorted(genres):
            parent = expander.infer_parent(genre)
            if parent:
                groups.setdefault(parent, []).append(genre)

        click.echo(f"\nAnalise de {len(genres)} generos unicos:\n")

        for parent, subgenres in sorted(groups.items(), key=lambda x: -len(x[1])):
            if len(subgenres) >= 3:
                click.echo(f"\n{parent.upper()} ({len(subgenres)} subgeneros):")
                for sub in sorted(subgenres)[:10]:
                    click.echo(f"  - {sub}")
                if len(subgenres) > 10:
                    click.echo(f"  ... e mais {len(subgenres) - 10}")

        grouped = set()
        for subs in groups.values():
            grouped.update(subs)
        ungrouped = genres - grouped

        if ungrouped:
            click.echo(f"\nGeneros nao agrupados ({len(ungrouped)}):")
            for g in sorted(ungrouped)[:10]:
                click.echo(f"  - {g}")
            if len(ungrouped) > 10:
                click.echo(f"  ... e mais {len(ungrouped) - 10}")

    except FileNotFoundError:
        click.echo(f"Banco de dados nao encontrado: {db_path}")
    except Exception as e:
        click.echo(f"Erro ao analisar: {e}")


if __name__ == "__main__":
    cli()
