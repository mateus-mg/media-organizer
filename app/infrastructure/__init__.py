"""Infrastructure package for Media Organization System."""

from app.infrastructure.database import OrganizationDatabase, UnorganizedDatabase
from app.infrastructure.link_registry import LinkRegistry
from app.infrastructure.trash_manager import TrashManager
from app.infrastructure.deletion_manager import DeletionManager, DeletionResult

__all__ = [
    "OrganizationDatabase",
    "UnorganizedDatabase",
    "LinkRegistry",
    "TrashManager",
    "DeletionManager",
    "DeletionResult",
]
