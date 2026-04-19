#!/usr/bin/env python3
"""CLI Manager for Media Organization System."""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from app.config import Config
from app.logging.config import get_logger, log_error, set_console_log_level

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

    @staticmethod
    def _admin_backfill_enabled() -> bool:
        """Return True when admin-only menu entries should be visible."""
        return os.getenv("ENABLE_ADMIN_BACKFILL_MENU", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @staticmethod
    def _normalize_term(value: Any) -> str:
        return " ".join(str(value or "").strip().split())

    @staticmethod
    def _unique_preserve_order(items: List[str]) -> List[str]:
        return list(dict.fromkeys(item for item in items if str(item).strip()))

    def _load_catalog_payload(self, catalog_key: str) -> Dict[str, Any]:
        from app.features.genre_guard.core import (
            load_genre_exceptions_payload,
            load_invalid_catalog,
            load_musical_keywords_payload,
        )

        if catalog_key == "invalid":
            return load_invalid_catalog(force_reload=True)
        if catalog_key == "keywords":
            return load_musical_keywords_payload(force_reload=True)
        if catalog_key == "exceptions":
            return load_genre_exceptions_payload(force_reload=True)
        raise ValueError(f"Unknown catalog key: {catalog_key}")

    def _save_catalog_payload(self, catalog_key: str, payload: Dict[str, Any]) -> None:
        from app.features.genre_guard.core import (
            save_genre_exceptions_payload,
            save_invalid_catalog,
            save_musical_keywords_payload,
        )

        if catalog_key == "invalid":
            save_invalid_catalog(payload)
            return
        if catalog_key == "keywords":
            save_musical_keywords_payload(payload)
            return
        if catalog_key == "exceptions":
            save_genre_exceptions_payload(payload)
            return
        raise ValueError(f"Unknown catalog key: {catalog_key}")

    def _get_catalog_items(self, catalog_key: str, payload: Dict[str, Any]) -> List[str]:
        if catalog_key == "invalid":
            return list(payload.get("exact", []) or [])
        if catalog_key == "keywords":
            return list(payload.get("keywords", []) or [])
        if catalog_key == "exceptions":
            return list(payload.get("exceptions", []) or [])
        return []

    def _set_catalog_items(self, catalog_key: str, payload: Dict[str, Any], items: List[str]) -> Dict[str, Any]:
        if catalog_key == "invalid":
            payload["exact"] = self._unique_preserve_order(items)
            return payload
        if catalog_key == "keywords":
            payload["keywords"] = self._unique_preserve_order(items)
            return payload
        if catalog_key == "exceptions":
            payload["exceptions"] = self._unique_preserve_order(items)
            return payload
        return payload

    def _print_catalog_entries(self, title: str, entries: List[str]) -> None:
        console.print(f"\n[bold cyan]{title}[/bold cyan]")
        if not entries:
            console.print("[yellow]No entries found.[/yellow]")
            return

        for index, item in enumerate(entries, 1):
            console.print(f"  [bold cyan][{index}][/bold cyan] {item}")

    def _sort_invalid_catalog_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        exact = self._unique_preserve_order(
            [str(item).strip()
             for item in payload.get("exact", []) if str(item).strip()]
        )
        regex = self._unique_preserve_order(
            [str(item).strip()
             for item in payload.get("regex", []) if str(item).strip()]
        )
        payload["exact"] = sorted(exact)
        payload["regex"] = sorted(regex)
        return payload

    def show_genre_catalogs_menu(self):
        while True:
            console.print("\n[bold cyan]Genre Catalog Management[/bold cyan]")
            console.print("[bold]Select a catalog:[/bold]\n")

            options = {
                "1": "Invalid music genres",
                "2": "Musical keywords",
                "3": "Genre exceptions",
                "4": "Return to previous menu",
            }

            for key, value in options.items():
                console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            choice = Prompt.ask(
                "\n[bold]Your choice[/bold]", choices=list(options.keys()), default="4")

            if choice == "4":
                break
            if choice == "1":
                self.show_invalid_genres_menu()
            elif choice == "2":
                self.show_simple_catalog_menu(
                    catalog_key="keywords",
                    title="Musical Keywords",
                    entry_label="keyword",
                    list_label="keywords",
                )
            elif choice == "3":
                self.show_simple_catalog_menu(
                    catalog_key="exceptions",
                    title="Genre Exceptions",
                    entry_label="exception",
                    list_label="exceptions",
                )

    def show_invalid_genres_menu(self):
        from app.features.genre_guard.core import _canonical_genre_key

        while True:
            console.print("\n[bold cyan]Invalid Music Genres[/bold cyan]")
            console.print("[bold]Select an operation:[/bold]\n")

            options = {
                "1": "List catalog",
                "2": "Add exact invalid genre",
                "3": "Add regex pattern",
                "4": "Remove exact invalid genre",
                "5": "Remove regex pattern",
                "6": "Return to catalog menu",
            }

            for key, value in options.items():
                console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            choice = Prompt.ask(
                "\n[bold]Your choice[/bold]", choices=list(options.keys()), default="6")

            if choice == "6":
                break

            payload = self._load_catalog_payload("invalid")
            payload = self._sort_invalid_catalog_payload(payload)

            if choice == "1":
                self._print_catalog_entries(
                    "Exact invalid genres", list(payload.get("exact", []) or []))
                self._print_catalog_entries(
                    "Regex invalid patterns", list(payload.get("regex", []) or []))
                auto_added = payload.get("auto_added", {}) or {}
                console.print(
                    f"\n[dim]Auto-added entries: {len(auto_added)}[/dim]")
                continue

            if choice in {"2", "3"}:
                raw_value = Prompt.ask(
                    "Enter value to add",
                    default="",
                ).strip()
                if not raw_value:
                    console.print("[yellow]No value provided.[/yellow]")
                    continue

                if choice == "2":
                    normalized = _canonical_genre_key(raw_value)
                    target_list = list(payload.get("exact", []) or [])
                    if normalized in {_canonical_genre_key(item) for item in target_list}:
                        console.print(
                            "[yellow]Exact term already exists.[/yellow]")
                        continue
                    target_list.append(normalized)
                    payload["exact"] = sorted(
                        self._unique_preserve_order(target_list))
                else:
                    normalized = self._normalize_term(raw_value)
                    target_list = list(payload.get("regex", []) or [])
                    if normalized in target_list:
                        console.print(
                            "[yellow]Regex pattern already exists.[/yellow]")
                        continue
                    target_list.append(normalized)
                    payload["regex"] = sorted(
                        self._unique_preserve_order(target_list))

                self._save_catalog_payload("invalid", payload)
                console.print("[green]Catalog updated.[/green]")
                continue

            if choice in {"4", "5"}:
                field_name = "exact" if choice == "4" else "regex"
                items = list(payload.get(field_name, []) or [])
                if not items:
                    console.print("[yellow]No entries to remove.[/yellow]")
                    continue

                self._print_catalog_entries(
                    f"Current {field_name} entries", items)
                raw_index = Prompt.ask(
                    "Enter item number to remove", default="")
                try:
                    index = int(raw_index)
                except ValueError:
                    console.print("[red]Invalid selection.[/red]")
                    continue

                if index < 1 or index > len(items):
                    console.print("[red]Selection out of range.[/red]")
                    continue

                removed_item = items.pop(index - 1)
                payload[field_name] = self._unique_preserve_order(items)
                if field_name == "exact":
                    auto_added = payload.get("auto_added", {}) or {}
                    auto_added.pop(_canonical_genre_key(removed_item), None)
                    payload["auto_added"] = auto_added

                self._save_catalog_payload("invalid", payload)
                console.print(f"[green]Removed: {removed_item}[/green]")

    def show_simple_catalog_menu(self, catalog_key: str, title: str, entry_label: str, list_label: str):
        while True:
            console.print(f"\n[bold cyan]{title}[/bold cyan]")
            console.print("[bold]Select an operation:[/bold]\n")

            options = {
                "1": f"List {list_label}",
                "2": f"Add {entry_label}",
                "3": f"Remove {entry_label}",
                "4": "Return to catalog menu",
            }

            for key, value in options.items():
                console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            choice = Prompt.ask(
                "\n[bold]Your choice[/bold]", choices=list(options.keys()), default="4")

            if choice == "4":
                break

            payload = self._load_catalog_payload(catalog_key)
            items = self._get_catalog_items(catalog_key, payload)

            if choice == "1":
                self._print_catalog_entries(f"Current {list_label}", items)
                continue

            if choice == "2":
                raw_value = Prompt.ask(
                    f"Enter {entry_label} to add", default="").strip()
                if not raw_value:
                    console.print("[yellow]No value provided.[/yellow]")
                    continue

                normalized = self._normalize_term(raw_value)
                existing_lower = {str(item).strip().casefold()
                                  for item in items}
                if normalized.casefold() in existing_lower:
                    console.print("[yellow]Entry already exists.[/yellow]")
                    continue

                items.append(normalized)
                payload = self._set_catalog_items(catalog_key, payload, items)
                self._save_catalog_payload(catalog_key, payload)
                console.print("[green]Catalog updated.[/green]")
                continue

            if choice == "3":
                if not items:
                    console.print("[yellow]No entries to remove.[/yellow]")
                    continue

                self._print_catalog_entries(f"Current {list_label}", items)
                raw_index = Prompt.ask(
                    "Enter item number to remove", default="")
                try:
                    index = int(raw_index)
                except ValueError:
                    console.print("[red]Invalid selection.[/red]")
                    continue

                if index < 1 or index > len(items):
                    console.print("[red]Selection out of range.[/red]")
                    continue

                removed_item = items.pop(index - 1)
                payload = self._set_catalog_items(catalog_key, payload, items)
                self._save_catalog_payload(catalog_key, payload)
                console.print(f"[green]Removed: {removed_item}[/green]")

    def show_interactive_menu(self):
        while True:
            console.print("\n[bold cyan]Media Organizer System[/bold cyan]")
            console.print("[bold]Select an operation:[/bold]\n")

            admin_backfill_visible = self._admin_backfill_enabled()

            options = {
                "1": "Organize media files",
                "2": "Filename suggestions",
                "3": "System information",
                "4": "Genre catalog management",
                "5": "Comic Vine backfill",
                "6": "Exit",
            }
            if admin_backfill_visible:
                options["9"] = "[Admin] Music genre backfill"

            for key, value in options.items():
                console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            choice = Prompt.ask(
                "\n[bold]Your choice[/bold]", choices=list(options.keys()), default="6")

            if choice == "1":
                self.show_organize_menu()
            elif choice == "2":
                self.show_filename_suggestions_menu()
            elif choice == "3":
                self.show_system_info_menu()
            elif choice == "4":
                self.show_genre_catalogs_menu()
            elif choice == "5":
                self.show_comic_vine_backfill_menu()
            elif choice == "6":
                break
            elif choice == "9" and admin_backfill_visible:
                self.show_music_backfill_menu()

    def show_quality_dashboard_interactive(self):
        """Generate and display music quality dashboard metrics."""
        from app.features.quality_monitor import MusicQualityMonitor

        console.print("\n[bold cyan]Music Quality Dashboard[/bold cyan]")
        top_n = int(Prompt.ask(
            "Top genres to display",
            default=str(self.config.quality_dashboard_top_n_default),
        ))

        try:
            monitor = MusicQualityMonitor(
                data_dir=self.data_dir,
                organization_path=self.config.database_path,
                link_registry_path=self.config.link_registry_path,
            )
            report = monitor.generate_report(top_n=max(1, top_n))

            metrics = report.get("metrics", {})
            table = Table(title="Music Quality Metrics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Total tracks", str(metrics.get("total_tracks", 0)))
            table.add_row("Tracks with genre", str(
                metrics.get("tracks_with_genre", 0)))
            table.add_row("Tracks missing genre", str(
                metrics.get("tracks_missing_genre", 0)))
            table.add_row("Genre completeness",
                          f"{metrics.get('genre_completeness', 0.0):.2f}%")
            table.add_row("Multi-genre tracks",
                          str(metrics.get("multi_genre_tracks", 0)))
            table.add_row("Playlist-like tokens",
                          str(metrics.get("playlist_like_tokens", 0)))
            table.add_row("Genre equals folder", str(
                metrics.get("genre_equal_folder", 0)))
            table.add_row("Avg tag quality score",
                          f"{metrics.get('avg_tag_quality_score', 0.0):.2f}")
            table.add_row("Registry music records", str(
                metrics.get("registry_music_records", 0)))
            console.print(table)

            top_table = Table(title="Top Genres")
            top_table.add_column("#", style="cyan")
            top_table.add_column("Genre", style="white")
            top_table.add_column("Count", style="green")
            for index, row in enumerate(report.get("top_genres", []), 1):
                genre, count = row
                top_table.add_row(str(index), str(genre), str(count))
            console.print(top_table)

            save_choice = Prompt.ask(
                "Save quality report to file?",
                choices=["y", "n"],
                default="y",
            )
            if save_choice.lower() == "y":
                default_output = self.data_dir / "quality_report_latest.json"
                output_input = Prompt.ask(
                    "Output report path",
                    default=str(default_output),
                )
                output_path = monitor.save_report(report, Path(output_input))
                console.print(f"Report saved: {output_path}", style="green")

        except Exception as exc:
            log_error(
                self.logger, f"Error generating quality dashboard: {exc}")
            console.print(f"[red]Error generating dashboard: {exc}[/red]")

    def show_genre_quality_report(self):
        """Generate and display detailed genre quality report."""
        from app.features.quality_monitor import MusicQualityMonitor

        console.print(
            "\n[bold cyan]Genre Quality Report (Detailed)[/bold cyan]")

        try:
            monitor = MusicQualityMonitor(
                data_dir=self.data_dir,
                organization_path=self.config.database_path,
                link_registry_path=self.config.link_registry_path,
            )
            report = monitor.generate_genre_quality_report()

            # Summary table
            summary = report.get("summary", {})
            summary_table = Table(title="Genre Summary")
            summary_table.add_column("Metric", style="cyan")
            summary_table.add_column("Value", style="green")
            summary_table.add_row("Total tracks analyzed", str(
                summary.get("total_tracks_analyzed", 0)))
            summary_table.add_row("Unique genres found", str(
                summary.get("unique_genres_found", 0)))
            summary_table.add_row("Total genre occurrences", str(
                summary.get("total_genre_occurrences", 0)))
            summary_table.add_row("Valid genres", str(
                summary.get("valid_genres_count", 0)))
            summary_table.add_row("Invalid genres", str(
                summary.get("invalid_genres_count", 0)))
            summary_table.add_row("Suspicious genres", str(
                summary.get("suspicious_genres_count", 0)))
            summary_table.add_row("Whitelisted genres", str(
                summary.get("whitelisted_genres_count", 0)))
            console.print(summary_table)

            # Coverage table
            coverage = report.get("coverage", {})
            coverage_table = Table(title="Genre Coverage")
            coverage_table.add_column("Metric", style="cyan")
            coverage_table.add_column("Value", style="green")
            coverage_table.add_row("Valid occurrences", str(
                coverage.get("valid_occurrences", 0)))
            coverage_table.add_row("Invalid occurrences", str(
                coverage.get("invalid_occurrences", 0)))
            coverage_table.add_row(
                "Valid percentage", f"{coverage.get('valid_percentage', 0.0):.2f}%")
            coverage_table.add_row(
                "Invalid percentage", f"{coverage.get('invalid_percentage', 0.0):.2f}%")
            console.print(coverage_table)

            # Top genres
            top_genres = report.get("top_genres", [])
            if top_genres:
                top_table = Table(title="Top 20 Genres")
                top_table.add_column("#", style="cyan")
                top_table.add_column("Genre", style="white")
                top_table.add_column("Count", style="green")
                for index, (genre, count) in enumerate(top_genres[:20], 1):
                    top_table.add_row(str(index), str(genre), str(count))
                console.print(top_table)

            # Potential false positives
            false_positives = report.get("potential_false_positives", [])
            if false_positives:
                fp_table = Table(title="Potential False Positives")
                fp_table.add_column("Genre", style="yellow")
                fp_table.add_column("Occurrences", style="green")
                for fp in false_positives[:10]:
                    fp_table.add_row(str(fp.get("genre", "")),
                                     str(fp.get("occurrences", 0)))
                console.print(fp_table)
                if len(false_positives) > 10:
                    console.print(
                        f"  ... and {len(false_positives) - 10} more", style="yellow")

            # Catalog status
            catalog = report.get("catalog_status", {})
            catalog_table = Table(title="Catalog Status")
            catalog_table.add_column("Catalog", style="cyan")
            catalog_table.add_column("Size", style="green")
            catalog_table.add_row("Invalid catalog", str(
                catalog.get("invalid_catalog_size", 0)))
            catalog_table.add_row("Suspect catalog", str(
                catalog.get("suspect_catalog_size", 0)))
            catalog_table.add_row("Genre exceptions", str(
                catalog.get("genre_exceptions_size", 0)))
            catalog_table.add_row("Musical keywords", str(
                catalog.get("musical_keywords_size", 0)))
            console.print(catalog_table)

            # Recommendations
            recommendations = report.get("recommendations", [])
            if recommendations:
                console.print("\n[bold]Recommendations:[/bold]")
                for rec in recommendations:
                    priority = rec.get("priority", "LOW")
                    issue = rec.get("issue", "")
                    action = rec.get("action", "")
                    priority_style = "red" if priority == "HIGH" else (
                        "yellow" if priority == "MEDIUM" else "green")
                    console.print(
                        f"  [{priority_style}]{priority}[/{priority_style}]: {issue}")
                    console.print(f"    → {action}", style="dim")

            # Save report
            save_choice = Prompt.ask(
                "\nSave genre quality report to file?",
                choices=["y", "n"],
                default="y",
            )
            if save_choice.lower() == "y":
                default_output = self.data_dir / "genre_quality_report_latest.json"
                output_input = Prompt.ask(
                    "Output report path",
                    default=str(default_output),
                )
                output_path = monitor.save_genre_quality_report(
                    report, Path(output_input))
                console.print(f"Report saved: {output_path}", style="green")

        except Exception as exc:
            log_error(
                self.logger, f"Error generating genre quality report: {exc}")
            console.print(f"[red]Error generating report: {exc}[/red]")

    def show_filename_suggestions_menu(self):
        from app.features.filename_suggestions import FilenameSuggestionEngine, iter_preview_lines

        engine = FilenameSuggestionEngine()

        while True:
            console.print("\n[bold cyan]Filename Suggestions[/bold cyan]")
            console.print("[bold]Select an operation:[/bold]\n")

            options = {
                "1": "Generate suggestions report",
                "2": "Preview report",
                "3": "Apply report (dry-run)",
                "4": "Apply report (execute)",
                "5": "Manual correction (edit by index)",
                "6": "Return to main menu",
            }

            for key, value in options.items():
                console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            choice = Prompt.ask(
                "\n[bold]Your choice[/bold]", choices=list(options.keys()), default="6")

            if choice == "6":
                break

            if choice == "1":
                books_path = getattr(self.config, "download_path_books", None)
                if isinstance(books_path, Path):
                    root_default = str(books_path.parent)
                else:
                    root_default = str(Path.cwd())
                root_input = Prompt.ask(
                    "Root directory",
                    default=root_default,
                )
                root_path = Path(root_input)
                if not root_path.exists() or not root_path.is_dir():
                    console.print(f"[red]Invalid directory: {root_path}[/red]")
                    continue

                media_filter = Prompt.ask(
                    "Media filter",
                    choices=["all", "books", "comics"],
                    default="all",
                )
                output_input = Prompt.ask(
                    "Output report path",
                    default=os.getenv(
                        "FILENAME_SUGGESTIONS_REPORT_PATH",
                        "data/filename_suggestions_report.json",
                    ),
                )
                output_path = Path(output_input)
                preview_limit = int(Prompt.ask(
                    "Preview lines",
                    default=str(self.config.filename_preview_limit_default),
                ))

                report = engine.suggest_for_root(
                    root_path=root_path,
                    media_filter=media_filter,
                )
                engine.save_report(report, output_path)

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
                continue

            report_input = Prompt.ask(
                "Report path",
                default=os.getenv(
                    "FILENAME_SUGGESTIONS_REPORT_PATH",
                    "data/filename_suggestions_report.json",
                ),
            )
            report_path = Path(report_input)
            if not report_path.exists() or not report_path.is_file():
                console.print(f"[red]Report not found: {report_path}[/red]")
                continue

            if choice == "2":
                report = engine.load_report(report_path)
                preview_limit = int(Prompt.ask(
                    "Preview lines",
                    default=str(self.config.filename_preview_limit_default),
                ))
                for line in iter_preview_lines(report, limit=max(0, preview_limit)):
                    console.print(line)
                continue

            if choice == "5":
                report = engine.load_report(report_path)
                only_changed = Prompt.ask(
                    "Show only changed suggestions?",
                    choices=["y", "n"],
                    default="y",
                )
                rows = engine.list_report_items(
                    report,
                    only_changed=(only_changed == "y"),
                )

                if not rows:
                    console.print(
                        "[yellow]No suggestions available for manual correction.[/yellow]")
                    continue

                preview_limit = int(Prompt.ask(
                    "Preview lines",
                    default=str(self.config.filename_preview_limit_default),
                ))
                for row in rows[:max(0, preview_limit)]:
                    console.print(
                        (
                            f"[{row['index']}] [{row['media_type']}|{row['confidence']}] "
                            f"{row['original_name']} => {row['suggested_name']}"
                        )
                    )

                index = int(Prompt.ask("Suggestion index to edit"))
                new_name = Prompt.ask("New suggested name")

                try:
                    updated = engine.update_report_suggestion(
                        report=report,
                        index=index,
                        new_name=new_name,
                    )
                except (IndexError, ValueError) as exc:
                    console.print(
                        f"[red]Invalid manual correction: {exc}[/red]")
                    continue

                learned = engine.learn_from_report(updated, only_manual=True)

                save_path = Prompt.ask(
                    "Save updated report path",
                    default=str(report_path),
                )
                out = Path(save_path)
                engine.save_report(updated, out)
                console.print(
                    (
                        f"Suggestion updated | changed={updated['changed_suggestions']} | "
                        f"unchanged={updated['unchanged_suggestions']}"
                    ),
                    style="green",
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
                console.print(f"Report: {out}", style="green")
                continue

            execute = choice == "4"
            report = engine.load_report(report_path)
            result = engine.apply_report(report=report, dry_run=not execute)

            apply_output = Path(os.getenv(
                "FILENAME_SUGGESTIONS_APPLY_REPORT_PATH",
                "data/filename_suggestions_apply_report.json",
            ))
            apply_output.parent.mkdir(parents=True, exist_ok=True)
            apply_output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            mode = "EXECUTE" if execute else "DRY-RUN"
            console.print(
                (
                    f"Apply suggestions ({mode}) | processed={result['processed']} | "
                    f"renamed={result['renamed']} | skipped={result['skipped']} | errors={result['errors']}"
                ),
                style="cyan",
            )
            console.print(f"Report: {apply_output}", style="green")

            preview_limit = int(Prompt.ask(
                "Preview lines",
                default=str(self.config.filename_preview_limit_default),
            ))
            for item in result.get("details", [])[:max(0, preview_limit)]:
                old = item.get("original_path", "")
                new = item.get("target_path", item.get("suggested_name", ""))
                status = item.get("status", "")
                console.print(f"[{status}] {old} => {new}")

    def show_system_info_menu(self):
        while True:
            console.print("\n[bold cyan]System Information[/bold cyan]")
            console.print("[bold]Select an operation:[/bold]\n")

            options = {
                "1": "View system status",
                "2": "View unorganized files",
                "3": "View organization logs",
                "4": "View statistics",
                "5": "Music quality dashboard",
                "6": "Genre quality report (detailed)",
                "7": "Return to main menu",
            }

            for key, value in options.items():
                console.print(f"  [bold cyan][{key}][/bold cyan]  {value}")

            choice = Prompt.ask(
                "\n[bold]Your choice[/bold]", choices=list(options.keys()), default="7")

            if choice == "1":
                self.show_status_interactive()
            elif choice == "2":
                self.view_unorganized_interactive()
            elif choice == "3":
                self.view_logs_interactive()
            elif choice == "4":
                self.view_stats_interactive()
            elif choice == "5":
                self.show_quality_dashboard_interactive()
            elif choice == "6":
                self.show_genre_quality_report()
            elif choice == "7":
                break

    def show_organize_menu(self):
        from app.main import MediaOrganizerApp

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

    def show_music_backfill_menu(self):
        """Interactive menu for music genre backfill."""
        from app.infrastructure.database import OrganizationDatabase
        from app.services.organizers import MusicOrganizer

        console.print("\n[bold cyan]Music Genre Backfill[/bold cyan]")
        console.print(
            "[bold yellow]This will enrich genre metadata for all organized music tracks[/bold yellow]")
        console.print(
            "[bold yellow]using improved MusicBrainz/Last.fm lookup[/bold yellow]\n")

        # Step 1: Dry-run first
        console.print("[cyan]Step 1: Dry-run preview (no changes)[/cyan]")
        dry_run_choice = Prompt.ask(
            "Run dry-run preview first?",
            choices=["y", "n"],
            default="y"
        )

        if dry_run_choice.lower() == "y":
            console.print("\n[cyan]Scanning organized music library...[/cyan]")
            set_console_log_level(logging.INFO)

            try:
                database = OrganizationDatabase(self.config.database_path)
                music_organizer = MusicOrganizer(
                    config=self.config,
                    database=database,
                    conflict_handler=None,
                    logger=self.logger,
                    dry_run=True,
                )

                report = asyncio.run(
                    music_organizer.backfill_music_genres(dry_run=True))

                self._display_backfill_report(report)

            except Exception as exc:
                console.print(f"[red]Error during dry-run: {exc}[/red]")
                return
            finally:
                set_console_log_level(logging.WARNING)

        # Step 2: Ask for confirmation to execute
        console.print("\n[cyan]Step 2: Execute backfill[/cyan]")
        execute_choice = Prompt.ask(
            "Execute genre backfill?",
            choices=["y", "n"],
            default="n"
        )

        if execute_choice.lower() != "y":
            console.print("[yellow]Backfill cancelled[/yellow]")
            return

        console.print("\n[cyan]Executing genre backfill...[/cyan]")
        set_console_log_level(logging.INFO)

        try:
            database = OrganizationDatabase(self.config.database_path)
            music_organizer = MusicOrganizer(
                config=self.config,
                database=database,
                conflict_handler=None,
                logger=self.logger,
                dry_run=False,
            )

            report = asyncio.run(
                music_organizer.backfill_music_genres(dry_run=False))

            console.print("\n[bold green]Backfill completed![/bold green]")
            self._display_backfill_report(report)

        except Exception as exc:
            console.print(f"[red]Error during backfill: {exc}[/red]")
        finally:
            set_console_log_level(logging.WARNING)

    def show_comic_vine_backfill_menu(self):
        """Backfill comic metadata using Comic Vine API."""
        from app.services import BookOrganizer

        console.print("\n[bold cyan]🔍 Comic Vine Backfill[/bold cyan]")

        if not self.config.comic_vine_enabled:
            console.print(
                "[yellow]COMIC_VINE_API_KEY not configured.[/yellow]")
            console.print("[dim]Set COMIC_VINE_API_KEY in .env to enable.[/dim]")
            return

        if not self.config.comic_vine_api_key:
            console.print(
                "[yellow]COMIC_VINE_API_KEY is empty.[/yellow]")
            return

        console.print(f"[green]Comic Vine enrichment enabled.[/green]")
        console.print(f"API Key: {self.config.comic_vine_api_key[:8]}...")
        console.print(f"Translate PT→EN: {self.config.comic_vine_translate_series_names}")
        console.print(f"Rate limit: {self.config.comic_vine_api_delay_seconds}s/request")
        console.print(f"Timeout: {self.config.comic_vine_timeout_seconds}s")
        console.print(f"Min match score: {self.config.comic_vine_min_match_score}")
        console.print(f"Download covers: {self.config.comic_vine_download_covers}")

        console.print("\n[dim]Comic Vine backfill is automatic during media organization.[/dim]")
        console.print("[dim]To backfill existing comics, run organization with --force flag.[/dim]")

    def _display_backfill_report(self, report: Dict) -> None:
        """Display backfill report in a readable format."""
        console.print("\n[bold cyan]Backfill Report[/bold cyan]")
        console.print(
            f"Total tracks processed: {report['total_tracks_processed']}")
        console.print(
            f"Enriched from MusicBrainz: {report['tracks_enriched_from_musicbrainz']}")
        console.print(
            f"Enriched from Last.fm: {report['tracks_enriched_from_lastfm']}")
        console.print(
            f"Already had genre: {report['tracks_skipped_already_has_genre']}")
        console.print(
            f"No genre found: {report['tracks_with_no_genre_found']}")
        console.print(f"Errors: {report['tracks_with_file_errors']}")

        if report.get("dry_run"):
            console.print("[yellow]DRY RUN[/yellow]")

        # Show sample of enriched tracks
        if report.get("enriched_tracks"):
            console.print("\n[cyan]Sample enriched tracks (first 10):[/cyan]")
            for track in report["enriched_tracks"][:10]:
                source_color = "green" if track["source"] == "musicbrainz" else "yellow"
                console.print(
                    f"  [{source_color}]{track['source'].upper()}[/{source_color}] "
                    f"{track['file']}: {track['genre']}"
                )

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
        from app.infrastructure.database import UnorganizedDatabase

        console.print("\n[bold cyan]Unorganized Files[/bold cyan]")

        try:
            unorganized_db = UnorganizedDatabase(
                Path(os.getenv("UNORGANIZED_DB_PATH", "data/unorganized.json"))
            )
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
        from app.main import MediaOrganizerApp

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
