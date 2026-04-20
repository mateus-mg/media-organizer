"""
Orchestrator and validators for Media Organization System.

Contains:
- Orquestrador (main coordination logic)
- FileExistenceValidator
- FileTypeValidator
- IncompleteFileValidator
- JunkFileValidator
"""
import asyncio
import hashlib
import logging
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.core.types import (
    MediaType,
    ValidationResult,
    FileMetadata,
    OrganizationResult,
    ProcessedFile,
)
from app.core.interfaces import (
    ValidatorInterface,
    OrganizadorInterface,
    MediaClassifierInterface,
    FileScannerInterface,
    DatabaseInterface,
)
from app.config.constants import AUDIO_EXTS
from app.infrastructure.database import UnorganizedDatabase
from app.utils.helpers import is_incomplete_file, is_junk_file


# ============================================================================
# SECTION 1: VALIDATORS
# ============================================================================

class FileExistenceValidator(ValidatorInterface):
    """Validate file exists and is accessible"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    async def validate(self, file_path: Path) -> ValidationResult:
        """Validate file exists"""
        if not file_path.exists():
            return ValidationResult(
                is_valid=False,
                error_message=f"File does not exist: {file_path}"
            )

        if not file_path.is_file():
            return ValidationResult(
                is_valid=False,
                error_message=f"Path is not a file: {file_path}"
            )

        try:
            with open(file_path, 'rb'):
                pass
        except IOError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"File not accessible: {e}"
            )

        return ValidationResult(is_valid=True)

    def can_validate(self, file_path: Path) -> bool:
        return True


class FileTypeValidator(ValidatorInterface):
    """Validate file type is supported"""

    def __init__(self, supported_types: List[str], logger: Optional[logging.Logger] = None):
        self.supported_types = {ext.lower() for ext in supported_types}
        self.logger = logger or logging.getLogger(__name__)

    async def validate(self, file_path: Path) -> ValidationResult:
        """Validate file type"""
        if file_path.suffix.lower() not in self.supported_types:
            return ValidationResult(
                is_valid=False,
                error_message=f"Unsupported file type: {file_path.suffix}"
            )
        return ValidationResult(is_valid=True)

    def can_validate(self, file_path: Path) -> bool:
        return True


class IncompleteFileValidator(ValidatorInterface):
    """Validate file is not incomplete"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    async def validate(self, file_path: Path) -> ValidationResult:
        """Validate file completeness"""
        if is_incomplete_file(file_path):
            return ValidationResult(
                is_valid=False,
                error_message=f"Incomplete or invalid file: {file_path.name}"
            )

        return ValidationResult(is_valid=True)

    def can_validate(self, file_path: Path) -> bool:
        return True


class JunkFileValidator(ValidatorInterface):
    """Validate file is not junk/promotional"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    async def validate(self, file_path: Path) -> ValidationResult:
        """Validate file is not junk"""
        if is_junk_file(file_path):
            return ValidationResult(
                is_valid=False,
                error_message=f"Junk file: {file_path.name}"
            )

        return ValidationResult(is_valid=True)

    def can_validate(self, file_path: Path) -> bool:
        return True


# ============================================================================
# SECTION 2: ORCHESTRATOR
# ============================================================================

class Orquestrador:
    """
    Main orchestrator for media organization process.

    Coordinates the entire workflow:
    1. Scan directory for files
    2. Filter already organized files
    3. Validate file completion
    4. Classify media type
    5. Apply validators
    6. Organize via appropriate organizer
    7. Track in database
    """

    def __init__(
        self,
        validators: List[ValidatorInterface],
        organizadores: Dict[MediaType, OrganizadorInterface],
        classifier: MediaClassifierInterface,
        scanner: FileScannerInterface,
        database: DatabaseInterface,
        file_completion_validator=None,
        logger: Optional[logging.Logger] = None
    ):
        self.validators = validators
        self.organizadores = organizadores
        self.classifier = classifier
        self.scanner = scanner
        self.database = database
        self.file_completion_validator = file_completion_validator
        self.logger = logger or logging.getLogger(__name__)
        unorganized_path = Path(
            os.getenv("UNORGANIZED_DB_PATH", "data/unorganized.json")
        )
        self.unorganized_db = UnorganizedDatabase(unorganized_path)

    def _is_schema_skip_reason(self, reason: str) -> bool:
        value = str(reason or "").strip().lower()
        return value.startswith("comic_schema_") or value.startswith("book_schema_")

    def _sync_unorganized_registry(
        self,
        file_path: Path,
        media_type: MediaType,
        result: OrganizationResult,
    ) -> None:
        if result.success and not result.skipped:
            self.unorganized_db.remove_unorganized(str(file_path))
            return

        if not result.skipped:
            return

        skip_reason = str(
            result.skip_reason or result.error_message or "").strip()
        if not self._is_schema_skip_reason(skip_reason):
            return

        self.unorganized_db.add_unorganized(
            file_path=str(file_path),
            error_message=skip_reason,
            media_type=getattr(media_type, "value", str(media_type)),
            reason=skip_reason,
        )

    def _order_files_for_processing(self, files: List[Path]) -> List[Path]:
        """Order files to keep audio tracks and sidecar lyrics together.

        Processing order priority inside the same stem group:
        1) music
        2) lyrics
        3) everything else
        """
        if len(files) <= 1:
            return files

        type_cache: Dict[Path, MediaType] = {}
        grouped: Dict[str, List[Path]] = {}
        group_order: List[str] = []

        for file_path in files:
            media_type = self.classifier.classificar_tipo_midia(file_path)
            type_cache[file_path] = media_type

            group_key = file_path.stem.casefold()
            if group_key not in grouped:
                grouped[group_key] = []
                group_order.append(group_key)
            grouped[group_key].append(file_path)

        type_priority = {
            MediaType.MUSIC: 0,
            MediaType.LYRICS: 1,
            MediaType.BOOK: 2,
            MediaType.COMIC: 2,
            MediaType.RENAMER: 2,
            MediaType.UNKNOWN: 3,
        }

        ordered: List[Path] = []
        for group_key in group_order:
            files = grouped[group_key]
            files.sort(
                key=lambda path: (
                    type_priority.get(type_cache.get(
                        path, MediaType.UNKNOWN), 3),
                    path.suffix.casefold(),
                    path.name.casefold(),
                )
            )
            ordered.extend(files)

        return ordered

    def _is_dry_run_mode(self) -> bool:
        for organizador in self.organizadores.values():
            dry_run = getattr(organizador, "dry_run", None)
            if isinstance(dry_run, bool):
                return dry_run
        return False

    def _log_stage(self, cycle_label: str, stage: str) -> None:
        self.logger.info("")
        self.logger.info("%s", "=" * 88)
        self.logger.info("%s | %s", cycle_label, stage)
        self.logger.info("%s", "=" * 88)

    def _normalize_lyrics_stem_for_dedup(self, stem: str) -> str:
        """Normalize common duplicate suffixes from downloaded lyrics names."""
        normalized = stem.strip()
        normalized = re.sub(r"\s*\(\d+\)\s*$", "", normalized)
        normalized = re.sub(
            r"\s*[-_ ]copy\s*$", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized.casefold()

    def _file_md5(self, file_path: Path, chunk_size: int = 1024 * 1024) -> Optional[str]:
        try:
            digest = hashlib.md5()
            with open(file_path, "rb") as handle:
                while True:
                    chunk = handle.read(chunk_size)
                    if not chunk:
                        break
                    digest.update(chunk)
            return digest.hexdigest()
        except Exception:
            return None

    def _deduplicate_lyrics_files(self, files: List[Path]) -> List[Path]:
        """Remove true duplicate `.lrc` files before processing."""
        lyrics = [f for f in files if f.suffix.lower() == ".lrc"]
        if len(lyrics) <= 1:
            return files

        grouped_exact: Dict[tuple[str, str], List[Path]] = {}
        for lyric in lyrics:
            content_md5 = self._file_md5(lyric)
            if not content_md5:
                continue
            key = (
                self._normalize_lyrics_stem_for_dedup(lyric.stem),
                content_md5,
            )
            grouped_exact.setdefault(key, []).append(lyric)

        duplicates_to_remove: List[Path] = []
        for group_files in grouped_exact.values():
            if len(group_files) <= 1:
                continue
            group_files.sort(key=lambda p: (len(p.name), p.name.casefold()))
            duplicates_to_remove.extend(group_files[1:])

        remaining_lyrics = [
            lyric for lyric in lyrics if lyric not in set(duplicates_to_remove)]
        grouped_semantic: Dict[str, List[Path]] = {}
        for lyric in remaining_lyrics:
            key = self._normalize_lyrics_stem_for_dedup(lyric.stem)
            grouped_semantic.setdefault(key, []).append(lyric)

        def _has_local_audio_pair(lyric: Path) -> bool:
            for ext in AUDIO_EXTS:
                if lyric.with_suffix(ext).exists():
                    return True
            return False

        for group_files in grouped_semantic.values():
            if len(group_files) <= 1:
                continue

            ranked = sorted(
                group_files,
                key=lambda p: (
                    0 if _has_local_audio_pair(p) else 1,
                    -p.stat().st_size if p.exists() else 0,
                    len(p.name),
                    p.name.casefold(),
                ),
            )
            duplicates_to_remove.extend(ranked[1:])

        if not duplicates_to_remove:
            return files

        duplicates_to_remove = list(dict.fromkeys(duplicates_to_remove))

        dry_run = self._is_dry_run_mode()
        removed = 0
        for duplicate in duplicates_to_remove:
            if dry_run:
                self.logger.info(
                    "[DRY RUN] Duplicate lyrics detected (would remove): %s",
                    duplicate,
                )
                removed += 1
                continue

            try:
                duplicate.unlink(missing_ok=True)
                self.logger.info("Removed duplicate lyrics: %s", duplicate)
                removed += 1
            except Exception as exc:
                self.logger.warning(
                    "Could not remove duplicate lyrics %s: %s",
                    duplicate,
                    exc,
                )

        if removed:
            self.logger.info(
                "Lyrics deduplication finished: removed=%s",
                removed,
            )

        duplicate_set = set(duplicates_to_remove)
        return [f for f in files if f not in duplicate_set]

    async def organizar_arquivos(
        self,
        diretorio_origem: Path,
        validar_completude_arquivo: bool = True,
        source_label: Optional[str] = None,
        progress_unit: str = "files",
    ) -> List[ProcessedFile]:
        """
        Orchestrate complete file organization process

        Args:
            diretorio_origem: Directory to organize
            validar_completude_arquivo: Validate file completion

        Returns:
            List of processed files
        """
        source_directory = diretorio_origem
        validate_file_completion = validar_completude_arquivo
        cycle_label = source_label or source_directory.name
        self._log_stage(cycle_label, "ORCHESTRATION START")
        self.logger.info(
            "Starting %s organization cycle: %s",
            cycle_label,
            source_directory,
        )

        self._log_stage(cycle_label, "SCAN START")
        all_files = self.scanner.scan_directory(source_directory)
        self.logger.info("%s scan: found %s %s", cycle_label,
                         len(all_files), progress_unit)
        self._log_stage(cycle_label, "SCAN END")

        self._log_stage(cycle_label, "PENDING FILTER START")
        files_to_process = [
            f for f in all_files
            if not self.database.is_file_organized(str(f))
        ]
        self.logger.info(
            "%s pending: %s %s need organization",
            cycle_label,
            len(files_to_process),
            progress_unit,
        )
        self._log_stage(cycle_label, "PENDING FILTER END")

        self._log_stage(cycle_label, "VALIDATION START")
        if validate_file_completion and self.file_completion_validator:
            valid_files = self.file_completion_validator.validate_files(
                files_to_process)
        else:
            valid_files = files_to_process
        self._log_stage(cycle_label, "VALIDATION END")

        self._log_stage(cycle_label, "DEDUP/SORT START")
        valid_files = self._deduplicate_lyrics_files(valid_files)
        valid_files = self._order_files_for_processing(valid_files)
        self._log_stage(cycle_label, "DEDUP/SORT END")

        classified_valid_files = [
            (file_path, self.classifier.classificar_tipo_midia(file_path))
            for file_path in valid_files
        ]
        ignored_unknown = sum(
            1 for _, media_type in classified_valid_files if media_type == MediaType.UNKNOWN
        )
        if ignored_unknown:
            self.logger.info(
                "%s pre-filter: ignored=%s unsupported %s",
                cycle_label,
                ignored_unknown,
                progress_unit,
            )

        valid_files = [
            file_path
            for file_path, media_type in classified_valid_files
            if media_type != MediaType.UNKNOWN
        ]

        pending_by_type: Counter[MediaType] = Counter(
            media_type
            for _, media_type in classified_valid_files
            if media_type != MediaType.UNKNOWN
        )
        type_order = {
            MediaType.MUSIC: 0,
            MediaType.LYRICS: 1,
            MediaType.ARTWORK: 2,
            MediaType.BOOK: 3,
            MediaType.COMIC: 4,
            MediaType.RENAMER: 5,
            MediaType.UNKNOWN: 6,
        }

        cycle_types = [
            media_type
            for media_type, count in pending_by_type.items()
            if count > 0
        ]
        cycle_types.sort(
            key=lambda media_type: (
                type_order.get(media_type, 99),
                getattr(media_type, "value", str(media_type)),
            )
        )

        if cycle_types:
            pending_breakdown = " | ".join(
                f"{getattr(media_type, 'value', str(media_type))}={pending_by_type.get(media_type, 0)}"
                for media_type in cycle_types
            )
            self.logger.info(
                "%s breakdown: %s",
                cycle_label,
                pending_breakdown,
            )

        results = []
        total_valid = len(valid_files)
        self._log_stage(cycle_label, "PROCESSING START")
        progress_step = 10 if total_valid >= 10 else 1
        organized_count = 0
        skipped_count = 0
        failed_count = 0
        organized_by_type: Counter[MediaType] = Counter()
        skipped_by_type: Counter[MediaType] = Counter()
        failed_by_type: Counter[MediaType] = Counter()

        for index, file_path in enumerate(valid_files, start=1):
            result = await self._process_file(file_path)
            results.append(result)

            media_type = result.media_type or MediaType.UNKNOWN
            current_type = getattr(media_type, "value", str(media_type))

            if result.was_skipped:
                skipped_count += 1
                skipped_by_type[media_type] += 1
            elif result.success:
                organized_count += 1
                organized_by_type[media_type] += 1
            else:
                failed_count += 1
                failed_by_type[media_type] += 1

            if index == 1 or index % progress_step == 0 or index == total_valid:
                breakdown_suffix = ""
                if cycle_types:
                    breakdown_suffix = " | " + " | ".join(
                        f"{getattr(media_type, 'value', str(media_type))}(o/s/f)="
                        f"{organized_by_type.get(media_type, 0)}/"
                        f"{skipped_by_type.get(media_type, 0)}/"
                        f"{failed_by_type.get(media_type, 0)}"
                        for media_type in cycle_types
                    )

                self.logger.info(
                    "%s progress: %s/%s processed %s | organized=%s skipped=%s failed=%s | current_type=%s | current=%s%s",
                    cycle_label,
                    index,
                    total_valid,
                    progress_unit,
                    organized_count,
                    skipped_count,
                    failed_count,
                    current_type,
                    file_path.name,
                    breakdown_suffix,
                )

        final_breakdown = ""
        if cycle_types:
            final_breakdown = " | " + " | ".join(
                f"{getattr(media_type, 'value', str(media_type))}(o/s/f)="
                f"{organized_by_type.get(media_type, 0)}/"
                f"{skipped_by_type.get(media_type, 0)}/"
                f"{failed_by_type.get(media_type, 0)}"
                for media_type in cycle_types
            )

        self.logger.info(
            "%s organization completed: %s/%s organized | skipped=%s failed=%s%s",
            cycle_label,
            organized_count,
            total_valid,
            skipped_count,
            failed_count,
            final_breakdown,
        )
        self._log_stage(cycle_label, "PROCESSING END")
        self._log_stage(cycle_label, "ORCHESTRATION END")
        return results

    async def _process_file(self, file_path: Path) -> ProcessedFile:
        """Process single file"""
        processed_file = ProcessedFile(
            original_path=file_path,
            processing_time=datetime.now(),
            metadata=FileMetadata(media_type=MediaType.UNKNOWN)
        )

        try:
            media_type = self.classifier.classificar_tipo_midia(file_path)
            processed_file.media_type = media_type

            validation = await self._validate_file_global(file_path)
            if not validation.is_valid:
                processed_file.error_message = validation.error_message
                processed_file.was_skipped = True
                self.logger.info(
                    "↷ Skipped: %s | reason=%s",
                    str(file_path),
                    validation.error_message or "global_validation_failed",
                )
                return processed_file

            organizador = self.organizadores.get(media_type)
            if not organizador:
                processed_file.error_message = f"No organizer for: {media_type}"
                processed_file.was_skipped = True
                self.logger.info(
                    "↷ Skipped: %s | reason=%s",
                    str(file_path),
                    processed_file.error_message,
                )
                return processed_file

            if not organizador.pode_processar(file_path):
                processed_file.error_message = f"Cannot process: {file_path}"
                processed_file.was_skipped = True
                self.logger.info(
                    "↷ Skipped: %s | reason=%s",
                    str(file_path),
                    processed_file.error_message,
                )
                return processed_file

            result = await organizador.organizar(file_path)
            processed_file.success = result.success
            processed_file.organized_path = result.organized_path
            processed_file.was_skipped = result.skipped
            self._sync_unorganized_registry(file_path, media_type, result)

            if result.error_message:
                processed_file.error_message = result.error_message

            if result.skipped:
                skip_reason = (
                    result.skip_reason
                    or result.error_message
                    or "organizer_returned_skipped"
                )
                self.logger.info(
                    "↷ Skipped: %s | reason=%s | destination=%s",
                    str(file_path),
                    skip_reason,
                    str(result.organized_path) if result.organized_path else "-",
                )
            elif result.success:
                self.logger.info(f"✓ Organized: {file_path.name}")
            else:
                self.logger.error(f"✗ Failed: {file_path.name}")

        except Exception as e:
            processed_file.error_message = f"Error: {str(e)}"
            processed_file.success = False
            self.logger.error(f"Error processing {file_path.name}: {e}")

        return processed_file

    async def _validate_file_global(self, file_path: Path) -> ValidationResult:
        """Apply all global validators"""
        for validator in self.validators:
            if validator.can_validate(file_path):
                result = await validator.validate(file_path)
                if not result.is_valid:
                    return result
        return ValidationResult(is_valid=True)

    def configurar_validadores(self, validadores: List[ValidatorInterface]) -> None:
        """Configure validators"""
        self.validators = validadores

    def configurar_organizadores(
        self,
        organizadores: Dict[MediaType, OrganizadorInterface]
    ) -> None:
        """Configure organizers"""
        self.organizadores = organizadores
