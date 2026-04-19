# Architecture

The Media Organizer follows a modular architecture with clear separation of concerns.

## Overview

The system is organized in layers:

```
┌─────────────────────────────────────────┐
│              CLI Layer                   │
│         (click, rich, cli_manager)      │
├─────────────────────────────────────────┤
│           Core Layer                    │
│    (orchestrator, detection, types)     │
├─────────────────────────────────────────┤
│          Services Layer                 │
│        (organizers, playlists)          │
├─────────────────────────────────────────┤
│         Features Layer                  │
│   (genre_guard, metadata, suggestions) │
├─────────────────────────────────────────┤
│       Infrastructure Layer              │
│ (database, link_registry, navidrome)   │
└─────────────────────────────────────────┘
```

## Key Modules

| Module | Description |
|--------|-------------|
| `core/orchestrator.py` | Main workflow coordinator |
| `core/detection.py` | Media classifier and file scanner |
| `services/organizers.py` | Type-specific organization logic |
| `features/genre_guard/` | Genre validation system |
| `infrastructure/database.py` | TinyDB persistence layer |

## Documentation

- [Overview](overview.md) - System design principles
- [Directory Structure](directory-structure.md) - Project layout
- [Core Modules](core-modules.md) - Core components
- [Infrastructure](infrastructure.md) - Infrastructure components
- [Data Flow](data-flow.md) - Processing pipelines
