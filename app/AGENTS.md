# App Module - Agent Knowledge Base

**Path:** `app/`  
**Purpose:** Main source code for Media Organization System

## STRUCTURE

```
app/
├── main.py              # CLI entry point (1367 lines)
├── cli/                 # Interactive menu system
│   └── cli_manager.py   # Menu orchestration (1937 lines)
├── core/                # Core logic
│   ├── orchestrator.py  # Orquestrador class, validators
│   ├── detection.py     # FileScanner, MediaClassifier
│   ├── types.py         # Dataclasses & enums
│   └── interfaces.py    # Abstract base classes
├── services/            # Media organizers
│   ├── organizers.py    # Music, Book, Comic organizers (5441 lines)
│   └── playlists.py     # Playlist management (644 lines)
├── features/            # Advanced features
│   ├── genre_guard/     # Genre validation
│   ├── smart_playlists/ # Query parser & builder
│   ├── filename_suggestions.py
│   └── quality_monitor.py
├── infrastructure/      # System infrastructure
│   ├── database.py      # TinyDB wrapper
│   ├── link_registry.py # Hardlink tracking
│   ├── navidrome_client.py
│   ├── trash_manager.py
│   └── deletion_manager.py
├── config/              # Configuration
│   └── settings.py      # Config class (421 lines)
├── metadata/            # Metadata enrichment
│   └── metadata.py      # MusicBrainz, Google Books (1441 lines)
├── validators/          # File validators
├── logging/             # Logging setup
└── utils/               # Utility functions
```

## KEY MODULES

| Module | Lines | Purpose |
|--------|-------|---------|
| `services/organizers.py` | 5441 | Music, Book, Comic, Lyrics, Artwork, Renamer |
| `cli/cli_manager.py` | 1937 | Interactive menu system |
| `main.py` | 1367 | Click CLI commands |
| `metadata/metadata.py` | 1441 | Online metadata enrichment |
| `core/orchestrator.py` | 669 | Orquestrador & validators |

## CONVENTIONS

### Imports
```python
# Standard pattern in this codebase
from app.core import MediaType, Orquestrador
from app.config import Config
from app.utils.helpers import ConflictHandler
from app.infrastructure.database import format_datetime_br
```

### Async Patterns
- Most organizers are async: `async def organizar(self, ...)`
- Use `asyncio.gather()` for parallel operations
- Concurrency control via `app/utils/concurrency.py`

### Portuguese Naming
Core classes use Portuguese names:
- `Orquestrador` (not Orchestrator)
- `organizar()` (not organize)
- `obter_tipo_midia()` (not get_media_type)

### Type Hints
- Full type annotations preferred
- Uses `from __future__ import annotations` in some files
- Custom types in `app/core/types.py`

## TESTING

Test files mirror app structure:
- `tests/test_organizers_unit.py` → `app/services/organizers.py`
- `tests/test_detection_unit.py` → `app/core/detection.py`

Run tests:
```bash
python tests/run_all_tests.py
```

## INTEGRATION POINTS

- **Database:** All modules use `OrganizationDatabase` from `infrastructure/`
- **Config:** Environment variables via `Config` class
- **Logging:** Custom logger via `app/logging/get_logger`
- **Validation:** Chain of validators in `core/orchestrator.py`

## ANTI-PATTERNS SPECIFIC TO THIS MODULE

1. **Large files:** `organizers.py` is 5441 lines - avoid adding more; prefer splitting
2. **Mixed languages:** Portuguese internal names are intentional; maintain consistency
3. **Bare except Exception:** Existing debt; prefer specific exceptions for new code
