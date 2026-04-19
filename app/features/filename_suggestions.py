"""Filename suggestion engine for books and comics."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.core import MediaType
from app.core.detection import MediaClassifier
from app.config.constants import BOOK_EXTS, COMIC_EXTS
from app.utils.helpers import parse_book_filename_fields, parse_comic_filename_fields


@dataclass
class FilenameSuggestion:
    original_path: str
    media_type: str
    original_name: str
    suggested_name: str
    confidence: str
    reason: str
    changed: bool


class FilenameSuggestionEngine:
    """Generate safe filename suggestions for books and comics recursively."""

    def __init__(
        self,
        classifier: Optional[MediaClassifier] = None,
        learning_path: Optional[Path] = None,
    ):
        self.classifier = classifier or MediaClassifier()
        self.learning_path = learning_path or Path(
            "data/filename_suggestion_learning.json")
        self.learning_data = self._load_learning_data()
        # Cache para normalization (melhoria de performance)
        self._normalize_cache: Dict[str, str] = {}

    def suggest_for_root(
        self,
        root_path: Path,
        media_filter: str = "all",
    ) -> Dict[str, Any]:
        # Limite de scan configurável para evitar travamento em grandes diretórios
        MAX_FILES_DEFAULT = 50000
        max_files = min(int(os.getenv(
            "FILENAME_SUGGESTIONS_MAX_SCAN", MAX_FILES_DEFAULT)), MAX_FILES_DEFAULT)

        files = []
        scanned_total = 0
        for file_path in sorted(root_path.rglob("*")):
            if file_path.is_file():
                files.append(file_path)
                scanned_total += 1
                if len(files) >= max_files:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Suggestion scan reached limit of {max_files} files. "
                        f"Some files may not be included. Use FILENAME_SUGGESTIONS_MAX_SCAN to adjust."
                    )
                    break

        suggestions: List[FilenameSuggestion] = []

        for file_path in files:
            media_type = self.classifier.classificar_tipo_midia(file_path)

            if media_filter == "books" and media_type != MediaType.BOOK:
                continue
            if media_filter == "comics" and media_type != MediaType.COMIC:
                continue
            if media_filter == "all" and media_type not in {MediaType.BOOK, MediaType.COMIC}:
                continue

            suggestion = self._suggest_for_file(file_path, media_type)
            suggestions.append(suggestion)

        changed_count = sum(1 for s in suggestions if s.changed)
        report = {
            "root": str(root_path),
            "media_filter": media_filter,
            "total_files_scanned": scanned_total,
            "matched_media_files": len(suggestions),
            "total_suggestions": len(suggestions),
            "changed_suggestions": changed_count,
            "unchanged_suggestions": len(suggestions) - changed_count,
            "has_changes": changed_count > 0,
        }

        if changed_count > 0:
            report["suggestions"] = [asdict(item) for item in suggestions]
            report["summary_only"] = False
        else:
            report["suggestions"] = []
            report["summary_only"] = True

        return report

    def save_report(self, report: Dict[str, Any], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def learn_from_report(self, report: Dict[str, Any], only_manual: bool = True) -> Dict[str, int]:
        entries = report.get("suggestions") or []
        learned_exact = 0
        learned_comic_alias = 0
        learned_book_alias = 0

        for item in entries:
            if only_manual and not bool(item.get("manual_override", False)):
                continue

            result = self._learn_from_suggestion_item(item)
            learned_exact += result["exact"]
            learned_comic_alias += result["comic_alias"]
            learned_book_alias += result["book_alias"]

        self._save_learning_data()
        return {
            "exact_overrides": learned_exact,
            "comic_series_aliases": learned_comic_alias,
            "book_author_aliases": learned_book_alias,
        }

    def load_report(self, report_path: Path) -> Dict[str, Any]:
        return json.loads(report_path.read_text(encoding="utf-8"))

    def update_report_suggestion(
        self,
        report: Dict[str, Any],
        index: int,
        new_name: str,
    ) -> Dict[str, Any]:
        entries = report.get("suggestions") or []
        if index < 0 or index >= len(entries):
            raise IndexError("suggestion index out of range")

        item = entries[index]
        original_name = str(item.get("original_name") or "").strip()
        suggested_name = str(new_name or "").strip()

        if not suggested_name:
            raise ValueError("new suggested name cannot be empty")

        # Validação de path traversal (CRÍTICO - segurança)
        invalid_path_chars = {'..', '/', '\\', '\x00'}
        if any(char in suggested_name for char in invalid_path_chars):
            raise ValueError(
                "suggested name must be a simple filename (no path separators or path traversal)"
            )

        # Não permitir nome vazio ou só pontos
        if suggested_name == "." or not suggested_name.strip("."):
            raise ValueError("suggested name cannot be empty or only dots")

        original_ext = Path(original_name).suffix.lower()
        suggested_ext = Path(suggested_name).suffix.lower()
        if original_ext and suggested_ext != original_ext:
            raise ValueError(
                f"new suggested name must keep original extension ({original_ext})"
            )

        previous = str(item.get("suggested_name") or "")
        item["suggested_name"] = suggested_name
        item["changed"] = suggested_name != original_name
        item["confidence"] = "manual"
        item["reason"] = "manual_override"
        item["manual_override"] = True
        item["previous_suggested_name"] = previous

        self._refresh_report_counters(report)
        return report

    def list_report_items(
        self,
        report: Dict[str, Any],
        only_changed: bool = False,
    ) -> List[Dict[str, Any]]:
        entries = report.get("suggestions") or []
        rows: List[Dict[str, Any]] = []
        for idx, item in enumerate(entries):
            changed = bool(item.get("changed", False))
            if only_changed and not changed:
                continue
            rows.append(
                {
                    "index": idx,
                    "original_name": str(item.get("original_name") or ""),
                    "suggested_name": str(item.get("suggested_name") or ""),
                    "media_type": str(item.get("media_type") or ""),
                    "confidence": str(item.get("confidence") or ""),
                    "changed": changed,
                }
            )
        return rows

    def _refresh_report_counters(self, report: Dict[str, Any]) -> None:
        entries = report.get("suggestions") or []
        changed_count = sum(1 for item in entries if bool(
            item.get("changed", False)))
        report["total_suggestions"] = len(entries)
        report["changed_suggestions"] = changed_count
        report["unchanged_suggestions"] = len(entries) - changed_count

    def apply_report(self, report: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
        entries = report.get("suggestions") or []
        result = {
            "dry_run": dry_run,
            "processed": 0,
            "renamed": 0,
            "skipped": 0,
            "errors": 0,
            "details": [],
        }

        for item in entries:
            result["processed"] += 1

            original_path = Path(str(item.get("original_path") or ""))
            suggested_name = str(item.get("suggested_name") or "").strip()
            changed = bool(item.get("changed", False))

            detail = {
                "original_path": str(original_path),
                "suggested_name": suggested_name,
                "status": "",
            }

            if not changed:
                detail["status"] = "unchanged"
                result["skipped"] += 1
                result["details"].append(detail)
                continue

            if not original_path.exists() or not original_path.is_file():
                detail["status"] = "source_not_found"
                result["errors"] += 1
                result["details"].append(detail)
                continue

            if not suggested_name:
                detail["status"] = "empty_suggested_name"
                result["errors"] += 1
                result["details"].append(detail)
                continue

            target_path = original_path.with_name(suggested_name)
            detail["target_path"] = str(target_path)

            if target_path == original_path:
                detail["status"] = "same_name"
                result["skipped"] += 1
                result["details"].append(detail)
                continue

            if target_path.exists():
                detail["status"] = "target_exists"
                result["errors"] += 1
                result["details"].append(detail)
                continue

            if dry_run:
                detail["status"] = "would_rename"
                result["renamed"] += 1
                result["details"].append(detail)
                continue

            # Aplicar rename com tratamento robusto de erro (CRÍTICO - race conditions)
            try:
                # Double-check antes de rename (importante em multi-processo)
                if not original_path.exists():
                    detail["status"] = "source_disappeared"
                    result["errors"] += 1
                    result["details"].append(detail)
                    continue

                if target_path.exists():
                    detail["status"] = "target_collision"
                    result["errors"] += 1
                    result["details"].append(detail)
                    continue

                original_path.rename(target_path)
                detail["status"] = "renamed"
                result["renamed"] += 1
                result["details"].append(detail)

            except FileExistsError:
                detail["status"] = "target_collision_race"
                result["errors"] += 1
                result["details"].append(detail)
            except FileNotFoundError:
                detail["status"] = "source_disappeared_race"
                result["errors"] += 1
                result["details"].append(detail)
            except PermissionError:
                detail["status"] = "permission_denied"
                detail["error"] = "Insufficient permissions to rename file"
                result["errors"] += 1
                result["details"].append(detail)
            except OSError as exc:
                detail["status"] = "os_error"
                detail["error"] = f"{exc.strerror} (errno: {exc.errno if hasattr(exc, 'errno') else 'unknown'})"
                result["errors"] += 1
                result["details"].append(detail)
            except Exception as exc:
                detail["status"] = "rename_error"
                detail["error"] = str(exc)
                result["errors"] += 1
                result["details"].append(detail)

        return result

    def _suggest_for_file(self, file_path: Path, media_type: MediaType) -> FilenameSuggestion:
        if media_type == MediaType.BOOK:
            return self._suggest_book_filename(file_path)
        if media_type == MediaType.COMIC:
            return self._suggest_comic_filename(file_path)

        # This branch should be unreachable due to filtering.
        return FilenameSuggestion(
            original_path=str(file_path),
            media_type=media_type.name,
            original_name=file_path.name,
            suggested_name=file_path.name,
            confidence="low",
            reason="unsupported_media_type",
            changed=False,
        )

    def _suggest_book_filename(self, file_path: Path) -> FilenameSuggestion:
        exact_override = self._get_exact_override(file_path.name)
        if exact_override:
            return FilenameSuggestion(
                original_path=str(file_path),
                media_type=MediaType.BOOK.name,
                original_name=file_path.name,
                suggested_name=exact_override,
                confidence="manual",
                reason="learned_exact_override",
                changed=(file_path.name != exact_override),
            )

        stem = file_path.stem
        ext = file_path.suffix.lower()

        already_valid = parse_book_filename_fields(stem)
        if already_valid.get("is_valid"):
            canonical_author = str(already_valid.get("author") or "").strip()
            canonical_title = str(already_valid.get("title") or "").strip()
            canonical_year = already_valid.get("year")
            if canonical_author and canonical_author != "Unknown Author":
                canonical_name = f"{canonical_author} - {canonical_title} ({canonical_year}){ext}"
            else:
                canonical_name = f"{canonical_title} ({canonical_year}){ext}"
            return FilenameSuggestion(
                original_path=str(file_path),
                media_type=MediaType.BOOK.name,
                original_name=file_path.name,
                suggested_name=canonical_name,
                confidence="high",
                reason="book_schema_valid",
                changed=(file_path.name != canonical_name),
            )

        normalized = re.sub(r"\s+", " ", stem.replace("_", " ")).strip()
        year = self._extract_year(normalized)
        clean_stem = re.sub(
            r"\s*\((?:19|20)\d{2}\)\s*$", "", normalized).strip()

        author, title = self._extract_book_author_title(clean_stem)

        if author:
            author = self._apply_book_author_alias(author)

        if author and title:
            if year is not None:
                suggested = f"{author} - {title} ({year}){ext}"
                confidence = "high"
                reason = "author_title_year_extracted"
            else:
                suggested = file_path.name
                confidence = "low"
                reason = "book_schema_missing_year"
        else:
            title_fallback = self._sanitize_name(clean_stem or stem)
            if year is not None:
                suggested = f"{title_fallback} ({year}){ext}"
                confidence = "medium"
                reason = "title_year_only"
            else:
                suggested = file_path.name
                confidence = "low"
                reason = "book_schema_unrecognized"

        if suggested != file_path.name:
            candidate_valid = parse_book_filename_fields(Path(suggested).stem)
            if not candidate_valid.get("is_valid"):
                suggested = file_path.name
                confidence = "low"
                reason = "book_schema_unrecognized"

        return FilenameSuggestion(
            original_path=str(file_path),
            media_type=MediaType.BOOK.name,
            original_name=file_path.name,
            suggested_name=suggested,
            confidence=confidence,
            reason=reason,
            changed=(file_path.name != suggested),
        )

    def _suggest_comic_filename(self, file_path: Path) -> FilenameSuggestion:
        exact_override = self._get_exact_override(file_path.name)
        if exact_override:
            return FilenameSuggestion(
                original_path=str(file_path),
                media_type=MediaType.COMIC.name,
                original_name=file_path.name,
                suggested_name=exact_override,
                confidence="manual",
                reason="learned_exact_override",
                changed=(file_path.name != exact_override),
            )

        stem = file_path.stem
        ext = file_path.suffix.lower()

        already_valid = parse_comic_filename_fields(stem)
        if already_valid.get("is_valid"):
            return FilenameSuggestion(
                original_path=str(file_path),
                media_type=MediaType.COMIC.name,
                original_name=file_path.name,
                suggested_name=file_path.name,
                confidence="high",
                reason="comic_schema_valid",
                changed=False,
            )

        normalized = re.sub(r"\s+", " ", stem.replace("_", " ")).strip()
        normalized = re.sub(r"^\d+\.\s*", "", normalized).strip()

        series, issue = self._extract_series_issue(normalized)
        if series:
            series = self._apply_comic_series_alias(series)

        year = self._extract_year(normalized)

        if series and issue is not None and year is not None:
            title = self._sanitize_name(series)
            series_group = self._sanitize_name(series)
            suggested = f"{title} ({year}) - {series_group} #{issue:03d}{ext}"
            confidence = "high"
            reason = "comic_title_year_series_issue_extracted"
        else:
            suggested = file_path.name
            confidence = "low"
            reason = "comic_schema_unrecognized"

        if suggested != file_path.name:
            candidate_valid = parse_comic_filename_fields(Path(suggested).stem)
            if not candidate_valid.get("is_valid"):
                suggested = file_path.name
                confidence = "low"
                reason = "comic_schema_unrecognized"

        return FilenameSuggestion(
            original_path=str(file_path),
            media_type=MediaType.COMIC.name,
            original_name=file_path.name,
            suggested_name=suggested,
            confidence=confidence,
            reason=reason,
            changed=(file_path.name != suggested),
        )

    def _extract_book_author_title(self, stem: str) -> tuple[Optional[str], Optional[str]]:
        if " - " not in stem:
            return None, self._sanitize_name(stem)

        left, right = stem.split(" - ", 1)
        author = self._sanitize_name(left)
        title = self._sanitize_name(right)

        if not author or not title:
            return None, self._sanitize_name(stem)

        return author, title

    def _extract_series_issue(self, stem: str) -> tuple[Optional[str], Optional[int]]:
        # Fallback with trailing year: "Series 12 (2015)"
        match = re.match(r"^(.+?)\s+(\d{1,4})\s*\((?:19|20)\d{2}\)\s*$", stem)
        if match:
            return self._sanitize_name(match.group(1)), int(match.group(2))

        # Preferred comic pattern: "Series #12"
        match = re.match(r"^(.+?)\s*#\s*(\d{1,4})\s*$", stem)
        if match:
            return self._sanitize_name(match.group(1)), int(match.group(2))

        # Common fallback: "Series 12"
        match = re.match(r"^(.+?)\s+(\d{1,4})\s*$", stem)
        if match:
            return self._sanitize_name(match.group(1)), int(match.group(2))

        return self._sanitize_name(stem), None

    def _extract_year(self, text: str) -> Optional[int]:
        match = re.search(r"(?:19|20)\d{2}", text)
        if not match:
            return None
        value = int(match.group(0))
        if 1900 <= value <= 2100:
            return value
        return None

    def _sanitize_name(self, text: str) -> str:
        """Sanitize filename: remove invalid chars, normalize spaces, enforce length limits."""
        sanitized = str(text or "").strip()

        # Remover/substituir caracteres inválidos em filesystems (CRÍTICO)
        # Windows invalid: < > : " | ? *
        # Unix/Linux invalid: \x00 (null)
        sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', '', sanitized)

        # Remover barras (não substituir por espaço)
        sanitized = re.sub(r'[&/\\]', '', sanitized)

        # Normalizar espaços múltiplos
        sanitized = re.sub(r"\s+", " ", sanitized)

        # Remover pontos/espaços no início/fim
        sanitized = sanitized.strip(" .")

        # Verificar tamanho máximo (255 é limite NTFS, ext4, etc)
        if len(sanitized.encode('utf-8')) > 255:
            try:
                truncated = sanitized.encode(
                    'utf-8')[:250].decode('utf-8', errors='ignore')
                sanitized = truncated.rstrip()
            except Exception:
                sanitized = sanitized[:200]

        return sanitized or "Unknown"

    def _default_learning_data(self) -> Dict[str, Any]:
        return {
            "exact_overrides": {},
            "comics": {"series_aliases": {}},
            "books": {"author_aliases": {}},
        }

    def _load_learning_data(self) -> Dict[str, Any]:
        if not self.learning_path.exists() or not self.learning_path.is_file():
            return self._default_learning_data()

        try:
            data = json.loads(self.learning_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return self._default_learning_data()

            default = self._default_learning_data()
            for key, value in default.items():
                if key not in data:
                    data[key] = value
            if "series_aliases" not in data.get("comics", {}):
                data["comics"]["series_aliases"] = {}
            if "author_aliases" not in data.get("books", {}):
                data["books"]["author_aliases"] = {}
            return data
        except Exception:
            return self._default_learning_data()

    def _save_learning_data(self) -> None:
        self.learning_path.parent.mkdir(parents=True, exist_ok=True)
        self.learning_path.write_text(
            json.dumps(self.learning_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _normalize_lookup_name(self, text: str) -> str:
        """Normalize text for lookup with caching (performance improvement)."""
        # Verificar cache primeiro
        if text in self._normalize_cache:
            return self._normalize_cache[text]

        value = str(text or "").strip().lower()
        value = re.sub(r"\s+", " ", value)

        # Armazenar em cache
        self._normalize_cache[text] = value

        # Limpar cache se crescer muito (prevent memory leaks)
        if len(self._normalize_cache) > 10000:
            self._normalize_cache.clear()

        return value

    def _get_exact_override(self, original_name: str) -> Optional[str]:
        key = self._normalize_lookup_name(original_name)
        overrides = self.learning_data.get("exact_overrides", {})
        value = overrides.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _apply_comic_series_alias(self, series: str) -> str:
        aliases = self.learning_data.get(
            "comics", {}).get("series_aliases", {})
        key = self._normalize_lookup_name(series)
        alias = aliases.get(key)
        if isinstance(alias, str) and alias.strip():
            return alias.strip()
        return series

    def _apply_book_author_alias(self, author: str) -> str:
        aliases = self.learning_data.get("books", {}).get("author_aliases", {})
        key = self._normalize_lookup_name(author)
        alias = aliases.get(key)
        if isinstance(alias, str) and alias.strip():
            return alias.strip()
        return author

    def _learn_from_suggestion_item(self, item: Dict[str, Any]) -> Dict[str, int]:
        learned = {"exact": 0, "comic_alias": 0, "book_alias": 0}

        original_name = str(item.get("original_name") or "").strip()
        suggested_name = str(item.get("suggested_name") or "").strip()
        media_type = str(item.get("media_type") or "").strip().upper()

        if not original_name or not suggested_name:
            return learned

        key = self._normalize_lookup_name(original_name)
        overrides = self.learning_data.setdefault("exact_overrides", {})
        if overrides.get(key) != suggested_name:
            overrides[key] = suggested_name
            learned["exact"] = 1

        original_stem = Path(original_name).stem
        suggested_stem = Path(suggested_name).stem

        if media_type == MediaType.COMIC.name:
            old_normalized = re.sub(
                r"\s+", " ", original_stem.replace("_", " ")).strip()
            new_normalized = re.sub(
                r"\s+", " ", suggested_stem.replace("_", " ")).strip()

            old_comic = parse_comic_filename_fields(old_normalized)
            new_comic = parse_comic_filename_fields(new_normalized)

            old_series = None
            new_series = None
            old_issue = None
            new_issue = None

            if old_comic.get("is_valid"):
                old_series = old_comic.get("series") or old_comic.get("title")
                old_issue = old_comic.get("issue_number")
            else:
                old_series, old_issue_int = self._extract_series_issue(
                    old_normalized)
                old_issue = str(
                    old_issue_int) if old_issue_int is not None else None

            if new_comic.get("is_valid"):
                new_series = new_comic.get("series") or new_comic.get("title")
                new_issue = new_comic.get("issue_number")
            else:
                new_series, new_issue_int = self._extract_series_issue(
                    new_normalized)
                new_issue = str(
                    new_issue_int) if new_issue_int is not None else None

            if old_series and new_series and old_issue is not None and new_issue is not None:
                aliases = self.learning_data.setdefault("comics", {}).setdefault(
                    "series_aliases", {}
                )
                alias_key = self._normalize_lookup_name(old_series)
                existing_alias = aliases.get(alias_key)

                # Detectar conflito de alias (CRÍTICO - integridade de dados)
                if existing_alias and existing_alias != new_series:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"[ALIAS CONFLICT] Comic series '{old_series}': "
                        f"previously mapped to '{existing_alias}', now being mapped to '{new_series}'. "
                        f"Using latest value. Manual review recommended."
                    )
                    # Armazenar conflito para análise
                    conflicts = self.learning_data.setdefault(
                        "_conflicts", {}).setdefault("comics", [])
                    conflicts.append({
                        "series": old_series,
                        "previous_alias": existing_alias,
                        "new_alias": new_series,
                        "timestamp": __import__('datetime').datetime.now().isoformat(),
                    })

                if aliases.get(alias_key) != new_series:
                    aliases[alias_key] = new_series
                    learned["comic_alias"] = 1

        if media_type == MediaType.BOOK.name:
            old_author, _ = self._extract_book_author_title(
                re.sub(r"\s+", " ", original_stem.replace("_", " ")).strip()
            )
            new_author, _ = self._extract_book_author_title(
                re.sub(r"\s+", " ", suggested_stem.replace("_", " ")).strip()
            )
            if old_author and new_author:
                aliases = self.learning_data.setdefault("books", {}).setdefault(
                    "author_aliases", {}
                )
                alias_key = self._normalize_lookup_name(old_author)
                existing_alias = aliases.get(alias_key)

                # Detectar conflito de alias em livros
                if existing_alias and existing_alias != new_author:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"[ALIAS CONFLICT] Book author '{old_author}': "
                        f"previously mapped to '{existing_alias}', now being mapped to '{new_author}'. "
                        f"Using latest value. Manual review recommended."
                    )
                    # Armazenar conflito
                    conflicts = self.learning_data.setdefault(
                        "_conflicts", {}).setdefault("books", [])
                    conflicts.append({
                        "author": old_author,
                        "previous_alias": existing_alias,
                        "new_alias": new_author,
                        "timestamp": __import__('datetime').datetime.now().isoformat(),
                    })

                if aliases.get(alias_key) != new_author:
                    aliases[alias_key] = new_author
                    learned["book_alias"] = 1

        return learned


def iter_preview_lines(report: Dict[str, Any], limit: Optional[int] = None) -> Iterable[str]:
    if limit is None:
        try:
            limit = int(os.getenv("FILENAME_PREVIEW_LIMIT_DEFAULT", "30"))
        except ValueError:
            limit = 30
    limit = max(0, int(limit))

    suggestions = report.get("suggestions") or []
    changed_suggestions = [
        item for item in suggestions if bool(item.get("changed", False))]

    if not changed_suggestions:
        yield "[yellow]No filename changes detected.[/yellow]"
        return

    count = 0

    for item in changed_suggestions:
        if count >= limit:
            break
        old = item.get("original_name", "")
        new = item.get("suggested_name", "")
        media = item.get("media_type", "")
        confidence = item.get("confidence", "")
        yield f"[{media}|{confidence}] {old} => {new}"
        count += 1
