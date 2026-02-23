# Media Organization System

A powerful, automated system for organizing media files (movies, TV shows, anime, music, books, and comics) into standardized library structures compatible with media servers like Plex, Jellyfin, and Emby.

## Features

- **Multi-format Support**: Movies, TV shows, anime, doramas, music, books, and comics
- **Automatic TMDB ID Detection**: Automatically detects TMDB IDs from filename patterns using TMDB API
- **Smart Detection**: Automatically detects media type from filename patterns and folder context
- **Hardlink Support**: Organizes files using hardlinks to save disk space
- **Conflict Resolution**: Configurable strategies (skip, rename, overwrite) for duplicate files
- **Subtitle Management**: Automatically moves and renames subtitle files
- **Daemon Mode**: Continuous monitoring of download folders with configurable intervals
- **Statistics Dashboard**: View organization and mapping statistics
- **PDF to EPUB Conversion**: Optional conversion of PDF ebooks to EPUB format using Calibre
- **MOBI Support**: Full support for Amazon MOBI format with metadata enrichment via Calibre

## Supported Formats

### Video (Requires Manual Mapping)
- Movies: `.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`
- TV Shows/Anime/Doramas: Same formats with episode detection

### Audio (Auto-organized)
- Music: `.mp3`, `.flac`, `.m4a`, `.ogg`, `.opus`, `.aac`, `.wav`

### Books & Comics
- Books: `.epub`, `.pdf`, `.mobi`, `.azw`, `.azw3`
- Comics: `.cbz`, `.cbr`, `.cb7`, `.cbt`

## Installation

### Prerequisites
- Python 3.8+
- qBittorrent (optional, for torrent monitoring)
- Calibre (optional, for PDF to EPUB conversion)

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd media-organizer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment configuration
cp .env.example .env
# Edit .env with your paths and settings


## Configuration

Edit the `.env` file to configure:

### Library Paths
```env
LIBRARY_PATH_MOVIES=/path/to/movies/library
LIBRARY_PATH_TV=/path/to/tv/library
LIBRARY_PATH_ANIMES=/path/to/anime/library
LIBRARY_PATH_DORAMAS=/path/to/dorama/library
LIBRARY_PATH_MUSIC=/path/to/music/library
LIBRARY_PATH_BOOKS=/path/to/books/library
LIBRARY_PATH_COMICS=/path/to/comics/library
```

### Download Paths
```env
DOWNLOAD_PATH_MOVIES=/path/to/movies/downloads
DOWNLOAD_PATH_TV=/path/to/tv/downloads
DOWNLOAD_PATH_ANIMES=/path/to/anime/downloads
DOWNLOAD_PATH_DORAMAS=/path/to/dorama/downloads
DOWNLOAD_PATH_MUSIC=/path/to/music/downloads
DOWNLOAD_PATH_BOOKS=/path/to/books/downloads
DOWNLOAD_PATH_COMICS=/path/to/comics/downloads
```

### TMDB Integration (Optional but Recommended)
```env
TMDB_API_KEY=your_tmdb_api_key_here
```

### qBittorrent Integration (Optional)
```env
QBITTORRENT_ENABLED=true
QBITTORRENT_HOST=http://localhost:8080
QBITTORRENT_USERNAME=admin
QBITTORRENT_PASSWORD=password
QBITTORRENT_CHECK_COMPLETION=true
```

### Processing Priorities
```env
PROCESSING_PRIORITY_MOVIES=1
PROCESSING_PRIORITY_TV=2
PROCESSING_PRIORITY_ANIMES=3
PROCESSING_PRIORITY_DORAMAS=4
PROCESSING_PRIORITY_MUSIC=5
PROCESSING_PRIORITY_BOOKS=9
```

## Usage

### Interactive Mode
```bash
./run.sh organize
```
Presents a menu to select which directory to organize.

### Statistics
```bash
./run.sh stats
```
Shows organization statistics and mapped content.

### Auto-Detection Feature

**TMDB ID IS AUTOMATICALLY DETECTED** for all video files (movies, TV shows, anime, doramas). The system automatically detects TMDB IDs based on filename patterns:

1. The system extracts title and year from the filename
2. It queries the TMDB API to find a matching movie or TV show
3. If found, it organizes the file using the retrieved TMDB ID
4. If auto-detection fails, the file is added to the unorganized list with instructions for renaming

No manual mapping is required - just name your files appropriately and the system will handle the rest!

### Check Unmapped Files
```bash
./run.sh check-unmapped
```
Lists files that require manual mapping.

### Daemon Mode
```bash
# Start daemon
./run-daemon.sh

# Check status
./status-daemon.sh

# Stop daemon
./stop-daemon.sh
```

### Test Configuration
```bash
./run.sh test
```

## File Organization Structure

### Recommended Filename Patterns for Auto-Detection

For optimal auto-detection, use these filename patterns:

#### Movies
- `Movie.Title.(Year).EXT` - e.g., `The.Matrix.1999.mkv`
- `Movie.Title.Year.EXT` - e.g., `The.Matrix.1999.mkv`
- `Movie.Title.(Year).Quality.EXT` - e.g., `The.Matrix.1999.1080p.mkv`

#### TV Shows
- `Series.Title.SXXEXX.EXT` - e.g., `Breaking.Bad.S01E01.mkv`
- `Series.Title.SXX.EXX.EXT` - e.g., `Breaking.Bad.S01.E01.mkv`
- `Series.Title.(Year).SXXEXX.EXT` - e.g., `The.Office.2005.S01E01.mkv`
- `Series.Title.XXxXX.EXT` - e.g., `Stranger.Things.01x01.mkv`

### Movies
```
movies/
├── Movie Title (2020) [tmdbid-12345]/  # TMDB ID in folder name
│   └── Movie Title (2020).mkv
├── Another Movie (2018) [tmdbid-67890]/
│   └── Another Movie (2018).mp4
└── Movie.pt.BR.srt (subtitles)
```

### TV Shows
```
tv/
├── Series Name (2010) [tmdbid-67890]/  # TMDB ID in folder name
│   ├── Season 01/
│   │   ├── Series Name S01E01.mkv
│   │   ├── Series Name S01E02.mkv
│   │   └── Series Name S01E01.pt.srt
│   └── Season 02/
│       └── Series Name S02E01.mkv
```

### Music
```
music/
├── Artist Name/
│   ├── Album Name (2020)/
│   │   ├── 01 - Track Name.mp3
│   │   └── 02 - Another Track.flac
│   └── Singles/
│       └── Single Track.m4a
```

### Books
```
books/
├── Author Name/
│   ├── Book Title (2015)/
│   │   └── Book Title.epub
│   └── Another Book (2018)/
│       └── Another Book.pdf
```

## Manual Mapping System

The system uses `data/manual_mapping.json` to store mappings for movies and TV shows. **TMDB ID is required for all video files**.

### File Structure:
```json
{
    "movies": [
        {
            "file_path": "/path/to/movie.mkv",
            "title_pt": "Title in Original Language",
            "title_en": "Title in English",
            "year": 2020,
            "tmdb_id": 12345,  // REQUIRED
            "category": "movie"
        }
    ],
    "tv": [
        {
            "directory": "/path/to/series/folder",
            "title_pt": "Series Title in Original Language",
            "title_en": "Series Title",
            "year": 2010,
            "category": "tv",
            "structure_type": "complete_series",
            "tmdb_id": 67890  // REQUIRED
        }
    ]
}
```

### TMDB ID Rules:
1. **Required** for all movies, TV shows, anime, and doramas
2. Must be a positive integer
3. Will be included in folder names for media server compatibility
4. Files without TMDB ID will be added to `data/unorganized.json`

## Daemon Mode

The daemon continuously monitors download folders and automatically organizes new files. Configuration:

```env
CHECK_INTERVAL=3600  # Check every hour (seconds)
PROCESSING_PRIORITY_MOVIES=1  # Highest priority
```

Manage the daemon:
```bash
./run-daemon.sh    # Start
./status-daemon.sh # Check status
./stop-daemon.sh   # Stop
tail -f logs/daemon.log  # View logs
```

## Database

The system tracks organized files in `data/organization.json` with:
- File hashes (partial for performance)
- Original and organized paths
- Metadata including TMDB ID
- Statistics
- Failed operations log

Automatic backups are enabled by default (kept for 7 days).

## Unorganized Files

Files that cannot be organized (missing mapping, missing TMDB ID, etc.) are tracked in `data/unorganized.json`. View them with:

```bash
python -m json.tool data/unorganized.json
```

## Conflict Resolution

Configure conflict strategy in `.env`:
```env
CONFLICT_STRATEGY=rename  # skip, rename, or overwrite
CONFLICT_RENAME_PATTERN={name}_{counter}{ext}
CONFLICT_MAX_ATTEMPTS=100
```

## qBittorrent Integration

When enabled, the system checks qBittorrent for completed torrents and only processes files from torrents that are complete. Features:
- Path mapping support (container to host paths)
- Category-based filtering
- Progress verification
- State-based processing

## PDF to EPUB Conversion

Optional feature using Calibre's `ebook-convert`:
- Converts PDF ebooks to EPUB format
- Preserves metadata
- Supports OCR for scanned PDFs
- Configurable output profiles

## Enhanced Book Metadata

New features for improving book metadata:
- Updates embedded metadata in EPUB/PDF/MOBI files using Calibre
- Adds rich metadata like series information, genres, ratings, ISBN
- Improves compatibility with book servers like Kavita
- Available for all book types (books, comics)

## Online Metadata Fetching

New feature for fetching metadata from online sources:
- Fetches book metadata from OpenLibrary and Google Books
- Fetches music metadata from MusicBrainz
- Enriches existing metadata with online information
- Works for books, comics, and music
- Optional feature that can be enabled/disabled

## Smart Book Format Priority

New feature for intelligent book format management:
- Automatically detects duplicate books in different formats
- Prioritizes formats based on configurable priority order
- Skips organizing lower-priority formats when better ones exist
- Default priority: EPUB > MOBI > AZW3 > AZW > PDF

Example: If you have both `Book.epub` and `Book.mobi`, only the EPUB will be organized.

Configuration options:
```env
# Enable metadata enrichment for all book types
ENRICH_BOOK_METADATA=true

# Enable online metadata fetching for books (OpenLibrary, Google Books)
ENRICH_BOOK_METADATA_ONLINE=false  # Set to true to enable online metadata fetching

# Enable online metadata fetching for music (MusicBrainz)
ENRICH_MUSIC_METADATA_ONLINE=false  # Set to true to enable online metadata fetching

# Enable PDF to EPUB conversion
CONVERT_PDF_TO_EPUB=false  # Set to true if you want to convert PDFs to EPUB

# Book format priority (comma-separated, highest to lowest priority)
BOOK_FORMAT_PRIORITY=epub,mobi,azw3,azw,pdf
```

## Enhanced Metadata Quality

Improvements to ensure high-quality metadata:
- Filters out invalid YouTube-generated genres (like "People & Blogs")
- Infers appropriate genres from track titles when invalid genres are detected
- Maintains compatibility with media servers like Kavita and Navidrome
- Preserves original content language while enhancing metadata structure

Configuration options:
```env
# The system automatically filters invalid genres like "People & Blogs"
# No additional configuration needed - this is handled automatically
```

## Project Structure

```
media-organizer/
├── src/
│   ├── core/              # Core system components
│   │   ├── __init__.py
│   │   ├── orchestrator.py    # Main orchestration logic
│   │   ├── main_orchestrator.py # High-level orchestrator implementation
│   │   ├── types.py           # Core data types and enums
│   │   ├── interfaces.py      # Core interfaces definition
│   │   └── validator.py       # Core validation components
│   ├── detection/         # Media detection and classification
│   │   ├── __init__.py
│   │   ├── classifier.py      # Media type classification
│   │   └── scanner.py         # File scanning utilities
│   ├── io/                # Input/Output operations
│   │   ├── __init__.py
│   │   └── concurrency_manager.py # Concurrency control
│   ├── integration/       # External service integrations
│   │   ├── __init__.py
│   │   ├── qbittorrent_client.py   # QBittorrent API client
│   │   └── qbittorrent_validator.py # QBittorrent validation layer
│   ├── organizers/        # Media organizers
│   │   ├── __init__.py
│   │   ├── base.py            # Base organizer class
│   │   ├── movie.py           # Movie organizer (TMDB ID required)
│   │   ├── tv.py              # TV show organizer (TMDB ID required)
│   │   ├── music.py           # Music organizer
│   │   └── book.py            # Book organizer
│   ├── persistence/       # Data persistence
│   │   ├── __init__.py
│   │   ├── database.py        # Database operations
│   │   ├── mapping_db.py      # Manual mapping database
│   │   └── unorganized_db.py  # Unorganized files tracking
│   ├── utils/             # Utility functions
│   │   ├── __init__.py
│   │   ├── file_ops.py        # File operations
│   │   ├── conflict_handler.py # Conflict resolution
│   │   ├── validators.py      # Validation utilities
│   │   └── logger.py          # Logging utilities
│   ├── config/            # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py        # Configuration class
│   ├── metadata/          # Metadata handling
│   │   └── parsers.py         # Media type detection
│   ├── monitors/          # Monitoring components
│   │   └── torrent_monitor.py # Torrent monitoring
│   ├── database.py        # Legacy database operations (deprecated)
│   ├── database_unorganized.py # Legacy unorganized database (deprecated)
│   ├── simple_mapping.py  # Legacy mapping database (deprecated)
│   ├── config.py          # Legacy configuration (deprecated)
│   └── main.py            # CLI entry point
├── data/
│   ├── manual_mapping.json  # User mappings (with TMDB IDs)
│   ├── organization.json    # Database
│   └── unorganized.json    # Failed files
├── logs/                   # Log files
├── tests/                  # Test suite
│   ├── __init__.py
│   ├── test_refactored_system.py # Core system tests
│   └── test_orchestrator_integration.py # Orchestrator integration tests
├── scripts/
│   ├── run-daemon.sh      # Daemon control
│   ├── status-daemon.sh
│   └── stop-daemon.sh
├── .env                   # Configuration
├── .env.example          # Example config
├── requirements.txt      # Dependencies
├── run.sh               # Main runner
└── README.md           # This file
```

## Logging

Logs are stored in `logs/` directory with rotation (50MB max, 5 backups). Different log levels available:
- `DEBUG`: Detailed information
- `INFO`: General operations
- `WARNING`: Non-critical issues
- `ERROR`: Critical failures

## Requirements

See `requirements.txt` for full list. Key dependencies:
- `qbittorrent-api` (optional): qBittorrent integration
- `mutagen`: Audio metadata
- `tinydb`: JSON database
- `python-dotenv`: Environment configuration
- `rich`: Console output and logging
- `click`: CLI interface
- `ebooklib` (optional): EPUB metadata

## License

MIT License - see LICENSE file for details.

## 📋 **Refactored Architecture Overview:**

The media organization system has been refactored to improve maintainability, testability, and extensibility. The new architecture introduces:

### 1. **Modular Design**
- **Core Module**: Contains orchestration logic, types, and interfaces
- **Detection Module**: Handles media classification and file scanning
- **Integration Module**: Manages external service connections (QBittorrent)
- **IO Module**: Controls concurrency and file operations
- **Persistence Module**: Handles data storage and retrieval
- **Organizers Module**: Specialized media organizers

### 2. **Enhanced QBittorrent Validation**
- **Mandatory validation**: Files are checked against QBittorrent completion status before processing
- **State verification**: Ensures downloads are fully completed before organization
- **Connection management**: Robust handling of QBittorrent API connections

### 3. **Concurrency Control**
- **Resource management**: Thread-safe access to file system resources
- **Operation throttling**: Limits simultaneous file operations
- **Lock management**: Prevents race conditions during file operations

### 4. **Improved Architecture Benefits**
- **Maintainability**: Clear separation of concerns makes code easier to understand and modify
- **Testability**: Modular design enables comprehensive unit testing
- **Extensibility**: Well-defined interfaces allow for easy addition of new features
- **Reliability**: Mandatory QBittorrent validation prevents processing of incomplete files
- **Performance**: Concurrency controls optimize resource utilization

### 5. **Core Components**
- `core/orchestrator.py`: Main orchestration logic
- `core/main_orchestrator.py`: High-level orchestrator implementation
- `detection/classifier.py`: Advanced media type classification
- `integration/qbittorrent_validator.py`: QBittorrent validation layer
- `io/concurrency_manager.py`: Concurrency control implementation
- `persistence/database.py`: Database operations with backup support

### 6. **Backward Compatibility**
- All existing functionality is preserved
- Same CLI interface maintained
- Same configuration approach kept
- Existing mapping files remain compatible

The refactored system maintains full compatibility with existing workflows while providing a more robust, scalable foundation for future enhancements.
```

## 📋 **Original Summary of Changes:**

1. **`simple_mapping.py`**: TMDB ID is now required in `add_movie()` and `add_series()`
2. **`movie.py`**: TMDB ID validation before organizing, adds to unorganized list if missing
3. **`tv.py`**: Same validation for series, anime, and doramas
4. **`README.md`**: Documentation updated emphasizing that TMDB ID is required

The system now **will not organize any video without TMDB ID**, exactly as requested! 🎯