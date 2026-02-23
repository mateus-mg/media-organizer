#!/usr/bin/env python3
"""
Setup test environment with sample files
"""

import os
import shutil
from pathlib import Path
import json

def setup_test_environment():
    """Create test directory structure and sample files"""
    
    # Base paths
    test_dir = Path("test_environment")
    downloads = test_dir / "downloads"
    library = test_dir / "library"
    
    # Clean previous test environment
    if test_dir.exists():
        shutil.rmtree(test_dir)
    
    # Create directories
    media_types = ['movies', 'tv', 'anime', 'dorama', 'music', 'books', 'audiobooks', 'comics']
    
    for media_type in media_types:
        (downloads / media_type).mkdir(parents=True, exist_ok=True)
        (library / media_type).mkdir(parents=True, exist_ok=True)
    
    # Create test .env file
    env_content = f"""# Test Configuration
LIBRARY_PATH_MOVIES={library / 'movies'}
LIBRARY_PATH_TV={library / 'tv'}
LIBRARY_PATH_ANIMES={library / 'anime'}
LIBRARY_PATH_DORAMAS={library / 'dorama'}
LIBRARY_PATH_MUSIC={library / 'music'}
LIBRARY_PATH_BOOKS={library / 'books'}
LIBRARY_PATH_AUDIOBOOKS={library / 'audiobooks'}
LIBRARY_PATH_COMICS={library / 'comics'}

DOWNLOAD_PATH_MOVIES={downloads / 'movies'}
DOWNLOAD_PATH_TV={downloads / 'tv'}
DOWNLOAD_PATH_ANIMES={downloads / 'anime'}
DOWNLOAD_PATH_DORAMAS={downloads / 'dorama'}
DOWNLOAD_PATH_MUSIC={downloads / 'music'}
DOWNLOAD_PATH_BOOKS={downloads / 'books'}
DOWNLOAD_PATH_AUDIOBOOKS={downloads / 'audiobooks'}
DOWNLOAD_PATH_COMICS={downloads / 'comics'}

# qBittorrent (disabled for tests)
QBITTORRENT_ENABLED=false

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
CHECK_INTERVAL=300
ORGANIZATION_CHECK_INTERVAL=60

# Processing Priorities
PROCESSING_PRIORITY_MOVIES=1
PROCESSING_PRIORITY_TV=2
PROCESSING_PRIORITY_ANIMES=3
PROCESSING_PRIORITY_DORAMAS=4
PROCESSING_PRIORITY_MUSIC=5
PROCESSING_PRIORITY_BOOKS=9

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
    
    with open(test_dir / ".env.test", "w") as f:
        f.write(env_content)
    
    # Create sample test files
    create_sample_files(downloads)
    
    print("✅ Test environment created successfully!")
    print(f"   Test directory: {test_dir.absolute()}")
    print(f"   Downloads: {downloads}")
    print(f"   Library: {library}")
    
    return test_dir

def create_sample_files(downloads_path):
    """Create sample media files for testing"""
    
    # Sample movie file
    movie_file = downloads_path / "movies" / "Inception.2010.1080p.BluRay.mkv"
    movie_file.write_text("Fake movie content for testing")
    
    # Sample TV show files
    tv_dir = downloads_path / "tv" / "Breaking.Bad.S01"
    tv_dir.mkdir(parents=True, exist_ok=True)
    
    for i in range(1, 4):
        episode = tv_dir / f"Breaking.Bad.S01E{i:02d}.mkv"
        episode.write_text(f"Fake episode {i} content")
    
    # Sample anime file
    anime_file = downloads_path / "anime" / "[SubsPlease] Attack on Titan - 01.mkv"
    anime_file.write_text("Fake anime content")
    
    # Sample music file
    music_file = downloads_path / "music" / "Artist - Album" / "01 - Song Name.mp3"
    music_file.parent.mkdir(parents=True, exist_ok=True)
    music_file.write_text("Fake music content")
    
    # Sample book file
    book_file = downloads_path / "books" / "Sample Book.epub"
    book_file.write_text("Fake book content")
    
    # Sample audiobook file
    audiobook_dir = downloads_path / "audiobooks" / "Audiobook Title"
    audiobook_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 3):
        chapter = audiobook_dir / f"Chapter {i:02d}.mp3"
        chapter.write_text(f"Fake audiobook chapter {i}")
    
    # Sample comic file
    comic_file = downloads_path / "comics" / "Batman #001.cbz"
    comic_file.write_text("Fake comic content")
    
    print("✅ Sample test files created")

if __name__ == "__main__":
    setup_test_environment()