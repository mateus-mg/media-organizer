# Module Reference

## Module Relationships

The system consists of these Python modules organized by responsibility:

```
CLI Layer
├── main.py                # Click commands, app entry point
└── cli_manager.py        # Interactive menus

Core Layer
├── orchestrator.py        # Main workflow coordinator
├── detection.py           # Media classifier, file scanner
├── interfaces.py         # Abstract interfaces
└── types.py              # Core enums and data classes

Services Layer
├── organizers.py          # Type-specific organization logic
└── playlists.py          # Navidrome playlist management

Features Layer
├── genre_guard/           # Genre validation
│   └── core.py
├── metadata/             # Metadata extraction/enrichment
│   └── metadata.py
└── filename_suggestions.py  # AI filename improvements

Infrastructure Layer
├── database.py            # TinyDB persistence
├── link_registry.py       # Hardlink tracking
├── trash_manager.py       # Safe deletion
├── navidrome_client.py    # Subsonic API client
└── playlist_store.py      # Playlist state persistence
```

**Dependencies:**
- `main.py` imports from all layers
- `orchestrator.py` coordinates all other modules
- `organizers.py` uses `genre_guard` and `metadata` for enrichment

---

## main.py

**Purpose:** CLI entry point providing all click commands.

**Key Classes:**
- `MediaOrganizerApp`: Main application class

**Key Commands:**

| Command | Description |
|--------|-------------|
| `process-new-media` | Full organization cycle |
| `organize` | Interactive organize menu |
| `interactive` | Full interactive menu |
| `navidrome-test` | Test Navidrome connection |
| `navidrome-sync-simple` | Sync playlists by filters |
| `music-genre-backfill` | Fix genres in database |
| `suggest-filenames` | Generate filename suggestions |
| `stats` | Show statistics |
| `backup-integrity` | Verify backup integrity |

---

## cli_manager.py

**Purpose:** Interactive menu system using Rich library.

**Key Classes:**
- `CLIManager`: Main CLI controller

**Key Methods:**

| Method | Description |
|--------|-------------|
| `show_main_menu()` | Display main menu loop |
| `show_organize_menu()` | Organization submenu |
| `show_system_info_menu()` | Stats, logs, quality reports |
| `show_genre_catalog_menu()` | Genre catalog management |
| `show_playlist_menu()` | Navidrome playlists |

---

## orchestrator.py

**Purpose:** Main workflow coordinator.

**Key Classes:**
- `Orquestrador`: Main orchestrator
- `FileExistenceValidator`: Check file exists
- `FileTypeValidator`: Check extension is supported
- `IncompleteFileValidator`: Reject incomplete files
- `JunkFileValidator`: Reject promotional/sponsor patterns

**Key Methods:**

| Method | Description |
|--------|-------------|
| `processar_novos_medias()` | Execute full organization cycle |
| `verificar_e_organizar()` | Process single file |
| `obter_estatisticas()` | Get operation statistics |

---

## organizers.py

**Purpose:** Type-specific organization logic implementing `OrganizadorInterface`.

**Key Classes:**
- `BaseOrganizer`: Abstract base class
- `MusicOrganizer`: Audio file organization
- `BookOrganizer`: Book organization
- `ComicOrganizer`: Comic organization
- `LyricsOrganizer`: Lyrics pairing
- `ArtworkOrganizer`: Cover art management
- `RenamerOrganizer`: Batch rename operations

**Music Path Pattern:**
```
{LIBRARY_PATH_MUSIC}/
  {Artist}/
    {Album}/
      {Track Number} - {Title}.ext
```

**Book Path Pattern:**
```
{LIBRARY_PATH_BOOKS}/
  {Author}/
    {Title}.ext
```

**Comic Path Pattern:**
```
{LIBRARY_PATH_COMICS}/
  {Title} ({Year})/
    {Title} ({Year}) - {Series} #{Issue}.ext
```

---

## genre_guard/core.py

**Purpose:** Intelligent genre validation and sanitization.

**Key Classes:**
- `GenreGuard`: Genre validation engine

**Validation Logic:**
1. Normalize input (lowercase, trim)
2. Check exact match in invalid list → REJECT
3. Check exact match in exceptions → ACCEPT
4. Check compound genre → validate each token
5. Apply heuristic scoring for uncertain cases

**Data Files:**
- `data/invalid_music_genres.json` - Blacklist
- `data/suspect_music_genres.json` - Suspicious but kept
- `data/genre_exceptions.json` - Explicit exceptions
- `data/musical_keywords.json` - Valid genre keywords

---

## metadata/metadata.py

**Purpose:** Metadata extraction and online enrichment.

**Key Classes:**
- `MetadataEnricher`: Main enrichment class
- `MetadataResult`: Result dataclass
- `MetadataParser`: Parsing utilities

**Music Enrichment Sources:**
- MusicBrainz - Release/artist IDs, genres
- Last.fm - Genre tags

**Book Enrichment Sources:**
- OpenLibrary - ISBN lookup, cover URLs
- Google Books - Description, categories

---

## database.py

**Purpose:** TinyDB-based persistence for organized media.

**Key Classes:**
- `OrganizationDatabase`: Main database
- `UnorganizedDatabase`: Failed attempts tracking

**Features:**
- Automatic backups before modifications
- Backup rotation (7 days default)
- Thread-safe operations via RLock
- Statistics tracking

**Tables:**
- `media` - All organized media records
- `statistics` - Operation statistics
- `failed_operations` - Failed organization attempts

---

## navidrome_client.py

**Purpose:** Subsonic API client for Navidrome integration.

**Key Classes:**
- `NavidromeClient`: API client
- `NavidromeClientError`: Base error
- `NavidromeAuthError`: Authentication error

**Key Methods:**

| Method | Description |
|--------|-------------|
| `ping()` | Test connection |
| `get_playlists()` | List playlists |
| `create_playlist()` | Create new playlist |
| `sync_playlist()` | Sync playlist contents |

---

## trash_manager.py

**Purpose:** Safe file deletion with quarantine and audit trail.

**Key Classes:**
- `TrashManager`: Trash operations controller

**Key Methods:**

| Method | Description |
|--------|-------------|
| `mover_para_lixeira()` | Move file to quarantine |
| `restaurar()` | Restore from quarantine |
| `esvaziar_lixeira()` | Permanent deletion |
| `obter_itens_lixeira()` | List quarantined items |

**Features:**
- Configurable retention period (30 days default)
- Automatic cleanup of expired items
- Audit trail for all deletions
