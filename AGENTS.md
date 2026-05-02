# Media Organization System - Agent Knowledge Base

**Generated:** 2026-05-03 00:03:05 WEST  
**Commit:** 3cde5e1  
**Branch:** main  
**Commits:** 74 (since 2026-01-09)

## OVERVIEW

Python CLI application for organizing media files (music, books, comics) with hardlink-based organization, genre validation, Navidrome integration, and conflict resolution. Uses async-first architecture with TinyDB for JSON storage.

## STRUCTURE

```
media-organizer/
├── app/                    # Main Python source (20k lines)
│   ├── main.py            # CLI entry point (1367 lines, click-based)
│   ├── cli/               # Interactive menu system
│   ├── core/              # Orchestration, validators, detection
│   ├── services/          # Media organizers (Music, Book, Comic, etc.)
│   ├── features/          # Genre Guard, Filename Suggestions, Smart Playlists
│   ├── infrastructure/    # Database, Navidrome client, Link Registry
│   ├── config/            # Settings management
│   ├── metadata/          # MusicBrainz, Google Books enrichment
│   ├── validators/        # File validation logic
│   ├── logging/           # Logging setup
│   └── utils/             # Helpers, value utilities
├── tests/                 # Unit & integration tests (7k lines)
├── data/                  # JSON databases, backups, reports
├── docs/                  # MkDocs documentation
├── logs/                  # Log files
├── run.sh                 # Entry point wrapper (bash)
└── requirements.txt       # Dependencies (no pyproject.toml)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Entry point | `app/main.py` | Click CLI with 20+ commands, async orchestration |
| Organization logic | `app/services/organizers.py` | 5441 lines - Music, Book, Comic, Lyrics, Artwork organizers |
| Orchestration | `app/core/orchestrator.py` | `Orquestrador` class, validators |
| Smart Playlists | `app/features/smart_playlists/` | Query parser, builder, validators for Navidrome |
| Genre validation | `app/features/genre_guard/core.py` | Invalid genre detection & correction |
| Navidrome client | `app/infrastructure/navidrome_client.py` | Subsonic API integration |
| Link registry | `app/infrastructure/link_registry.py` | Hardlink tracking system |
| Database | `app/infrastructure/database.py` | TinyDB wrapper |
| Config | `app/config/settings.py` | 420-line Config class with ~50 properties |
| Metadata | `app/metadata/metadata.py` | MusicBrainz, Last.fm, Google Books APIs |

## CONVENTIONS

### Entry Point
```bash
./run.sh <command>      # Shell wrapper (sets PYTHONPATH, venv)
python -m app.main      # Direct Python execution
```

### Testing
- **Framework:** Python stdlib `unittest` (NOT pytest)
- **Runner:** `python tests/run_all_tests.py`
- **Pattern:** `test_*.py` files in `tests/`

### Configuration
- **No pyproject.toml** - uses `.env` file + `requirements.txt`
- **Environment-based:** All config in `.env` (see `.env.example`)
- **Config class:** `app/config/settings.py` with type coercion

### CLI Framework
- **Click** library (decorator-based commands)
- Commands defined in `app/main.py` via `@cli.command()`
- Interactive menu via `app/cli/cli_manager.py`

### Code Organization
- **Interfaces:** Abstract base classes in `app/core/interfaces.py`
- **Types:** Dataclasses/enums in `app/core/types.py`
- **Portuguese names:** `Orquestrador`, `organizar`, `format_datetime_br`
- **Async-first:** Heavy use of `asyncio` throughout

## ANTI-PATTERNS (THIS PROJECT)

### FORBIDDEN

1. **Never use bare `except:`**
   ```python
   # WRONG - catches SystemExit, KeyboardInterrupt
   except:
       pass
   ```
   **Found:** `app/infrastructure/deletion_manager.py:150`

2. **Never commit `.env` files**
   - `.env` contains credentials/API keys
   - Always use `.env.example` as template
   - Enforced by `.gitignore`

3. **Never skip dry-run for destructive ops**
   - All destructive operations support `--dry-run`
   - Always preview before executing

### DISCOURAGED

1. **Minimize bare `except Exception:`**
   - 46 instances across 15 files (existing debt)
   - Prefer specific exception types
   - Never catch `Exception` without logging

2. **Avoid hardcoding paths**
   - Use `Config` class properties
   - Never assume directory structure

### GUARDRAILS

1. **Dry-run mode** - All destructive operations support `--dry-run`
2. **Trash system** - Soft delete with restore capability
3. **Link registry** - Tracks all hardlinks to prevent data loss
4. **Automatic backups** - Database backed up before modifications
5. **Confirmation prompts** - Deletion requires user confirmation

## UNIQUE STYLES

### Naming Conventions
- **Mixed language:** English (public API) + Portuguese (internal)
- **Examples:** `Orquestrador.organizar()`, `format_datetime_br()`

### Hardlink-Based Architecture
- Core design uses hardlinks to conserve disk space
- Source files hardlinked to organized library
- `link_registry.json` tracks all created links
- Cross-filesystem fallback to copy/skip

### Genre Guard System
- Sophisticated genre validation module
- Invalid genre detection with cycle reports
- Genre exceptions database (`data/genre_exceptions.json`)
- Auto-corrects suspicious genres

### Smart Playlists
- Custom query language for dynamic playlists
- `.nsp` file format for playlist definitions
- Navidrome integration for sync
- Query parser in `app/features/smart_playlists/query_parser.py`

## COMMANDS

```bash
# Development
./run.sh interactive                    # Interactive menu
./run.sh process-new-media             # Full organization cycle
./run.sh process-new-media --dry-run   # Preview mode

# Testing
python tests/run_all_tests.py          # Run all tests
./run.sh test                          # Via wrapper

# Documentation
mkdocs serve                           # Preview docs
mkdocs gh-deploy                       # Deploy to GitHub Pages

# Utilities
./run.sh backup-integrity              # Verify database
./run.sh backup-integrity --cleanup    # Remove orphans
```

## DEPENDENCIES

**Core:** click, python-dotenv, rich, tinydb, mutagen  
**Metadata:** aiohttp, requests, asyncio-throttle  
**Books:** PyPDF2, ebooklib, (optional) comicbox  
**Music:** music-tag  

## NOTES

### No Standard Python Packaging
- No `pyproject.toml`, `setup.py`, or `tox.ini`
- Direct `requirements.txt` dependency management
- Virtual environment in `venv/` or `.venv/`

### Data Storage
- **JSON-based** using TinyDB (not SQLite)
- Main database: `data/organization.json`
- Link registry: `data/link_registry.json`
- Genre data: `data/invalid_music_genres.json`
- Backups: `data/backups/` (auto-versioned)

### MkDocs Documentation
- Material theme with mkdocstrings
- Python docstrings: Google style
- Deployed to GitHub Pages

### Integration Points
- **Navidrome:** Subsonic API for playlists
- **MusicBrainz:** Music metadata enrichment
- **Google Books:** Book metadata enrichment
- **Last.fm:** Artist genre information
