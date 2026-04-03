"""
Media Organization System - Application Package

Reorganized structure:
- app/config/ - Configuration and constants
- app/core/ - Types, interfaces, orchestrator
- app/services/ - Business logic organizers
- app/infrastructure/ - Database, registry, trash, deletion
- app/validators/ - File validators
- app/metadata/ - Metadata extraction and enrichment
- app/features/ - Genre guard, quality monitor, filename suggestions
- app/cli/ - Command-line interface
- app/utils/ - Utilities
- app/logging/ - Logging configuration
"""

# Re-export main components for convenience
from app.config import Config, AUDIO_EXTS, BOOK_EXTS, COMIC_EXTS, LYRICS_EXTS
from app.core import (
    MediaType,
    ValidationResult,
    FileMetadata,
    OrganizationResult,
    Orquestrador,
    FileExistenceValidator,
    FileTypeValidator,
    IncompleteFileValidator,
    JunkFileValidator,
)
from app.infrastructure import (
    LinkRegistry,
    TrashManager,
    DeletionManager,
    OrganizationDatabase,
)
from app.utils import ConflictHandler, ConflictResolution

__all__ = [
    # Config
    "Config",
    "AUDIO_EXTS",
    "BOOK_EXTS",
    "COMIC_EXTS",
    "LYRICS_EXTS",
    # Core types
    "MediaType",
    "ValidationResult",
    "FileMetadata",
    "OrganizationResult",
    # Orchestrator and validators
    "Orquestrador",
    "FileExistenceValidator",
    "FileTypeValidator",
    "IncompleteFileValidator",
    "JunkFileValidator",
    # Infrastructure
    "LinkRegistry",
    "TrashManager",
    "DeletionManager",
    "OrganizationDatabase",
    # Utils
    "ConflictHandler",
    "ConflictResolution",
]
