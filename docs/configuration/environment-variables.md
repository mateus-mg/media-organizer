# Environment Variables

Complete reference for all configuration variables.

## Quick Reference

```bash
# Library Paths
LIBRARY_PATH_MUSIC=/path/to/music
LIBRARY_PATH_BOOKS=/path/to/books
LIBRARY_PATH_COMICS=/path/to/comics

# Download Paths
DOWNLOAD_PATH_MUSIC=/path/to/downloads/music
DOWNLOAD_PATH_BOOKS=/path/to/downloads/books
DOWNLOAD_PATH_COMICS=/path/to/downloads/comics

# Conflict Resolution
CONFLICT_STRATEGY=rename

# Metadata Enrichment
ENRICH_MUSIC_METADATA_ONLINE=true
ENRICH_BOOK_METADATA_ONLINE=true
MUSIC_METADATA_API_DELAY_SECONDS=1.0

# Navidrome
NAVIDROME_ENABLED=false
NAVIDROME_BASE_URL=http://localhost:4533
NAVIDROME_USERNAME=admin
NAVIDROME_PASSWORD=changeme

# Database
DATABASE_PATH=data/organization.json
DATABASE_BACKUP_ENABLED=true
DATABASE_BACKUP_KEEP_DAYS=7

# Trash
TRASH_ENABLED=true
TRASH_PATH=/path/to/trash
TRASH_RETENTION_DAYS=30

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/organizer.log
LOG_MAX_SIZE_MB=50
LOG_BACKUP_COUNT=5
```

## Alphabetical List

| Variable | Required | Default |
|----------|----------|---------|
| `DATABASE_BACKUP_ENABLED` | No | `true` |
| `DATABASE_BACKUP_KEEP_DAYS` | No | `7` |
| `DATABASE_PATH` | No | `data/organization.json` |
| `DOWNLOAD_PATH_BOOKS` | Yes | - |
| `DOWNLOAD_PATH_COMICS` | Yes | - |
| `DOWNLOAD_PATH_MUSIC` | Yes | - |
| `ENABLE_QUALITY_MONITOR` | No | `false` |
| `ENRICH_BOOK_METADATA_ONLINE` | No | `true` |
| `ENRICH_MUSIC_METADATA_ONLINE` | No | `true` |
| `LIBRARY_PATH_BOOKS` | Yes | - |
| `LIBRARY_PATH_COMICS` | Yes | - |
| `LIBRARY_PATH_MUSIC` | Yes | - |
| `LOG_BACKUP_COUNT` | No | `5` |
| `LOG_FILE` | No | `logs/organizer.log` |
| `LOG_LEVEL` | No | `INFO` |
| `LOG_MAX_SIZE_MB` | No | `50` |
| `MUSIC_METADATA_API_DELAY_SECONDS` | No | `1.0` |
| `NAVIDROME_API_VERSION` | No | `1.16.1` |
| `NAVIDROME_BASE_URL` | No | - |
| `NAVIDROME_ENABLED` | No | `false` |
| `NAVIDROME_PASSWORD` | No | - |
| `NAVIDROME_USERNAME` | No | - |
| `TRASH_ENABLED` | No | `true` |
| `TRASH_PATH` | No | `data/trash` |
| `TRASH_RETENTION_DAYS` | No | `30` |
| `CONFLICT_STRATEGY` | No | `rename` |
