# Architecture Overview

## System Design

The Media Organizer follows a **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│  Entry Points                                               │
│  ├── run.sh (Bash wrapper → Python CLI)                     │
│  └── Python CLI (app/main.py)                              │
├─────────────────────────────────────────────────────────────┤
│  CLI Layer                                                  │
│  └── cli_manager.py (Rich-based interactive menus)          │
├─────────────────────────────────────────────────────────────┤
│  Core Layer                                                 │
│  ├── orchestrator.py (Main workflow coordinator)            │
│  ├── detection.py (Media classifier, file scanner)        │
│  └── types.py (Core enums and data classes)                │
├─────────────────────────────────────────────────────────────┤
│  Services Layer                                             │
│  ├── organizers.py (Type-specific organization logic)       │
│  └── playlists.py (Playlist management)                      │
├─────────────────────────────────────────────────────────────┤
│  Features Layer                                             │
│  ├── genre_guard/ (Genre validation)                        │
│  ├── metadata/ (Metadata extraction/enrichment)             │
│  └── filename_suggestions.py (AI filename improvements)      │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure Layer                                       │
│  ├── database.py (TinyDB persistence)                       │
│  ├── link_registry.py (Hardlink tracking)                   │
│  ├── trash_manager.py (Safe deletion)                       │
│  └── navidrome_client.py (Subsonic API client)             │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Workflow Orchestration Pattern

The system uses a central **Orquestrador** (orchestrator) that coordinates the entire media organization workflow:
1. Scan download directories
2. Filter already organized files
3. Validate file completeness
4. Classify media type
5. Enrich metadata online
6. Create hardlinks in library structure
7. Track in database

### 2. Hardlink Strategy

- Source and destination on same filesystem = hardlink (saves disk space)
- Cross-filesystem = fallback to copy
- Same inode detected = skip duplicate organization

### 3. Genre Guard System

Instead of maintaining an 800+ genre whitelist, Genre Guard uses:
- Musical Keywords (548 terms) - covers 99%+ of valid genres
- Genre Exceptions (7 items) - niche genres not in keywords
- Invalid Genres - explicitly blacklisted terms

### 4. Configuration Storage

Configuration is stored in `.env` file following standard Python practices:

```
media-organizer/
├── .env                 # User configuration (gitignored)
├── data/                # Runtime databases
│   ├── organization.json    # Main database
│   ├── link_registry.json    # Hardlink tracking
│   └── backups/             # Database backups
└── logs/                # Runtime logs
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Primary Language | Python 3.9+ | Core logic |
| CLI Framework | Click | Command-line interface |
| UI Framework | Rich | Terminal UI |
| Database | TinyDB | JSON-based document storage |
| Audio Metadata | mutagen, music-tag | ID3/metadata extraction |
| Book Metadata | PyPDF2, ebooklib | PDF/EPUB extraction |
| HTTP Client | aiohttp, requests | Online metadata enrichment |
| Logging | Python logging | Runtime diagnostics |

## Supported Media Types

| Type | Extensions | Organization Pattern |
|------|------------|---------------------|
| Music | .mp3, .flac, .wav, .m4a, .ogg, .opus, .aac, .wma, .m4b | `Artist/Album/Track.ext` |
| Books | .epub, .pdf, .mobi, .azw, .azw3 | `Author/Title.ext` |
| Comics | .cbz, .cbr, .cb7, .cbt | `Title (Year) - Series #Issue.ext` |
| Lyrics | .lrc | Matched to music tracks |
| Artwork | .jpg, .jpeg, .png, .webp | Matched to albums/books |
