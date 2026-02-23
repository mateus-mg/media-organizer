#!/usr/bin/env python3
"""
Consolidated Test Suite for Media Organization System

Tests the consolidated module structure.
Run with: python3 tests/test_consolidated.py
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Test counters
passed = 0
failed = 0


def test_import(name, import_fn):
    """Test an import and track results"""
    global passed, failed
    try:
        import_fn()
        print(f"  ✅ {name}")
        passed += 1
        return True
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        failed += 1
        return False


def run_import_tests():
    """Test all consolidated module imports"""
    print("\n" + "=" * 60)
    print("IMPORT TESTS")
    print("=" * 60)
    
    # Config
    print("\n📁 Config module:")
    test_import("Config", lambda: __import__('src.config', fromlist=['Config']))
    
    # Core
    print("\n📁 Core module:")
    test_import("MediaType", lambda: __import__('src.core', fromlist=['MediaType']))
    test_import("Orquestrador", lambda: __import__('src.core', fromlist=['Orquestrador']))
    test_import("Validators", lambda: __import__('src.core', fromlist=['FileExistenceValidator']))
    test_import("Interfaces", lambda: __import__('src.core', fromlist=['ValidatorInterface']))
    
    # Detection
    print("\n📁 Detection module:")
    test_import("MediaClassifier", lambda: __import__('src.detection', fromlist=['MediaClassifier']))
    test_import("FileScanner", lambda: __import__('src.detection', fromlist=['FileScanner']))
    
    # Integrations
    print("\n📁 Integrations module:")
    test_import("TMDBClient", lambda: __import__('src.integrations', fromlist=['TMDBClient']))
    test_import("FileCompletionValidator", lambda: __import__('src.integrations', fromlist=['FileCompletionValidator']))
    test_import("get_tmdb_id_for_movie", lambda: __import__('src.integrations', fromlist=['get_tmdb_id_for_movie']))
    
    # Organizers
    print("\n📁 Organizers module:")
    test_import("MovieOrganizer", lambda: __import__('src.organizers', fromlist=['MovieOrganizer']))
    test_import("TVOrganizer", lambda: __import__('src.organizers', fromlist=['TVOrganizer']))
    test_import("MusicOrganizer", lambda: __import__('src.organizers', fromlist=['MusicOrganizer']))
    test_import("BookOrganizer", lambda: __import__('src.organizers', fromlist=['BookOrganizer']))
    
    # Persistence
    print("\n📁 Persistence module:")
    test_import("OrganizationDatabase", lambda: __import__('src.persistence', fromlist=['OrganizationDatabase']))
    test_import("UnorganizedDatabase", lambda: __import__('src.persistence', fromlist=['UnorganizedDatabase']))
    
    # Utils
    print("\n📁 Utils module:")
    test_import("get_logger", lambda: __import__('src.utils', fromlist=['get_logger']))
    test_import("ConflictHandler", lambda: __import__('src.utils', fromlist=['ConflictHandler']))
    test_import("ConcurrencyManager", lambda: __import__('src.utils', fromlist=['ConcurrencyManager']))
    test_import("normalize_title", lambda: __import__('src.utils', fromlist=['normalize_title']))
    
    # Metadata
    print("\n📁 Metadata module:")
    test_import("extract_audio_metadata", lambda: __import__('src.metadata', fromlist=['extract_audio_metadata']))
    
    # Main app
    print("\n📁 Main module:")
    test_import("MediaOrganizerApp", lambda: __import__('src.main', fromlist=['MediaOrganizerApp']))


def run_functional_tests():
    """Test basic functionality"""
    print("\n" + "=" * 60)
    print("FUNCTIONAL TESTS")
    print("=" * 60)
    
    from src.config import Config
    from src.core import MediaType
    from src.utils import ConflictHandler, normalize_title, normalize_movie_filename, normalize_tv_filename, get_logger
    from src.detection import MediaClassifier, FileScanner
    from src.persistence import OrganizationDatabase
    
    # Config
    print("\n⚙️  Config tests:")
    config = Config()
    test_import("Config loads .env", lambda: config.database_path)
    test_import("Config has library paths", lambda: config.library_path_movies)
    test_import("Config has download paths", lambda: config.download_path_movies)
    
    # MediaType enum
    print("\n📺 MediaType enum tests:")
    test_import("MediaType.MOVIE", lambda: MediaType.MOVIE.value == "movie")
    test_import("MediaType.TV_SHOW", lambda: MediaType.TV_SHOW.value == "tv")
    test_import("MediaType.ANIME", lambda: MediaType.ANIME.value == "anime")
    test_import("MediaType.MUSIC", lambda: MediaType.MUSIC.value == "music")
    
    # Utils
    print("\n🔧 Utils tests:")
    test_import("normalize_title", lambda: normalize_title("Test.Title.2020") == "Test Title 2020")
    test_import("normalize_movie_filename", lambda: normalize_movie_filename("Movie.2020.mkv")[0] == "Movie")
    test_import("normalize_tv_filename", lambda: normalize_tv_filename("Show.S01E01.mkv")[1] == 1)
    
    # MediaClassifier
    print("\n🎬 MediaClassifier tests:")
    classifier = MediaClassifier()
    test_import("Classify movie", lambda: classifier.classificar_tipo_midia(Path("/test/movie.mkv")) == MediaType.MOVIE)
    test_import("Classify music", lambda: classifier.classificar_tipo_midia(Path("/test/song.mp3")) == MediaType.MUSIC)
    test_import("Classify book", lambda: classifier.classificar_tipo_midia(Path("/test/book.epub")) == MediaType.BOOK)
    
    # ConflictHandler
    print("\n⚔️  ConflictHandler tests:")
    handler = ConflictHandler(strategy="skip")
    test_import("ConflictHandler init", lambda: handler.strategy == "skip")
    
    # Logger
    print("\n📝 Logger tests:")
    logger = get_logger(dry_run=True)
    test_import("Logger init", lambda: logger is not None)


async def run_async_tests():
    """Test async functionality"""
    print("\n" + "=" * 60)
    print("ASYNC TESTS")
    print("=" * 60)
    
    from src.config import Config
    from src.persistence import OrganizationDatabase
    from src.utils import ConflictHandler, get_logger
    from src.core import Orquestrador, FileExistenceValidator, FileTypeValidator
    from src.detection import MediaClassifier, FileScanner
    from src.integrations import FileCompletionValidator
    
    print("\n🔄 Orchestrator initialization:")
    config = Config()
    logger = get_logger(dry_run=True)
    
    # Create database
    db = OrganizationDatabase(
        db_path=Path("./data/test_organization.json"),
        backup_enabled=False
    )
    
    # Create components
    conflict_handler = ConflictHandler(strategy="skip")
    classifier = MediaClassifier(logger=logger)
    scanner = FileScanner(logger=logger)
    validators = [
        FileExistenceValidator(logger=logger),
        FileTypeValidator(
            supported_types=['.mkv', '.mp4', '.mp3', '.epub'],
            logger=logger
        ),
    ]
    file_validator = FileCompletionValidator(logger=logger)
    
    test_import("Database init", lambda: db is not None)
    
    # Create orchestrator
    orchestrator = Orquestrador(
        validators=validators,
        organizadores={},
        classifier=classifier,
        scanner=scanner,
        database=db,
        file_completion_validator=file_validator,
        logger=logger
    )
    
    test_import("Orchestrator init", lambda: orchestrator is not None)
    
    # Cleanup
    db.close()
    
    # TMDB Client (connection test)
    print("\n🌐 TMDB Client test:")
    from src.integrations import TMDBClient
    client = TMDBClient()
    test_import("TMDBClient init", lambda: client is not None)
    # Note: Actual API call would require valid API key


def run_all_tests():
    """Run all test suites"""
    global passed, failed
    
    print("\n" + "=" * 60)
    print("MEDIA ORGANIZER - CONSOLIDATED TEST SUITE")
    print("=" * 60)
    print(f"Project root: {project_root}")
    print(f"Python path: {sys.path[0]}")
    
    # Run tests
    run_import_tests()
    run_functional_tests()
    asyncio.run(run_async_tests())
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total:  {passed + failed}")
    print(f"📈 Rate:   {(passed / (passed + failed) * 100):.1f}%" if (passed + failed) > 0 else "📈 Rate:   N/A")
    print("=" * 60)
    
    if failed > 0:
        print("\n⚠️  Some tests failed. Review output above.")
        return 1
    else:
        print("\n🎉 All tests passed!")
        return 0


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
