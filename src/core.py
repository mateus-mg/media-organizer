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
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime


# ============================================================================
# SECTION 1: TYPES
# ============================================================================

class MediaType(Enum):
    """Supported media types"""
    MOVIE = "movie"
    TV_SHOW = "tv"
    ANIME = "anime"
    DORAMA = "dorama"
    MUSIC = "music"
    BOOK = "book"
    COMIC = "comic"
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
    season: Optional[int] = None
    episode: Optional[int] = None
    tmdb_id: Optional[int] = None
    author: Optional[str] = None
    album: Optional[str] = None
    track_number: Optional[int] = None
    genre: Optional[str] = None
    original_title_pt: Optional[str] = None
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
class TorrentFileInfo:
    """Information about file from QBittorrent"""
    hash: str
    name: str
    state: str
    progress: float
    save_path: Path
    file_path: Path
    is_complete: bool = False
    category: Optional[str] = None


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
    metadata: FileMetadata = field(default_factory=lambda: FileMetadata(media_type=MediaType.UNKNOWN))
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


class QBittorrentValidatorInterface(ABC):
    """Interface for QBittorrent validation"""
    
    @abstractmethod
    async def validar_arquivos(self, arquivos: List[Path]) -> List[Path]:
        """Validate files against QBittorrent"""
        pass
    
    @abstractmethod
    def esta_conectado(self) -> bool:
        """Check if connected"""
        pass
    
    @abstractmethod
    async def desconectar(self) -> None:
        """Disconnect"""
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
    async def adicionar_midia(
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
        self.incomplete_extensions = {'.part', '.tmp', '.!qB', '.crdownload', '.download'}
    
    async def validate(self, file_path: Path) -> ValidationResult:
        """Validate file completeness"""
        if file_path.suffix.lower() in self.incomplete_extensions:
            return ValidationResult(
                is_valid=False,
                error_message=f"Incomplete file: {file_path.name}"
            )
        
        try:
            if file_path.stat().st_size == 0:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Zero-size file: {file_path.name}"
                )
        except OSError:
            return ValidationResult(
                is_valid=False,
                error_message=f"Cannot access file: {file_path.name}"
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
        filename = file_path.name.upper()
        
        junk_names = {
            'BLUDV.MP4', 'BLUDV.TV.MP4', 'BLUDV.COM.MP4',
            '1XBET.MP4', '1XBET.COM.MP4',
            'SAMPLE.MP4', 'SAMPLE.MKV', 'SAMPLE.AVI',
            'TRAILER.MP4', 'TRAILER.MKV'
        }
        
        if filename in junk_names:
            return ValidationResult(
                is_valid=False,
                error_message=f"Junk file: {file_path.name}"
            )
        
        junk_patterns = ['BLUDV', '1XBET', 'SAMPLE', 'WWW.', '_PROMO_', 'DINHEIRO_LIVRE', 'ACESSE']
        
        for pattern in junk_patterns:
            if pattern in filename:
                try:
                    if file_path.stat().st_size < 100 * 1024 * 1024:
                        return ValidationResult(
                            is_valid=False,
                            error_message=f"Promotional file: {file_path.name}"
                        )
                except:
                    pass
        
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
    
    async def organizar_arquivos(
        self,
        diretorio_origem: Path,
        validar_completude_arquivo: bool = True
    ) -> List[ProcessedFile]:
        """
        Orchestrate complete file organization process
        
        Args:
            diretorio_origem: Directory to organize
            validar_completude_arquivo: Validate file completion
            
        Returns:
            List of processed files
        """
        self.logger.info(f"Starting organization: {diretorio_origem}")
        
        # Step 1: Scan
        all_files = self.scanner.escanear_diretorio(diretorio_origem)
        self.logger.info(f"Found {len(all_files)} files")
        
        # Step 2: Filter already organized
        files_to_process = [
            f for f in all_files
            if not self.database.is_file_organized(str(f))
        ]
        self.logger.info(f"{len(files_to_process)} need organization")
        
        # Step 3: Validate completion
        if validar_completude_arquivo and self.file_completion_validator:
            valid_files = self.file_completion_validator.validar_arquivos(files_to_process)
        else:
            valid_files = files_to_process
        
        # Step 4: Process each file
        resultados = []
        for arquivo in valid_files:
            resultado = await self._processar_arquivo(arquivo)
            resultados.append(resultado)
        
        self.logger.info(f"Completed: {len(resultados)} files")
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
            if resultado.success:
                self.logger.info(f"✓ Organized: {arquivo.name}")
            elif resultado.skipped:
                self.logger.info(f"↷ Skipped: {arquivo.name}")
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
