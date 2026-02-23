# 🗂️ Media Organization System - Development Instructions

## 📁 Project Overview
Develop a 100% free, lightweight, efficient, and cross-platform system for automatic organization and local metadata management of digital media, fully compatible with Jellyfin servers without relying on Jellyfin or paid services.

**Deployment**: This system runs **locally as a Python application** (not containerized). Uses virtual environment (venv) for dependency isolation.

## 🌐 Language Policy
**IMPORTANT**: All documentation and scripts MUST be in English.
- ✅ **MUST**: Write all code comments, variable names, and function names in English
- ✅ **MUST**: Write all documentation (README, instructions, comments) in English
- ✅ **MUST**: Write all log messages and error messages in English
- ❌ **MUST NOT**: Use any language other than English in code or documentation
- ❌ **MUST NOT**: Mix languages in the same project

## 🎯 Core Requirements

### 1. Cross-Platform Compatibility
- Must work on Linux, Windows, and MacOS
- Use platform-agnostic libraries and paths
- Handle filesystem differences transparently

### 2. Intelligent Automated Organization
- Process download folders via scheduled execution (cron/systemd timer) for: movies, series, doramas, anime, music, books, comics
- Evaluate destination folders and only organize new, unprocessed files
- Use **hardlinks** exclusively to save disk space (no file duplication)
- Never reprocess already organized media (maintain JSON database)
- Handle subtitle files (.srt, .ass, .vtt) correctly - rename and move with corresponding videos

### 3. File Organization Standards (Jellyfin-Compatible)
Based on existing library structure at `/media/mateus/Servidor/containers/media/library/`:

#### **Movies**
```
movies/
└── Movie Name (Year) [tmdbid-12345]/
    ├── Movie Name (Year).mp4
    ├── Movie Name (Year).en.srt
    ├── Movie Name (Year).pt.br.forced.srt
    ├── poster.jpg
    └── backdrop.jpg
```
**Rules:**
- Folder name: `Movie Name (Year) [tmdbid-id]` (ID optional but recommended)
- File name: Same as folder name for main video file
- Multiple versions: `Movie Name (Year) - 2160p.mp4` (space-hyphen-space format)
- 3D videos: Add `.3D.FTAB.mp4` or similar tags
- Extras: Use subfolders (`trailers/`, `behind the scenes/`) or file suffixes (`-trailer.mp4`)

#### **TV Shows, Anime, Doramas**
```
tv/  # or animes/, doramas/
└── Series Name (Year)/
    ├── Season 00/
    │   └── Series Name S00E01.mkv
    ├── Season 01/
    │   ├── Series Name S01E01.mkv
    │   ├── Series Name S01E01.en.srt
    │   └── Series Name S01E01-thumb.jpg
    └── poster.jpg
```
**Rules:**
- Series folder: `Series Name (Year)` **(Year is REQUIRED - system must add if missing)**
- Season folders: `Season 01`, `Season 02` (padded with zeros)
- Episode files: `Series Name S01E01.ext` **(NO hyphen before S01E01)**
- Specials: Place in `Season 00/`
- Episode detection: Support patterns (Ep01, E01, Episode 1, 01)

#### **Music**
```
musics/
└── Artist Name/
    └── Album Name/
        ├── 01 - Track Name.flac
        ├── 02 - Track Name.flac
        ├── folder.jpg
        └── Artist Name - Track Name.lrc
```
**Rules:**
- Structure: `Artist/Album/Tracks`
- Track naming: `## - Track Name.ext` (optional but organized)
- Metadata: Preserve embedded ID3/Vorbis tags
- Lyrics: `.lrc` files with same base name as track
- **Integration**: This folder connects with Music Automation system database

#### **Books, Audiobooks, Comics**
```
library/
├── books/
│   └── Author Name/
│       └── Book Title (Year)/
│           ├── Book Title.epub
│           ├── metadata.opf
│           └── cover.jpg
├── audiobooks/
│   └── [Author or Title]/
│       └── Book Title.mp3
└── comics/
    └── Series Name (Year)/
        ├── Series Name #001.cbz
        └── ComicInfo.xml
```
**Rules:**
- **Books**: `library/books/Author/Title (Year)/` structure
- **Audiobooks**: `library/audiobooks/Title/` (all MP3s together)
- **Comics**: `library/comics/Series (Year)/Issue.cbz` with ComicInfo.xml
- Each book gets its own subfolder
- Comics: Include year of first issue in folder name
- **PDF to EPUB**: Converted EPUB files go to `books/` structure, PDF stays in downloads

### 4. Local Metadata Management

#### **System Focus: Organization ONLY**
This system is a **file organizer**, not a metadata manager:
- ✅ **Does**: Organize files into proper folder structures
- ✅ **Does**: Add IDs to folder names for Jellyfin identification
- ✅ **Does**: Rename and move subtitle files correctly
- ✅ **Does**: Clean and normalize metadata in music files (ID3 tags)
- ✅ **Does**: Generate ComicInfo.xml for comics
- ✅ **Does**: Detect language and update book metadata
- ❌ **Does NOT**: Download images (posters, backdrops, covers)
- ❌ **Does NOT**: Generate NFO files
- ❌ **Does NOT**: Manage or update metadata after organization
- ❌ **Does NOT**: Sync with Jellyfin API

#### **Metadata Sources (Minimal - IDs Only)**
The system uses TMDB API **only for obtaining IDs** to add to folder names:
- Monitor download folders for each media type
- Check download completion (torrent clients or file analysis)
- Only process fully downloaded media
- Wait for Music Automation to complete before processing music

**Download Sources Supported:**
1. **Torrent files** - qBittorrent (Docker)
   - **Integration Method**: qBittorrent Web API (v2)
   - **Authentication**: Username/password login via `/api/v2/auth/login`
   - **Monitoring**: Periodic polling of `/api/v2/torrents/info` (every 30 seconds)
   - **Status Check**: Only process torrents with state `seeding` or `pausedUP` (100% complete)
   - **File Location**: Get actual file paths from `/api/v2/torrents/files?hash=<hash>`
   - **Configuration Required**:
     - Enable Web UI in qBittorrent settings
     - Set Web UI port (default: 8080)
     - Create username/password for API access
     - Optional: Bypass authentication for localhost/subnet
   - **Python Library**: `qbittorrent-api` (official wrapper)
   
2. **Manual downloads** - Direct file placement
   - User manually places files in download folders
   - System detects and processes when file is complete
   
3. **Music Automation** - Automated Spotify/Soulseek downloads
   - System monitors music download folder
   - Reads `downloaded.json` for track metadata
   - Waits for Music Automation to mark track as complete

**Completion Detection:**
- Check file size stability (no changes for 30 seconds)
- For torrents: Query qBittorrent API for completion status
- For Music Automation: Check `downloaded.json` status field
- Skip files with `.part`, `.tmp`, `.!qB` extensions

### 7. Local Database & Logging
**Database Format: JSON (Required)**

**File**: `organization.json` (TinyDB or pure JSON)
- **Must be JSON format** - No SQL databases
- Simple, human-readable, easy to backup
- Complete system information in single file:
```json
{
  "version": "1.0.0",
  "last_updated": "2026-01-04T10:30:00Z",
  
  "media": {
    "sha256_file_hash": {
      "original_path": "/downloads/movies/Inception.2010.mkv",
      "original_filename": "Inception.2010.1080p.BluRay.x264.mkv",
      "original_size_bytes": 2147483648,
      "organized_path": "/library/movies/Inception (2010) [tmdbid-27205]/Inception (2010).mkv",
      "media_type": "movie",
      "media_subtype": null,
      "processed_date": "2026-01-04T10:15:00Z",
      "last_checked": "2026-01-04T10:15:00Z",
      "file_exists": true,
      "hardlink_created": true,
      "metadata": {
        "title": "Inception",
        "year": 2010,
        "tmdb_id": 27205,
        "imdb_id": "tt1375666"
      },
      "subtitles": [
        {
          "path": "/library/movies/Inception (2010) [tmdbid-27205]/Inception (2010).en.srt",
          "language": "en"
        }
      ],
      "errors": []
    },
    "another_hash": {
      "original_path": "/downloads/tv/Breaking.Bad.S01E01.mkv",
      "original_filename": "Breaking.Bad.S01E01.1080p.mkv",
      "original_size_bytes": 1073741824,
      "organized_path": "/library/tv/Breaking Bad (2008) [tmdbid-1396]/Season 01/Breaking Bad S01E01.mkv",
      "media_type": "tv",
      "media_subtype": "series",
      "processed_date": "2026-01-04T09:30:00Z",
      "last_checked": "2026-01-04T09:30:00Z",
      "file_exists": true,
      "hardlink_created": true,
      "metadata": {
        "series_title": "Breaking Bad",
        "year": 2008,
        "season": 1,
        "episode": 1,
        "episode_title": "Pilot",
        "tmdb_id": 1396
      },
      "subtitles": [],
      "jellyfin_item_id": null,
      "
  },
  
  "statistics": {
    "total_files_organized": 1250,
    "movies_organized": 450,
    "series_organized": 320,
    "animes_organized": 180,
    "doramas_organized": 45,
    "music_organized": 200,
    "books_organized": 35,
    "audiobooks_organized": 15,
    "comics_organized": 5,
    "total_size_bytes": 5497558138880,
    "total_size_gb": 5120,
    "space_saved_bytes": 0,
    "failed_operations": 12,
    "last_organization_run": "2026-01-04T10:30:00Z",
    "jellyfin_playlists_synced": 25,
    "last_playlist_sync": "2026-01-04T09:00:00Z"
  "failed_operations": [
    {
      "timestamp": "2026-01-03T15:20:00Z",
      "file_path": "/downloads/movies/corrupted_file.mkv",
      "error_type": "FileCorrupted",
      "error_message": "Unable to read file metadata",
      "retry_count": 3
    }
  ],
  
  "monitoring": {
    "last_scan": "2026-01-04T10:30:00Z",
    "folders_monitored": [
      "/downloads/movies",
      "/downloads/tv",
      "/downloads/animes",
      "/downloads/doramas",
      "/downloads/music",
      "/downloads/books",
      "/downloads/torrents"
    ],
    "active_downloads": 3,
    "pending_organization": 5
  },
  
  "torrent_tracking": {
    "torrent_hash_123abc": {
      "name": "Movie.2024.1080p",
      "status": "downloading",
      "progress": 0.75,
      "download_path": "/downloads/torrents/Movie.2024.1080p",
      "added_date": "2026-01-04T08:00:00Z",
      "completed_date": null,
      "organized": false
    }
  }
}
```

**Logging:**
- Detailed execution logs with summary/detailed modes
- Track: operations, failures, skipped media, sync status
- Visual indicators for different operation types

## 🛠️ Technical Requirements

### Python Environment
- **Python Version**: 3.12.3
- **Environment**: Use `venv` (virtual environment)
  ```bash
  python3.12 -m venv venv
  source venv/bin/activate  # Linux/Mac
  venv\Scripts\activate     # Windows
  ```

### Dependencies
```
# Core libraries
python-dotenv            # Load configuration from .env file
tinydb                   # JSON database (simple and lightweight)

# CLI interface
click or rich           # Interactive CLI menus

# File operations
python-hardlink         # Cross-platform hardlinks

# Media monitoring
qbittorrent-api         # Query qBittorrent for torrent status (optional)

# Audio/Music
mutagen                 # Read audio tags (ID3/Vorbis) for organization

# Metadata (minimal)
# - TMDB API for IDs only (requires free API key)
# - No image downloading libraries needed
# - No metadata file generation libraries needed
```

### Configuration
Single configuration file (`.env`):
```bash
# Library Paths
LIBRARY_PATH_MOVIES="/media/mateus/Servidor/containers/media/library/movies"
LIBRARY_PATH_TV="/media/mateus/Servidor/containers/media/library/tv"
LIBRARY_PATH_ANIMES="/media/mateus/Servidor/containers/media/library/animes"
LIBRARY_PATH_DORAMAS="/media/mateus/Servidor/containers/media/library/doramas"
LIBRARY_PATH_MUSIC="/media/mateus/Servidor/containers/media/library/musics"
LIBRARY_PATH_BOOKS="/media/mateus/Servidor/containers/media/library/books"
LIBRARY_PATH_AUDIOBOOKS="/media/mateus/Servidor/containers/media/library/audiobooks"
LIBRARY_PATH_COMICS="/media/mateus/Servidor/containers/media/library/comics"

# Download Paths
DOWNLOAD_PATH_MOVIES="/media/mateus/Servidor/containers/media/downloads/movies"
DOWNLOAD_PATH_TV="/media/mateus/Servidor/containers/media/downloads/tv"
DOWNLOAD_PATH_ANIMES="/media/mateus/Servidor/containers/media/downloads/animes"
DOWNLOAD_PATH_DORAMAS="/media/mateus/Servidor/containers/media/downloads/doramas"
DOWNLOAD_PATH_MUSIC="/media/mateus/Servidor/containers/media/downloads/musics"
DOWNLOAD_PATH_BOOKS="/media/mateus/Servidor/containers/media/downloads/books"
DOWNLOAD_PATH_AUDIOBOOKS="/media/mateus/Servidor/containers/media/downloads/audiobooks"
DOWNLOAD_PATH_COMICS="/media/mateus/Servidor/containers/media/downloads/comics"
DOWNLOAD_PATH_TORRENTS="/media/mateus/Servidor/containers/media/downloads/torrents"

# TMDB API (used ONLY for extracting IDs, not for downloading metadata or images)
# When registering: Use GitHub repo URL or "http://localhost" as Application URL
# TMDB accepts personal/local projects - no public URL needed
TMDB_API_KEY="8dabc8071598ec954d06fe602fc69627"
TMDB_USE_FALLBACK_PARSING="true"  # Use filename parsing if TMDB API fails

# Music Automation Integration
MUSIC_AUTOMATION_DB_PATH="/media/mateus/Servidor/scripts/music-automation/data/downloaded.json"

# qBittorrent (Docker)
# API endpoints used:
# - POST /api/v2/auth/login - Authentication
# - GET /api/v2/torrents/info - List all torrents
# - GET /api/v2/torrents/files?hash=<hash> - Get torrent file list
# - GET /api/v2/torrents/properties?hash=<hash> - Get torrent details
QBITTORRENT_ENABLED="true"
QBITTORRENT_HOST="http://localhost:8080"
QBITTORRENT_USERNAME="admin"
QBITTORRENT_PASSWORD="^eZA@x58YSyHrq"
QBITTORRENT_WATCH_FOLDER="/media/mateus/Servidor/containers/media/downloads/torrents"
QBITTORRENT_CHECK_COMPLETION="true"
QBITTORRENT_STATES_TO_PROCESS="seeding,pausedUP"  # Process only completed torrents
QBITTORRENT_MIN_PROGRESS="1.0"  # 100% download complete

# Scheduling
ORGANIZATION_CHECK_INTERVAL="300"  # Seconds (5 minutes) - check for new files

# Database
DATABASE_PATH="./data/organization.json"  # JSON database file
```

## 🖥️ CLI Interface

### Interactive Menu Structure
```
=== Media Organization System ===

1. Start/Stop Automatic Monitoring
2. Force Organization of New Media
3. System Configuration
   a. Edit folder paths
   b. Configure API keys (TMDB)
   c. Set Jellyfin API credentials
4. View Logs & Reports
   a. Recent operations
   b. Error summary
   c. Organization statistics
5. Database Management
   a. View organized media
   b. Remove entries
   c. Check for problems
6. Exit
```

### Key Functions
- **Scheduled execution**: Run via cron/systemd timer with configurable intervals
- **Manual organization**: One-time scan and organization
- **Configuration**: Single file, CLI editable
- **Logs**: Filterable by date, type, media type
- **Search**: Find media by name, type, status
## 🔄 Operation Flow

### For Movies/Shows:
1. Monitor download folder → Detect completed file (torrent/manual)
2. Verify file completion (size stable, no .part extension)
3. Parse filename for title/year
4. Search TMDB for ID only (if API available)
5. Create destination folder structure with TMDB ID if found
6. Create hardlink with proper naming
7. Move subtitle files with proper naming
8. Update database

**Example:**
```
Downloads: /downloads/movies/Inception.2010.1080p.BluRay.x264.mkv
Organized: /library/movies/Inception (2010) [tmdbid-27205]/Inception (2010).mkv
```

### For TV/Anime/Doramas:
1. Monitor download folder → Detect completed episodes
2. Parse folder/file names for series name, season, episode
3. Search TMDB for series ID (if API available)
4. Create series/season folder structure with ID
5. Create hardlinks for all episodes
6. Move subtitle files
7. Update database

**Example:**
```
Downloads: /downloads/animes/Demon.Slayer.S01E01.mkv
Organized: /library/animes/Demon Slayer (2019) [tmdbid-85937]/Season 01/Demon Slayer S01E01.mkv
```

### For Music (Integrated):
1. Detect new files in Music Automation download folder
2. Organize into `musics/Artist/Album/` structure
3. Read Music Automation database for metadata
4. Update organization database with clean ID3 tags

### MUST:
- Use hardlinks exclusively (no file copying)
- Maintain full Jellyfin naming compatibility
- Handle subtitles with language/flag codes
- Integrate with existing Music Automation database
- Support existing library structure without renaming root folders
- Add year to series folders if missing
- Provide clear English CLI interface
- Log all operations in English

### MUST NOT:
- Duplicate files (use hardlinks)
- Reprocess already organized files
- Rename existing library root folders (`movies/`, `tv/`, etc.)
- Create `.nfo` files that conflict with Jellyfin scrapers
- Use paid services or APIs
- Depend on Jellyfin server for metadata
- Implement complex metadata update/refresh systems (unnecessary with good organization)

## 📊 Testing Requirements
- Unit tests for file operations, hardlink creation
- Test with existing library structure
- Verify Music Automation database integration
- Cross-platform file operation tests

---

**Note**: This system complements but does not replace the Music Automation system. It focuses on file organization only, while Music Automation handles the download process from Spotify/Soulseek.