# 🗂️ Media Organization System

A lightweight, efficient, and cross-platform system for automatic organization of digital media files. Fully compatible with Jellyfin servers without relying on Jellyfin or paid services.

## 📋 Features

- ✅ **Automatic Organization** - Continuously monitors download folders for new media
- ✅ **Hardlink Support** - Zero disk space duplication using hardlinks
- ✅ **Jellyfin Compatible** - Perfect naming structure for Jellyfin recognition
- ✅ **Rate Limiting** - Prevents system overload with configurable limits
- ✅ **Dry-Run Mode** - Test operations safely before applying changes
- ✅ **Conflict Resolution** - Configurable strategies (skip, rename, overwrite)
- ✅ **Health Check Endpoint** - HTTP endpoint for monitoring system status
- ✅ **Automatic Backups** - JSON database with automatic backup rotation
- ✅ **Cross-Platform** - Works on Linux, Windows, and macOS
- ✅ **Smart Subtitle Handling** - Automatically processes and renames subtitle files
- ✅ **qBittorrent Integration** - Monitors torrent completion status
- ✅ **Music Automation Integration** - Syncs with existing music download system

## 🎯 Supported Media Types

- **Movies** - Organized by title and year with TMDB IDs
- **TV Shows** - Organized by season and episode
- **Anime** - Dedicated structure for anime series
- **Doramas** - Korean/Asian drama organization
- **Music** - Artist/Album structure with playlist syncing
- **Books** - Organized by author and title
- **Audiobooks** - Separate organization from ebooks
- **Comics** - CBZ/CBR support with series tracking

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd media-organizer
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# OR
venv\Scripts\activate     # On Windows
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
nano .env  # Edit configuration with your paths and API keys
```

## ⚙️ Configuration

Edit `.env` file with your settings:

### Essential Settings

```bash
# Library paths (where organized media will be stored)
LIBRARY_PATH_MOVIES="/path/to/library/movies"
LIBRARY_PATH_TV="/path/to/library/tv"
LIBRARY_PATH_ANIMES="/path/to/library/animes"
LIBRARY_PATH_MUSIC="/path/to/library/musics"

# Download paths (where system monitors for new files)
DOWNLOAD_PATH_MOVIES="/path/to/downloads/movies"
DOWNLOAD_PATH_TV="/path/to/downloads/tv"
DOWNLOAD_PATH_TORRENTS="/path/to/downloads/torrents"
```

### TMDB API (Optional but Recommended)

Get a free API key at: https://www.themoviedb.org/settings/api

```bash
TMDB_API_KEY="your_api_key_here"
TMDB_USE_FALLBACK_PARSING="true"  # Use filename parsing if API fails
```

### Rate Limiting (New Feature)

```bash
MAX_CONCURRENT_FILE_OPS="3"         # Max simultaneous file operations
MAX_CONCURRENT_API_CALLS="2"        # Max simultaneous API calls
FILE_OP_DELAY_MS="100"              # Delay between operations (ms)
```

### Conflict Resolution (New Feature)

```bash
CONFLICT_STRATEGY="skip"            # Options: skip, rename, overwrite
CONFLICT_RENAME_PATTERN="{name}_{counter}{ext}"
```

### Health Check (New Feature)

```bash
HEALTH_CHECK_ENABLED="true"
HEALTH_CHECK_HOST="127.0.0.1"
HEALTH_CHECK_PORT="8765"
```

## 📖 Usage

### Interactive CLI (Coming Soon)

```bash
python src/main.py
```

### Dry-Run Mode (Test Without Changes)

```bash
python src/main.py --dry-run
```

### Start with Health Check

```bash
python src/main.py --health-check
```

### Manual Organization

```bash
python src/main.py organize
```

## 📂 File Organization Structure

### Movies
```
movies/
└── Movie Name (Year) [tmdbid-12345]/
    ├── Movie Name (Year).mp4
    ├── Movie Name (Year).en.srt
    └── Movie Name (Year).pt.br.forced.srt
```

### TV Shows / Anime / Doramas
```
tv/
└── Series Name (Year) [tmdbid-1396]/
    ├── Season 01/
    │   ├── Series Name S01E01.mkv
    │   └── Series Name S01E01.en.srt
    └── Season 02/
        └── Series Name S02E01.mkv
```

### Music
```
musics/
└── Artist Name/
    └── Album Name/
        ├── 01 - Track Name.flac
        ├── 02 - Track Name.flac
        └── folder.jpg
```

### Books
```
books/
├── audiobooks/
│   └── Author Name/
│       └── Book Title.mp3
├── books/
│   └── Author Name/
│       └── Book Title (Year)/
│           └── Book Title.epub
└── comics/
    └── Series Name (Year)/
        └── Series Name #001.cbz
```

## 🔧 Core Components

### Already Implemented

1. ✅ **Configuration System** (`src/config.py`)
   - Environment variable loading
   - Validation of paths and settings
   - Support for all configuration options

2. ✅ **Logger** (`src/utils/logger.py`)
   - Colorized console output with Rich
   - File logging with rotation
   - Dry-run mode support
   - Special indicators for conflicts and rate limiting

3. ✅ **Rate Limiter** (`src/rate_limiter.py`)
   - Semaphores for concurrent operations
   - Token bucket algorithm for API throttling
   - Configurable limits per service
   - Statistics tracking

4. ✅ **Conflict Handler** (`src/utils/conflict_handler.py`)
   - Three strategies: skip, rename, overwrite
   - File comparison by hash
   - Unique filename generation

5. ✅ **Database** (`src/database.py`)
   - JSON-based with TinyDB
   - Automatic backup system
   - Backup rotation (keep last 7 days)
   - Statistics tracking
   - Failed operation logging

6. ✅ **File Operations** (`src/utils/file_ops.py`)
   - Cross-platform hardlink creation
   - File hash calculation (SHA256)
   - File stability checking
   - Subtitle detection and renaming
   - Safe directory creation

7. ✅ **Validators** (`src/utils/validators.py`)
   - Path validation
   - File type detection
   - Filename sanitization
   - Cross-platform compatibility checks

### In Progress

- 🔄 **Metadata Parsers** - Extract info from filenames
- 🔄 **TMDB Client** - Fetch movie/TV IDs
- 🔄 **Organizers** - Media-specific organization logic
- 🔄 **Monitors** - File system and torrent monitoring
- 🔄 **Health Check Server** - HTTP monitoring endpoint
- 🔄 **CLI Interface** - Interactive menu system

## 🎨 New Features Highlights

### 1. Rate Limiting

Prevents system overload by limiting:
- Concurrent file operations (default: 3)
- API calls per second (TMDB: 4/s, Jellyfin: 10/s)
- Configurable delays between operations

```python
# Automatic rate limiting in all operations
async with rate_limiter.file_operation():
    create_hardlink(source, dest)
```

### 2. Dry-Run Mode

Test everything safely without modifying files:

```bash
python src/main.py --dry-run

# Output example:
[DRY-RUN] Would create folder: /library/movies/Inception (2010)/
[DRY-RUN] Would create hardlink: Inception.mkv -> Inception (2010).mkv
[DRY-RUN] Simulation complete: 1 file would be organized
```

### 3. Conflict Resolution

Choose how to handle existing files:

- **Skip**: Leave existing file, don't create hardlink
- **Rename**: Create with unique name (Movie_2.mkv)
- **Overwrite**: Replace existing file (use with caution!)

### 4. Health Check Endpoint

Monitor system status via HTTP:

```bash
# Check if system is running
curl http://localhost:8765/health
{
  "status": "UP",
  "timestamp": "2026-01-04T14:30:00Z",
  "uptime_seconds": 3600
}

# Get statistics
curl http://localhost:8765/stats
{
  "total_files_organized": 1250,
  "movies": 450,
  "space_saved_gb": 0
}
```

### 5. Automatic Database Backups

Database automatically backs up:
- Before critical operations
- Timestamped backups
- Automatic cleanup (keep last 7 days)
- Easy restore from any backup

## 🔒 Security

- Health check endpoint binds to localhost by default
- All file operations are atomic
- No execution of untrusted code
- Validation of all file paths
- Safe filename sanitization

## 📊 Project Status

**Current Phase**: Core Implementation Complete

- ✅ Phase 1: Project structure and configuration
- ✅ Phase 2: Core utilities (logger, validators, rate limiter)
- ✅ Phase 3: Database with automatic backups
- ✅ Phase 4: File operations and conflict handling
- 🔄 Phase 5: Metadata parsing and TMDB integration (Next)
- 🔄 Phase 6: Media organizers (Movie, TV, Music, Books)
- 🔄 Phase 7: Monitoring system (File system, qBittorrent)
- 🔄 Phase 8: Jellyfin integration
- 🔄 Phase 9: CLI interface
- 🔄 Phase 9
## 🤝 Contributing

Contributions are welcome! Please ensure:
- All code and documentation in English
- Follow existing code style
- Add tests for new features
- Update documentation

## 📝 License

[Your License Here]

## 🙏 Acknowledgments

- Built with [Rich](https://github.com/Textualize/rich) for beautiful CLI output
- Uses [TinyDB](https://github.com/msiemens/tinydb) for lightweight JSON storage
- TMDB API for movie/TV metadata IDs
- Inspired by Jellyfin's organization standards

## 📞 Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Note**: This system is designed to complement, not replace, your existing media management workflow. It focuses on organization and does not download metadata or images - that's Jellyfin's job!
