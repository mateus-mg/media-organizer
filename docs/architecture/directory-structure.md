# Directory Structure

```
media-organizer/
├── app/                          # Main application source
│   ├── __init__.py
│   ├── main.py                   # CLI entry point (click commands)
│   ├── cli/
│   │   └── cli_manager.py       # Interactive menu system
│   ├── config/
│   │   ├── constants.py         # Extension constants
│   │   └── settings.py           # Configuration manager
│   ├── core/
│   │   ├── detection.py          # Media classifier & file scanner
│   │   ├── interfaces.py         # Abstract interfaces
│   │   ├── orchestrator.py       # Main workflow coordinator
│   │   └── types.py              # Core types and enums
│   ├── features/
│   │   ├── data/                 # Feature data files
│   │   ├── filename_suggestions.py
│   │   ├── genre_guard/          # Genre validation
│   │   └── quality_monitor.py
│   ├── infrastructure/
│   │   ├── database.py           # TinyDB persistence
│   │   ├── deletion_manager.py
│   │   ├── link_registry.py      # Hardlink tracking
│   │   ├── navidrome_client.py   # Subsonic API client
│   │   ├── playlist_store.py
│   │   └── trash_manager.py
│   ├── logging/
│   │   ├── config.py
│   │   └── formatter.py
│   ├── metadata/
│   │   ├── metadata.py            # Metadata extraction/enrichment
│   │   └── artist_genre_cache.py
│   ├── services/
│   │   ├── organizers.py          # Media organizers
│   │   ├── playlists.py
│   │   └── renamer.py
│   ├── utils/
│   │   ├── concurrency.py        # Parallel operations
│   │   ├── helpers.py
│   │   └── value_utils.py
│   └── validators/
│       └── integrations.py
├── data/                          # Runtime data
│   ├── backups/                   # Database backups
│   ├── navidrome/                 # Navidrome state
│   ├── organization.json          # Main database
│   └── *.json                    # Genre lists, caches
├── docs/                          # Documentation
├── logs/                          # Runtime logs
├── tests/                         # Test suite
├── run.sh                         # Launcher script
├── requirements.txt
├── mkdocs.yml                     # Documentation config
└── README.md
```

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `app/` | All Python source code |
| `data/` | Runtime databases and caches |
| `data/backups/` | Versioned JSON backups |
| `logs/` | Rotating log files |
| `tests/` | pytest test suite |
| `docs/` | mkdocs documentation source |
