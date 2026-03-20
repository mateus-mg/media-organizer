# Media Organization System

Media organizer focused on `music`, `books`, and `comics`.

## Features
- Organize files using hardlinks (saves disk space).
- Classify supported media by extension and metadata.
- Organize `.lrc` lyrics files together with corresponding music tracks.
- Manual execution only (no background service).
- Interactive CLI menus for organize, renamer, and stats.
- Optional metadata enrichment for music and books.

## Supported Formats
- Music: `.mp3`, `.flac`, `.m4a`, `.ogg`, `.opus`, `.aac`, `.wav`, `.m4b`
- Lyrics: `.lrc`
- Books: `.epub`, `.pdf`, `.mobi`, `.azw`, `.azw3`
- Comics: `.cbz`, `.cbr`, `.cb7`, `.cbt`

## Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Main Commands
```bash
./run.sh interactive         # Full interactive menu
./run.sh organize            # Open organize submenu
./run.sh process-new-media   # Run one full manual cycle
./run.sh renamer             # Open renamer submenu
./run.sh stats               # Show organization stats
./run.sh test                # Validate config/database access
```

## Manual Operation Model
All execution is manual. To process new files, run:

```bash
./run.sh process-new-media
```

This command scans configured download folders and organizes what is found in a single cycle.

## Configuration
Set your paths in `.env`:

```env
LIBRARY_PATH_MUSIC=/path/to/library/music
LIBRARY_PATH_BOOKS=/path/to/library/books
LIBRARY_PATH_COMICS=/path/to/library/comics

DOWNLOAD_PATH_MUSIC=/path/to/downloads/music
DOWNLOAD_PATH_BOOKS=/path/to/downloads/books
DOWNLOAD_PATH_COMICS=/path/to/downloads/comics
```

Optional metadata features:

```env
ENRICH_MUSIC_METADATA_ONLINE=false
ENRICH_BOOK_METADATA_ONLINE=false
ENRICH_BOOK_METADATA_GOOGLE_BOOKS=true
GOOGLE_BOOKS_API_KEY=
BOOK_METADATA_TRUST_MODE=missing_only
```

Note: when using Google Books enrichment, providing `GOOGLE_BOOKS_API_KEY` is recommended. Without it, Google may return quota/rate-limit errors (`429`/`403`) and no results will be returned.

If your embedded book metadata is polluted/unreliable, set `BOOK_METADATA_TRUST_MODE=replace_with_online` to overwrite core metadata fields with reliable online matches.

## Data and Logs
- Database: `data/organization.json`
- Backups: `data/backups/`
- Logs: `logs/organizer.log`

## Notes
- Conflict behavior is controlled by `CONFLICT_STRATEGY` in `.env` (`skip`, `rename`, `overwrite`).
- Lyrics duplicate handling uses the same conflict strategy and file identity checks (hash/inode) to avoid duplicate copies.
- Lyrics without a matching audio file are sent to `LIBRARY_PATH_MUSIC/_lyrics_unmatched/` using content-hash filenames to prevent duplicates.
- The project no longer supports lifecycle commands for background service management.
