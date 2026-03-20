#!/usr/bin/env python3
"""Setup test environment with sample files."""

import shutil
from pathlib import Path


def setup_test_environment():
    """Create test directory structure and sample files."""
    test_dir = Path("test_environment")
    downloads = test_dir / "downloads"
    library = test_dir / "library"

    if test_dir.exists():
        shutil.rmtree(test_dir)

    media_types = ["music", "books", "comics"]
    for media_type in media_types:
        (downloads / media_type).mkdir(parents=True, exist_ok=True)
        (library / media_type).mkdir(parents=True, exist_ok=True)

    env_content = f"""# Test Configuration
LIBRARY_PATH_MUSIC={library / 'music'}
LIBRARY_PATH_BOOKS={library / 'books'}
LIBRARY_PATH_COMICS={library / 'comics'}

DOWNLOAD_PATH_MUSIC={downloads / 'music'}
DOWNLOAD_PATH_BOOKS={downloads / 'books'}
DOWNLOAD_PATH_COMICS={downloads / 'comics'}

# Database
DATABASE_PATH=./data/organization.json
DATABASE_BACKUP_ENABLED=true
DATABASE_BACKUP_KEEP_DAYS=7

# Logging
LOG_LEVEL=DEBUG
LOG_FILE=./logs/test.log
LOG_MAX_SIZE_MB=10
LOG_BACKUP_COUNT=3

# Conflict Resolution
CONFLICT_STRATEGY=rename
CONFLICT_RENAME_PATTERN={{name}}_{{counter}}{{ext}}
CONFLICT_MAX_ATTEMPTS=100

# Scheduling
ORGANIZATION_CHECK_INTERVAL=60

# Manual Mapping
MANUAL_MAPPING_ENABLED=true
MANUAL_MAPPING_REQUIRED=true
MANUAL_MAPPING_PATH=./data/manual_mapping.json
MANUAL_MAPPING_BACKUP_ENABLED=true

# Other
MAX_CONCURRENT_FILE_OPS=3
MAX_CONCURRENT_API_CALLS=2
FILE_OP_DELAY_MS=100
DRY_RUN_MODE=false
HEALTH_CHECK_ENABLED=false
"""

    with open(test_dir / ".env.test", "w", encoding="utf-8") as f:
        f.write(env_content)

    create_sample_files(downloads)

    print("✅ Test environment created successfully!")
    print(f"   Test directory: {test_dir.absolute()}")
    print(f"   Downloads: {downloads}")
    print(f"   Library: {library}")

    return test_dir


def create_sample_files(downloads_path):
    """Create sample media files for testing."""
    music_file = downloads_path / "music" / "Artist - Album" / "01 - Song Name.mp3"
    music_file.parent.mkdir(parents=True, exist_ok=True)
    music_file.write_text("Fake music content", encoding="utf-8")

    book_file = downloads_path / "books" / "Sample Book.epub"
    book_file.write_text("Fake book content", encoding="utf-8")

    comic_file = downloads_path / "comics" / "Batman #001.cbz"
    comic_file.write_text("Fake comic content", encoding="utf-8")

    print("✅ Sample test files created")


if __name__ == "__main__":
    setup_test_environment()
