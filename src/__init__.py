"""
Media Organization System - Source Package
"""

# Re-export main components for convenience
from src.link_registry import LinkRegistry
from src.trash_manager import TrashManager
from src.deletion_manager import DeletionManager

__all__ = [
    'LinkRegistry',
    'TrashManager',
    'DeletionManager',
]
