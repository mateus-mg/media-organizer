"""
Core module for Media Organization System

Consolidated module containing:
- Types (MediaType, dataclasses)
- Interfaces (ABC for validators, organizers, etc.)
- Validators (File existence, type, completeness, junk)
- Orchestrator (Main coordination logic)

Usage:
    from src.core import (
        MediaType, Config, Orquestrador,
        ValidatorInterface, OrganizadorInterface,
        FileExistenceValidator, FileTypeValidator,
        IncompleteFileValidator, JunkFileValidator
    )
"""
import asyncio
import hashlib
import logging
import re
from collections import Counter
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from src.utils import is_incomplete_file, is_junk_file


# ============================================================================
# SECTION 1: TYPES
# ============================================================================

class MediaType(Enum):
    """Supported media types"""
    MUSIC = "music"
    LYRICS = "lyrics"
    BOOK = "book"
    COMIC = "comic"
    RENAMER = "renamer"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Result of validation operation"""
    is_valid: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FileMetadata:
    """Metadata extracted from media file"""
    media_type: MediaType
    title: Optional[str] = None
    year: Optional[int] = None
    author: Optional[str] = None
    album: Optional[str] = None
    track_number: Optional[int] = None
    genre: Optional[str] = None
    media_subtype: Optional[str] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrganizationResult:
    """Result of file organization"""
    success: bool
    organized_path: Optional[Path] = None
    error_message: Optional[str] = None
    skipped: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def was_processed(self) -> bool:
        """Check if file was processed (organized or skipped)"""
        return self.success or self.skipped


@dataclass
class ValidationRule:
    """Definition of validation rule"""
    name: str
    description: str
    applies_to: List[MediaType]
    required: bool = True
    error_message: str = "Validation failed"

    def validate(self, file_path: Path, metadata: FileMetadata) -> ValidationResult:
        """Validate file against this rule"""
        raise NotImplementedError


@dataclass
class ProcessedFile:
    """Information about processed file"""
    original_path: Path
    organized_path: Optional[Path] = None
    media_type: Optional[MediaType] = None
    success: bool = False
    error_message: Optional[str] = None
    processing_time: Optional[datetime] = None
    metadata: FileMetadata = field(
        default_factory=lambda: FileMetadata(media_type=MediaType.UNKNOWN))
    was_skipped: bool = False


# ============================================================================
# SECTION 2: INTERFACES
# ============================================================================

class ValidatorInterface(ABC):
    """Interface for file validators"""

    @abstractmethod
    async def validate(self, file_path: Path) -> ValidationResult:
        """Validate file and return result"""
        pass

    @abstractmethod
    def can_validate(self, file_path: Path) -> bool:
        """Check if validator can validate this file"""
        pass


class OrganizadorInterface(ABC):
    """Interface for media organizers"""

    @abstractmethod
    async def organizar(self, file_path: Path) -> OrganizationResult:
        """Organize single file"""
        pass

    @abstractmethod
    def pode_processar(self, file_path: Path) -> bool:
        """Check if organizer can process file"""
        pass

    @abstractmethod
    def obter_tipo_midia(self) -> MediaType:
        """Return media type this organizer handles"""
        pass


class ConcurrencyManagerInterface(ABC):
    """Interface for concurrency management"""

    @abstractmethod
    async def executar_em_paralelo(
        self,
        tarefas: List[Callable],
        limite_simultaneos: int
    ) -> List[Any]:
        """Execute tasks in parallel"""
        pass

    @abstractmethod
    def obter_lock_arquivo(self, caminho_arquivo: Path):
        """Get file lock"""
        pass


class MediaClassifierInterface(ABC):
    """Interface for media classification"""

    @abstractmethod
    def classificar_tipo_midia(self, file_path: Path) -> MediaType:
        """Classify media type"""
        pass

    @abstractmethod
    def extrair_metadados(self, file_path: Path) -> FileMetadata:
        """Extract metadata"""
        pass


class FileScannerInterface(ABC):
    """Interface for file scanning"""

    @abstractmethod
    def escanear_diretorio(self, diretorio: Path) -> List[Path]:
        """Scan directory"""
        pass

    @abstractmethod
    def filtrar_arquivos_para_organizacao(self, arquivos: List[Path]) -> List[Path]:
        """Filter files for organization"""
        pass


class DatabaseInterface(ABC):
    """Interface for database operations"""

    @abstractmethod
    def adicionar_midia(
        self,
        file_hash: str,
        original_path: str,
        organized_path: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Add organized media"""
        pass

    @abstractmethod
    def is_file_organized(self, file_path: str) -> bool:
        """Check if file organized"""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics"""
        pass


# ============================================================================
# SECTION 3: VALIDATORS
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
# SECTION 4: ORCHESTRATOR
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

    def _ordenar_arquivos_para_processamento(self, arquivos: List[Path]) -> List[Path]:
        """Order files to keep audio tracks and sidecar lyrics together.

        Processing order priority inside the same stem group:
        1) music
        2) lyrics
        3) everything else
        """
        if len(arquivos) <= 1:
            return arquivos

        type_cache: Dict[Path, MediaType] = {}
        grouped: Dict[str, List[Path]] = {}
        group_order: List[str] = []

        for arquivo in arquivos:
            media_type = self.classifier.classificar_tipo_midia(arquivo)
            type_cache[arquivo] = media_type

            group_key = arquivo.stem.casefold()
            if group_key not in grouped:
                grouped[group_key] = []
                group_order.append(group_key)
            grouped[group_key].append(arquivo)

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

    def _normalize_lyrics_stem_for_dedup(self, stem: str) -> str:
        """Normalize common duplicate suffixes from downloaded lyrics names."""
        normalized = stem.strip()
        normalized = re.sub(r"\s*\(\d+\)\s*$", "", normalized)
        normalized = re.sub(
            r"\s*[-_ ](?:copy|copia|cópia)\s*$", "", normalized, flags=re.IGNORECASE)
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

    def _deduplicate_lyrics_files(self, arquivos: List[Path]) -> List[Path]:
        """Remove true duplicate `.lrc` files before processing.

        Duplicates are confirmed only when all are true:
        - same parent directory
        - same normalized stem (handles `(1)`, `copy`, etc.)
        - identical file content hash
        """
        lyrics = [f for f in arquivos if f.suffix.lower() == ".lrc"]
        if len(lyrics) <= 1:
            return arquivos

        grouped: Dict[tuple[str, str, str], List[Path]] = {}
        for lyric in lyrics:
            content_md5 = self._file_md5(lyric)
            if not content_md5:
                continue
            key = (
                str(lyric.parent.resolve()),
                self._normalize_lyrics_stem_for_dedup(lyric.stem),
                content_md5,
            )
            grouped.setdefault(key, []).append(lyric)

        duplicates_to_remove: List[Path] = []
        for group_files in grouped.values():
            if len(group_files) <= 1:
                continue
            group_files.sort(key=lambda p: (len(p.name), p.name.casefold()))
            duplicates_to_remove.extend(group_files[1:])

        if not duplicates_to_remove:
            return arquivos

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
        return [f for f in arquivos if f not in duplicate_set]

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
        cycle_label = source_label or diretorio_origem.name
        self.logger.info(
            "Starting %s organization cycle: %s",
            cycle_label,
            diretorio_origem,
        )

        # Step 1: Scan
        all_files = self.scanner.escanear_diretorio(diretorio_origem)
        self.logger.info("%s scan: found %s %s", cycle_label,
                         len(all_files), progress_unit)

        # Step 2: Filter already organized
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

        # Step 3: Validate completion
        if validar_completude_arquivo and self.file_completion_validator:
            valid_files = self.file_completion_validator.validar_arquivos(
                files_to_process)
        else:
            valid_files = files_to_process

        # Remove true duplicate lyrics before ordering/processing.
        valid_files = self._deduplicate_lyrics_files(valid_files)

        valid_files = self._ordenar_arquivos_para_processamento(valid_files)

        # Show an explicit media breakdown for mixed folders (e.g. tracks + .lrc).
        pending_by_type: Counter[MediaType] = Counter(
            self.classifier.classificar_tipo_midia(file_path)
            for file_path in valid_files
        )
        track_total = pending_by_type.get(MediaType.MUSIC, 0)
        lyrics_total = pending_by_type.get(MediaType.LYRICS, 0)
        if track_total or lyrics_total:
            self.logger.info(
                "%s breakdown: tracks=%s | lyrics=%s",
                cycle_label,
                track_total,
                lyrics_total,
            )

        # Step 4: Process each file
        resultados = []
        total_valid = len(valid_files)
        progress_step = 10 if total_valid >= 10 else 1
        organized_count = 0
        skipped_count = 0
        failed_count = 0
        organized_by_type: Counter[MediaType] = Counter()
        skipped_by_type: Counter[MediaType] = Counter()
        failed_by_type: Counter[MediaType] = Counter()

        for index, arquivo in enumerate(valid_files, start=1):
            resultado = await self._processar_arquivo(arquivo)
            resultados.append(resultado)

            media_type = resultado.media_type or MediaType.UNKNOWN

            if resultado.was_skipped:
                skipped_count += 1
                skipped_by_type[media_type] += 1
            elif resultado.success:
                organized_count += 1
                organized_by_type[media_type] += 1
            else:
                failed_count += 1
                failed_by_type[media_type] += 1

            if index == 1 or index % progress_step == 0 or index == total_valid:
                breakdown_suffix = ""
                if track_total or lyrics_total:
                    breakdown_suffix = (
                        " | tracks(o/s/f)="
                        f"{organized_by_type.get(MediaType.MUSIC, 0)}/"
                        f"{skipped_by_type.get(MediaType.MUSIC, 0)}/"
                        f"{failed_by_type.get(MediaType.MUSIC, 0)}"
                        " | lyrics(o/s/f)="
                        f"{organized_by_type.get(MediaType.LYRICS, 0)}/"
                        f"{skipped_by_type.get(MediaType.LYRICS, 0)}/"
                        f"{failed_by_type.get(MediaType.LYRICS, 0)}"
                    )

                self.logger.info(
                    "%s progress: %s/%s %s processed | organized=%s skipped=%s failed=%s | current=%s%s",
                    cycle_label,
                    index,
                    total_valid,
                    progress_unit,
                    organized_count,
                    skipped_count,
                    failed_count,
                    arquivo.name,
                    breakdown_suffix,
                )

        final_breakdown = ""
        if track_total or lyrics_total:
            final_breakdown = (
                " | tracks(o/s/f)="
                f"{organized_by_type.get(MediaType.MUSIC, 0)}/"
                f"{skipped_by_type.get(MediaType.MUSIC, 0)}/"
                f"{failed_by_type.get(MediaType.MUSIC, 0)}"
                " | lyrics(o/s/f)="
                f"{organized_by_type.get(MediaType.LYRICS, 0)}/"
                f"{skipped_by_type.get(MediaType.LYRICS, 0)}/"
                f"{failed_by_type.get(MediaType.LYRICS, 0)}"
            )

        self.logger.info(
            "%s completed: %s/%s organized | skipped=%s failed=%s%s",
            cycle_label,
            organized_count,
            total_valid,
            skipped_count,
            failed_count,
            final_breakdown,
        )
        return resultados

    async def _processar_arquivo(self, arquivo: Path) -> ProcessedFile:
        """Process single file"""
        processed_file = ProcessedFile(
            original_path=arquivo,
            processing_time=datetime.now(),
            metadata=FileMetadata(media_type=MediaType.UNKNOWN)
        )

        try:
            # Classify
            media_type = self.classifier.classificar_tipo_midia(arquivo)
            processed_file.media_type = media_type

            # Validate
            validacao = await self._validar_arquivo_global(arquivo)
            if not validacao.is_valid:
                processed_file.error_message = validacao.error_message
                processed_file.was_skipped = True
                return processed_file

            # Organize
            organizador = self.organizadores.get(media_type)
            if not organizador:
                processed_file.error_message = f"No organizer for: {media_type}"
                processed_file.was_skipped = True
                return processed_file

            if not organizador.pode_processar(arquivo):
                processed_file.error_message = f"Cannot process: {arquivo}"
                processed_file.was_skipped = True
                return processed_file

            resultado = await organizador.organizar(arquivo)
            processed_file.success = resultado.success
            processed_file.organized_path = resultado.organized_path
            processed_file.was_skipped = resultado.skipped

            if resultado.error_message:
                processed_file.error_message = resultado.error_message

            # Log
            if resultado.skipped:
                self.logger.info(f"↷ Skipped: {arquivo.name}")
            elif resultado.success:
                self.logger.info(f"✓ Organized: {arquivo.name}")
            else:
                self.logger.error(f"✗ Failed: {arquivo.name}")

        except Exception as e:
            processed_file.error_message = f"Error: {str(e)}"
            processed_file.success = False
            self.logger.error(f"Error processing {arquivo.name}: {e}")

        return processed_file

    async def _validar_arquivo_global(self, arquivo: Path) -> ValidationResult:
        """Apply all global validators"""
        for validator in self.validators:
            if validator.can_validate(arquivo):
                resultado = await validator.validate(arquivo)
                if not resultado.is_valid:
                    return resultado
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
