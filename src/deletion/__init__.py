"""
Deletion Manager Module for Media Organization System

Provides safe deletion of files in hardlink-based environments:
- LinkRegistry: Track all hardlinks by inode
- TrashManager: Manage trash with retention policy
- DeletionManager: Orchestrate permanent and trash deletions

Usage:
    from src.deletion import LinkRegistry, TrashManager, DeletionManager
"""

from src.deletion.link_registry import LinkRegistry
from src.deletion.trash_manager import TrashManager
from src.deletion.deletion_manager import DeletionManager

__all__ = [
    'LinkRegistry',
    'TrashManager',
    'DeletionManager',
]
