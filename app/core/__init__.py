"""Core package for Media Organization System."""

from app.core.types import (
    MediaType,
    ValidationResult,
    FileMetadata,
    OrganizationResult,
    ValidationRule,
    ProcessedFile,
)
from app.core.interfaces import (
    ValidatorInterface,
    OrganizadorInterface,
    ConcurrencyManagerInterface,
    MediaClassifierInterface,
    FileScannerInterface,
    DatabaseInterface,
)
from app.core.orchestrator import (
    Orquestrador,
    FileExistenceValidator,
    FileTypeValidator,
    IncompleteFileValidator,
    JunkFileValidator,
)

__all__ = [
    # Types
    "MediaType",
    "ValidationResult",
    "FileMetadata",
    "OrganizationResult",
    "ValidationRule",
    "ProcessedFile",
    # Interfaces
    "ValidatorInterface",
    "OrganizadorInterface",
    "ConcurrencyManagerInterface",
    "MediaClassifierInterface",
    "FileScannerInterface",
    "DatabaseInterface",
    # Orchestrator and validators
    "Orquestrador",
    "FileExistenceValidator",
    "FileTypeValidator",
    "IncompleteFileValidator",
    "JunkFileValidator",
]
