# Media Organization System

A comprehensive media organization system for music, books, and comics with conflict resolution, genre validation, and schema-based organization.

## Features

- **Hardlink-based organization** — conserves disk space by creating hardlinks to original files
- **Automatic classification** — organizes files by type (music, books, comics) with context-aware logic
- **Companion file management** — organizes lyrics (`.lrc`) alongside music tracks
- **Artwork extraction** — manages cover art and artwork (`.jpg`, `.jpeg`, `.png`, `.webp`) as separate resources
- **Metadata enrichment** — optional online metadata enrichment for music and books
- **Comic schema parsing** — comic organization driven by filename schema and local metadata fields
- **Genre validation & cleanup** — intelligent genre cleaning with Genre Guard module
- **Filename suggestions** — AI-assisted naming for books and comics
- **Metadata quality reports** — detailed analytics on metadata completeness and consistency
- **Conflict resolution** — intelligent handling of duplicate file organization with skip/rename/overwrite strategies
- **Playlist management** — Navidrome integration for dynamic playlist creation and sync
- **Music cycle validation** — album identity verification with genre re-evaluation and normalization

## Supported Formats

- **Audio:** `.mp3`, `.flac`, `.wav`, `.m4a`, `.ogg`, `.opus`, `.aac`, `.wma`, `.m4b`
- **Lyrics:** `.lrc`
- **Artwork:** `.jpg`, `.jpeg`, `.png`, `.webp`
- **Books:** `.epub`, `.pdf`, `.mobi`, `.azw`, `.azw3`
- **Comics:** `.cbz`, `.cbr`, `.cb7`, `.cbt`

## Installation

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Configure your environment variables in `.env` before running.

## Usage

### Interactive Menu (Recommended)

```bash
./run.sh interactive
```

Main menu options:

- `[1]` Organize media files
- `[2]` Filename suggestions
- `[3]` System information
- `[4]` Genre catalog management
- `[5]` Playlists (Navidrome integration)
- `[6]` Exit
- `[9]` Admin: Music genre backfill (only with `ENABLE_ADMIN_BACKFILL_MENU=true`)

### Command-Line Interface

```bash
./run.sh organize                                        # Full organization cycle
./run.sh interactive                                    # Start interactive menu
./run.sh process-new-media                             # Run main media processing cycle
./run.sh preview-music-metadata --path "/path/to/media"
./run.sh music-genre-backfill                          # Preview genre corrections
./run.sh music-genre-backfill --execute                # Apply genre corrections
./run.sh music-metadata-normalize-albums               # Preview album normalization
./run.sh music-metadata-normalize-albums --execute     # Apply album normalization
./run.sh navidrome-test                                # Test Navidrome connectivity
./run.sh navidrome-playlists                           # List management options
./run.sh navidrome-sync-simple --name "Playlist Name" --artist "Artist Name"
./run.sh suggest-filenames --root "/path/to/folder" --media all
./run.sh edit-filename-suggestion --report data/filename_suggestions_report.json --index 0 --new-name "New Name.pdf"
./run.sh apply-filename-suggestions --report data/filename_suggestions_report.json
./run.sh apply-filename-suggestions --report data/filename_suggestions_report.json --execute
./run.sh backup-integrity                              # Verify backup consistency
./run.sh backup-integrity --cleanup                    # Remove old unused backups
./run.sh backfill-book-covers --limit 0
./run.sh backfill-book-years --limit 0
./run.sh stats                                         # Display system statistics
./run.sh test                                          # Run test suite
```

All commands support `--dry-run` flag to preview changes without writing to disk.

## Configuration

Set these required variables in `.env`:

```env
LIBRARY_PATH_MUSIC=/path/to/music/library
LIBRARY_PATH_BOOKS=/path/to/books/library
LIBRARY_PATH_COMICS=/path/to/comics/library

DOWNLOAD_PATH_MUSIC=/path/to/music/downloads
DOWNLOAD_PATH_BOOKS=/path/to/books/downloads
DOWNLOAD_PATH_COMICS=/path/to/comics/downloads
```

Key options:

```env
CONFLICT_STRATEGY=skip                    # skip | rename | overwrite
ENRICH_MUSIC_METADATA_ONLINE=false
ENRICH_BOOK_METADATA_ONLINE=false
ENRICH_BOOK_METADATA_GOOGLE_BOOKS=true
GOOGLE_BOOKS_API_KEY=                     # Required if using Google Books enrichment
BOOK_METADATA_TRUST_MODE=missing_only     # missing_only | replace_with_online
ENABLE_ADMIN_BACKFILL_MENU=false
NAVIDROME_URL=http://localhost:4533
NAVIDROME_USERNAME=admin
NAVIDROME_PASSWORD=                       # Set via environment, never in .env
```

### BOOK_METADATA_TRUST_MODE

- `missing_only` — preserves existing tags and only fills gaps
- `replace_with_online` — replaces main fields with trusted online data when available

### Comic Filename Schema

Comics are organized from filename-derived metadata using a strict schema for acceptance.

Canonical destination format:

`Titulo (Ano) - Serie (opcional) #Edicao.ext`

Examples:

- `Invencivel (2003) #001.cbz`
- `Invencivel (2003) - Biblioteca Galactica #010.cbr`

## Organization Workflow

The main organizing cycle is triggered by:

```bash
./run.sh process-new-media
```

Execution phases:

1. **Scan** — discovers new files in configured download directories
2. **Pre-clean** (music) — removes invalid genres from file tags before processing
3. **Organize** — applies conflict resolution strategy and creates hardlinks
4. **Validate** (music) — detects and reprocesses tracks with invalid genres
5. **Album Recheck** (music) — verifies album consistency (title, artist, year, track numbers)

## Genre Management

Access genre management from the interactive menu via `Genre catalog management`:

### Invalid Genres Catalog

Manage confirmed invalid genre terms:

- List all entries
- Add specific term or regex pattern
- Remove term or pattern

### Musical Keywords

Manage keywords used for genre detection:

- List, add, or remove keywords

### Genre Exceptions

Manage exceptions to standard genre rules:

- List, add, or remove exceptions

All changes are automatically saved to versioned backups in `data/backups/`.

## File Validation

Before organization, files pass through multiple validators to prevent invalid files from being processed:

### File Existence Validator

Ensures source file exists and is accessible.

### File Type Validator

Verifies file extension matches supported formats defined in configuration.

### Incomplete File Validator

Detects partially downloaded or in-progress files:

- `.part` — Firefox/Chrome partial downloads
- `.tmp` — temporary files
- `.!qB`, `.crdownload` — qBittorrent/Chrome incomplete
- `.aria2` — Aria2 download metadata
- `.download` — generic download indicator

These files are skipped automatically until complete.

### Junk File Validator

Filters watermarked, promotional, or low-quality files:

- Watermarked samples: `BLUDV.mp4`, `1XBET.mp4`
- Content samples: `SAMPLE.*`, `TRAILER.*`
- Promotional content: `*PROMO*`, `DINHEIRO_LIVRE*`, `ACESSE*`
- Any file matching configured junk patterns

Configure additional junk patterns via `JUNK_PATTERNS` in your analysis tools.

## Metadata Enrichment

When enabled, the system enriches media metadata from online sources:

### Music Enrichment

#### Data Sources

- **MusicBrainz** — comprehensive music database with album/artist metadata and genre information
- **Last.fm** — user-submitted genre tags and artist information

#### Features

- Automatic genre detection from multiple sources
- Track number validation against authoritative sources
- Album year verification
- Artist name canonicalization
- Rate limiting to respect API limits (1 request/second recommended)
- Cached results to avoid redundant API calls (`data/artist_genre_cache.json`)

#### Configuration

```env
ENRICH_MUSIC_METADATA_ONLINE=false          # Enable online enrichment
MUSICBRAINZ_RATE_LIMIT_DELAY=1.0            # Seconds between requests
LASTFM_API_KEY=                              # Optional Last.fm API key
```

#### Workflow

1. Extract existing metadata from file tags
2. Query online sources for artist/album information
3. Detect genre confidence level
4. Apply genre validation rules (Genre Guard)
5. Update file tags if confident

### Book Enrichment

#### Data Sources

- **OpenLibrary** — free library metadata with ISBN, author, published year
- **Google Books API** — additional title variants and metadata

#### Features

- Author name normalization
- ISBN lookup and verification
- Publication year detection
- Cover art extraction (when allowed)
- Book series identification

#### Configuration

```env
ENRICH_BOOK_METADATA_ONLINE=false           # Enable online enrichment
ENRICH_BOOK_METADATA_GOOGLE_BOOKS=true      # Use Google Books API
GOOGLE_BOOKS_API_KEY=                        # Required for Google Books
BOOK_METADATA_TRUST_MODE=missing_only       # missing_only | replace_with_online
```

## Link Management

The system uses hardlinks to conserve disk space while maintaining organizational structure.

### How Hardlinks Work

- **Hardlink:** Multiple directory entries pointing to same inode (same physical data)
- **Advantage:** Saves disk space; single file content with multiple "copies"
- **Limitation:** Can only hardlink within same filesystem
- **Detection:** Same inode across source and destination confirms hardlink creation

### Link Registry

Tracks all created hardlinks in `data/link_registry.json`:

```json
{
  "device_id": {
    "source_inode": {
      "organized_path": "path/to/organized/file"
    }
  }
}
```

Purpose:

- Detect duplicate organization attempts across different source copies
- Verify hardlink integrity
- Support recovery if hardlinks break
- Allow linking status queries

### Verification

Check hardlink status:

```bash
./run.sh backup-integrity                    # Verify all organized files
./run.sh backup-integrity --cleanup          # Remove orphaned registry entries
```

### Fallback for Cross-Filesystem Organization

If source and destination are on different filesystems:

- System detects hardlink incompatibility
- Falls back to conflict resolution strategy (skip/rename/copy)
- Logs decision for future reference

## Infrastructure Components

### Trash Manager

Safely deletes files that violate organization rules:

- Files quarantined by Genre Guard
- Corrupted or invalid media files
- Detected duplicates

Handles:

- Soft delete to recoverable trash location
- Logging of deletion decisions
- Audit trail for recovery

### Deletion Manager

Coordinates permanent file removal with reversibility options:

- **Soft delete:** Move to trash (recoverable)
- **Hard delete:** Permanent removal from system
- **Decision audit:** Logged decisions for compliance

### Playlist Store

Manages Navidrome playlist state:

- Persistent playlist definitions
- Last sync timestamp
- Track availability tracking
- Playlist synchronization history

### Concurrency Manager

Parallelizes safe file operations:

- Parallel hardlink creation
- Parallel file reading for hashing
- Configurable worker pool size
- Progress tracking across threads

## Quality Monitoring & Recommendations

### Music Quality Dashboard

Accessible via interactive menu `[3] System information` → `[4] Music quality dashboard`:

Analyzes all music tracks for:

- **Metadata completeness:** Presence of essential tags (artist, album, year, track number)
- **Genre validity:** Detected invalid or suspicious genres
- **Album consistency:** Track number sequences, artist uniformity
- **Encoding quality:** Bitrate, sample rate analysis

**Metrics tracked:**

- Total tracks analyzed
- Tracks with complete metadata
- Tracks with missing critical tags
- Invalid genre occurrences
- Suspicious genre detections
- Album identity conflicts

### Genre Quality Report

Detailed genre-specific analysis:

- Most common invalid genres detected
- Genres flagged as suspicious but kept
- Auto-corrected genre terms
- Protected genre exceptions

Access via: `[3] System information` → `[5] Genre quality report (detailed)`

### Filename Suggestion Engine

Generates improved filenames for books and comics based on extracted metadata:

```bash
./run.sh suggest-filenames --root "/path/to/folder" --media all
./run.sh edit-filename-suggestion --report data/filename_suggestions_report.json --index 0 --new-name "Improved Name.pdf"
./run.sh apply-filename-suggestions --report data/filename_suggestions_report.json --execute
```

Features:

- Removes redundant information
- Applies consistent naming patterns
- Preserves file extension
- Supports dry-run preview

## Unorganized Files & Error Recovery

### Tracking Unorganized Files

Files that fail validation or organization are tracked in a separate database for analysis:

```bash
./run.sh interactive
[3] System information → [1] View unorganized files
```

View unorganized files status to:

- Identify problematic files
- Understand why files were skipped
- Decide on manual correction

### Failure Reasons

Common reasons files remain unorganized:

- **Incomplete download:** File still being downloaded (detected by validators)
- **Junk file:** Watermarked sample or promotional content
- **Corrupt metadata:** File has invalid or unreadable tags
- **Conflict unresolved:** Destination already exists with incompatible strategy
- **Filesystem mismatch:** Hardlink attempted across filesystems
- **Permission denied:** Cannot read source or write destination

### Recovery Process

For problematic files:

1. Check file validation output: `./run.sh process-new-media --dry-run`
2. View logs: `./run.sh interactive` → `[3] System information` → `[2] View organization logs`
3. Address root cause (download completion, corrupt file, permission, etc.)
4. Re-run organization cycle

## Logging Configuration

### Log Levels

Configure logging verbosity via environment:

```env
LOG_LEVEL=INFO                    # DEBUG | INFO | WARNING | ERROR | CRITICAL
CONSOLE_LOG_LEVEL=WARNING         # Console output level
LOG_FILE=logs/organizer.log       # Log file path
LOG_MAX_BYTES=10485760            # Max log file size (10 MB)
LOG_BACKUP_COUNT=5                # Rotated backup files retained
```

### Log Content

Main log file (`logs/organizer.log`) includes:

- Organization cycle results (started, ended, statistics)
- File processing decisions (organized, skipped, deleted)
- Genre decisions and quarantine reasons
- Metadata enrichment API calls and results
- Error and warning conditions
- Performance metrics (processing time per file)

### Accessing Logs

View recent logs interactively:

```bash
./run.sh interactive
[3] System information → [2] View organization logs
```

View specific cycle results:

```bash
cat data/genre_guard_cycle_report.json    # Genre decisions from last cycle
cat data/genre_guard_decisions_latest.json # Decision audit trail
```

## Backup & Recovery Strategy

### Automated Backups

System creates automatic backups before modifying critical data:

- **When:** Before applying genre corrections, accepting filename suggestions, managing catalogs
- **Format:** Versioned JSON files prefixed with timestamp
- **Location:** `data/backups/`
- **Retention:** Configurable (default: keep last 30 days)

### Manual Backup

Create a manual backup before major operations:

```bash
cp -r data/organization.json "data/backups/organization_manual_$(date +%Y-%m-%d_%H-%M-%S).json"
cp -r data/link_registry.json "data/backups/link_registry_manual_$(date +%Y-%m-%d_%H-%M-%S).json"
```

### Recovery from Backup

Restore from a specific backup:

```bash
# List available backups
ls -la data/backups/

# Restore main database
cp "data/backups/organization_2026-04-06_10-30-45.json" data/organization.json

# Restore link registry
cp "data/backups/link_registry_2026-04-06_10-30-45.json" data/link_registry.json
```

### Backup Integrity Check

Verify all backups are consistent:

```bash
./run.sh backup-integrity                   # Verify without cleanup
./run.sh backup-integrity --cleanup         # Remove orphaned old backups
```

This validates:

- All file references in database exist or are tracked in registry
- No orphaned hardlinks
- Backup files are readable and valid JSON

## Data Storage

Core database files:

- `data/organization.json` — main database of organized files
- `data/link_registry.json` — tracks hardlink relationships
- `data/invalid_music_genres.json` — list of invalid genre terms
- `data/suspect_music_genres.json` — potentially problematic genres
- `data/genre_exceptions.json` — genre rule exceptions
- `data/musical_keywords.json` — genre detection keywords
- `data/artist_genre_cache.json` — cached artist genre information

Reports and diagnostics:

- `data/genre_guard_cycle_report.json` — genre validation cycle results
- `data/genre_guard_decisions_latest.json` — genre decision audit
- `data/quality_report_latest.json` — metadata quality metrics
- `data/genre_quality_report_latest.json` — genre-specific quality metrics
- `data/filename_suggestions_report.json` — suggested filename changes

Backups and logs:

- `data/backups/` — versioned backups of all data files
- `logs/organizer.log` — system operation log

## Security & Privacy

- **Never commit** `.env` with credentials or API keys to version control
- Data files in `data/` may contain library paths and file metadata
- Credentials should be set as environment variables before runtime
- Database files should be excluded from public repositories

## Troubleshooting

### Quality Dashboard is Empty

The quality dashboard requires prior organization cycles. Run:

```bash
./run.sh process-new-media
```

Then access the system information menu to view metrics.

### Valid Genres Being Removed

If legitimate genres are being invalidated:

1. Check `data/genre_exceptions.json` for rule conflicts
2. Check `data/musical_keywords.json` for keyword patterns
3. Use the `Genre catalog management` menu to add exceptions
4. Review `data/genre_guard_cycle_report.json` for detailed diagnostics

### File Organization Issues

If files aren't organizing correctly:

- Use `./run.sh process-new-media --dry-run` to preview changes
- Verify directory permissions and disk space
- Check conflict resolution strategy in `.env`
- Review `logs/organizer.log` for detailed error messages

## Testing

Run the test suite with:

```bash
./run.sh test
```

This executes automated tests for all core functionality.
