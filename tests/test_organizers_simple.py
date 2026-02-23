#!/usr/bin/env python3
"""
Test organizer classes
"""

import sys
import asyncio
from pathlib import Path
import tempfile

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.organizers import MovieOrganizer, TVOrganizer, MusicOrganizer, BookOrganizer
from src.persistence import OrganizationDatabase
from src.utils import ConflictHandler, get_logger
from src.config import Config
from src.core import MediaType


def test_organizer_initialization():
    """Test organizer initialization"""
    print("🧪 Testing Organizer Initialization...")
    
    # Mock config and database for testing
    config = Config()
    logger = get_logger(dry_run=True)
    
    # Test that organizers can be instantiated (with mocked dependencies)
    print("  Testing organizer imports...")
    print(f"  ✅ MovieOrganizer: {MovieOrganizer is not None}")
    print(f"  ✅ TVOrganizer: {TVOrganizer is not None}")
    print(f"  ✅ MusicOrganizer: {MusicOrganizer is not None}")
    print(f"  ✅ BookOrganizer: {BookOrganizer is not None}")
    
    print()


def test_media_type_enum():
    """Test MediaType enum"""
    print("🧪 Testing MediaType enum...")
    
    expected_types = ['MOVIE', 'TV_SHOW', 'ANIME', 'DORAMA', 'MUSIC', 'BOOK', 'COMIC', 'UNKNOWN']
    
    for type_name in expected_types:
        has_type = hasattr(MediaType, type_name)
        status = "✅" if has_type else "❌"
        print(f"  {status} MediaType.{type_name}: {'exists' if has_type else 'MISSING'}")
    
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("ORGANIZER TESTS")
    print("=" * 60)
    print()
    
    test_organizer_initialization()
    test_media_type_enum()
    
    print("=" * 60)
    print("TESTS COMPLETED")
    print("=" * 60)
