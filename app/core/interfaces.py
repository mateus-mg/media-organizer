"""
Core interfaces for Media Organization System.

Contains ABC interfaces for:
- Validators
- Organizers
- Concurrency management
- Media classification
- File scanning
- Database operations
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Any, Callable, Dict

from app.core.types import (
    MediaType,
    ValidationResult,
    FileMetadata,
    OrganizationResult,
)


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
    async def execute_parallel(
        self,
        tarefas: List[Callable],
        max_concurrent: int
    ) -> List[Any]:
        """Execute tasks in parallel"""
        pass

    @abstractmethod
    def get_file_lock(self, file_path: Path):
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
    def scan_directory(self, directory: Path) -> List[Path]:
        """Scan directory"""
        pass

    @abstractmethod
    def filter_files_for_organization(self, files: List[Path]) -> List[Path]:
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
