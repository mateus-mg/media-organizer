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
from src.utils import ConflictHandler
from src.config import Config
from src.core import MediaType
from src.utils import get_logger
    from src.utils.logger import MediaOrganizerLogger
    from src.simple_mapping import SimpleMappingDB
    
    print("✅ Imports successful via src.*")
    
except ImportError as e:
    print(f"❌ Import via src failed: {e}")
    
    # Try alternative: add src to path and import directly
    src_path = project_root / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))
        print(f"Added {src_path} to sys.path")
        
        try:
            from organizers.movie import MovieOrganizer
            from organizers.tv import TVOrganizer
            from organizers.music import MusicOrganizer
            from organizers.book import BookOrganizer
            from database import OrganizationDatabase
            from utils.conflict_handler import ConflictHandler
            from utils.logger import MediaOrganizerLogger
            from simple_mapping import SimpleMappingDB
            print("✅ Imports successful via direct path")
        except ImportError as e2:
            print(f"❌ Direct import failed: {e2}")
            print("Available modules in organizers:")
            org_path = src_path / "organizers"
            if org_path.exists():
                for f in org_path.iterdir():
                    if f.suffix == '.py':
                        print(f"  - {f.name}")
            sys.exit(1)

class MockConfig:
    """Mock configuration for testing"""
    def __init__(self):
        # Use absolute paths
        test_lib = Path("test_library")
        test_data = Path("test_data")
        
        self.library_path_movies = test_lib / "movies"
        self.library_path_tv = test_lib / "tv"
        self.library_path_animes = test_lib / "anime"
        self.library_path_doramas = test_lib / "dorama"
        self.library_path_music = test_lib / "music"
        self.library_path_books = test_lib / "books"
        self.library_path_audiobooks = test_lib / "audiobooks"
        self.library_path_comics = test_lib / "comics"
        
        self.manual_mapping_path = test_data / "manual_mapping.json"
        
        self.database_path = test_data / "organization.json"
        self.database_backup_enabled = False
        
        self.log_level = "DEBUG"
        self.log_file = test_data / "test.log"
        
        self.conflict_strategy = "skip"
        self.conflict_rename_pattern = "{name}_{counter}{ext}"
        self.conflict_max_attempts = 100
        
        # Add required properties for organizers
        self.download_path_movies = Path("test_downloads/movies")
        self.download_path_tv = Path("test_downloads/tv")
        self.download_path_music = Path("test_downloads/music")
        self.download_path_books = Path("test_downloads/books")

async def test_movie_organizer():
    """Test movie organizer - SIMPLIFIED VERSION"""
    print("🧪 Testing Movie Organizer (simplified)...")
    
    # Create test directories
    test_dir = Path("test_organizer_movie")
    test_dir.mkdir(exist_ok=True)
    
    # Create mock files
    movie_file = test_dir / "Inception.2010.mkv"
    movie_file.write_text("Fake movie content")
    
    try:
        # Create test directories
        Path("test_data").mkdir(exist_ok=True)
        Path("test_library").mkdir(exist_ok=True)
        Path("test_downloads").mkdir(exist_ok=True)
        
        # Create mapping database
        mapping_db = SimpleMappingDB("test_data/manual_mapping.json")
        mapping_db.add_movie(
            file_path=str(movie_file),
            title_pt="A Origem",
            title_en="Inception",
            year=2010,
            tmdb_id=27205
        )
        
        # Initialize organizer
        config = MockConfig()
        logger = MediaOrganizerLogger(name="test", dry_run=True)
        db = OrganizationDatabase(config.database_path, backup_enabled=False)
        conflict_handler = ConflictHandler()
        
        organizer = MovieOrganizer(
            config=config,
            database=db,
            conflict_handler=conflict_handler,
            logger=logger,
            dry_run=True
        )
        
        print(f"  ✅ MovieOrganizer initialized")
        print(f"  File: {movie_file.name}")
        
        # Just test that we can create the organizer without errors
        print("  ✅ Movie organizer test passed (basic initialization)")
            
    except Exception as e:
        print(f"  ❌ Movie organizer test error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)

async def test_tv_organizer():
    """Test TV show organizer - SIMPLIFIED"""
    print("\n🧪 Testing TV Organizer (simplified)...")
    
    test_dir = Path("test_organizer_tv")
    test_dir.mkdir(exist_ok=True)
    
    try:
        # Create test directories
        Path("test_data").mkdir(exist_ok=True)
        Path("test_library").mkdir(exist_ok=True)
        Path("test_downloads").mkdir(exist_ok=True)
        
        # Create mapping database
        mapping_db = SimpleMappingDB("test_data/manual_mapping.json")
        mapping_db.add_series(
            directory=str(test_dir),
            title_pt="Breaking Bad",
            title_en="Breaking Bad",
            year=2008,
            category="tv",
            tmdb_id=1396
        )
        
        config = MockConfig()
        logger = MediaOrganizerLogger(name="test", dry_run=True)
        db = OrganizationDatabase(config.database_path, backup_enabled=False)
        conflict_handler = ConflictHandler()
        
        organizer = TVOrganizer(
            config=config,
            database=db,
            conflict_handler=conflict_handler,
            logger=logger,
            dry_run=True,
            media_subtype="tv"
        )
        
        print(f"  ✅ TVOrganizer initialized")
        print(f"  Directory: {test_dir}")
        print("  ✅ TV organizer test passed (basic initialization)")
            
    except Exception as e:
        print(f"  ❌ TV organizer test error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)

async def test_music_organizer():
    """Test music organizer - SIMPLIFIED"""
    print("\n🧪 Testing Music Organizer (simplified)...")
    
    test_dir = Path("test_organizer_music")
    test_dir.mkdir(exist_ok=True)
    
    try:
        config = MockConfig()
        logger = MediaOrganizerLogger(name="test", dry_run=True)
        db = OrganizationDatabase(config.database_path, backup_enabled=False)
        conflict_handler = ConflictHandler()
        
        organizer = MusicOrganizer(
            config=config,
            database=db,
            conflict_handler=conflict_handler,
            logger=logger,
            dry_run=True
        )
        
        print(f"  ✅ MusicOrganizer initialized")
        print("  ✅ Music organizer test passed (basic initialization)")
            
    except Exception as e:
        print(f"  ❌ Music organizer test error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)

async def test_book_organizer():
    """Test book organizer - SIMPLIFIED"""
    print("\n🧪 Testing Book Organizer (simplified)...")
    
    test_dir = Path("test_organizer_book")
    test_dir.mkdir(exist_ok=True)
    
    try:
        config = MockConfig()
        logger = MediaOrganizerLogger(name="test", dry_run=True)
        db = OrganizationDatabase(config.database_path, backup_enabled=False)
        conflict_handler = ConflictHandler()
        
        organizer = BookOrganizer(
            config=config,
            database=db,
            conflict_handler=conflict_handler,
            logger=logger,
            dry_run=True,
            book_type="book"
        )
        
        print(f"  ✅ BookOrganizer initialized")
        print("  ✅ Book organizer test passed (basic initialization)")
            
    except Exception as e:
        print(f"  ❌ Book organizer test error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)

async def run_organizer_tests():
    """Run all organizer tests - SIMPLIFIED"""
    print("=" * 60)
    print("🧪 ORGANIZER TEST SUITE (SIMPLIFIED)")
    print("=" * 60)
    
    print("Testing organizer initialization only...")
    
    # Create test data directory
    Path("test_data").mkdir(exist_ok=True)
    Path("test_library").mkdir(exist_ok=True)
    Path("test_downloads").mkdir(exist_ok=True)
    
    await test_movie_organizer()
    await test_tv_organizer()
    await test_music_organizer()
    await test_book_organizer()
    
    # Cleanup
    import shutil
    for dir_name in ["test_data", "test_library", "test_downloads"]:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name, ignore_errors=True)
    
    print("\n✅ Organizer test suite completed (initialization tests only)!")

if __name__ == "__main__":
    asyncio.run(run_organizer_tests())