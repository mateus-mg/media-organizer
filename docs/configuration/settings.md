# Settings (`config/settings.py`)

Configuration manager using python-dotenv.

## Class: Config

```python
class Config:
    def __init__(self, env_path: Path | None = None)
    def is_valid() -> bool
    def reload()
```

## Configuration Loading

1. Load from `.env` file in project root
2. Validate required variables
3. Provide defaults for optional variables

## Key Categories

### Library Paths

| Variable | Description |
|----------|-------------|
| `LIBRARY_PATH_MUSIC` | Music library root |
| `LIBRARY_PATH_BOOKS` | Books library root |
| `LIBRARY_PATH_COMICS` | Comics library root |

### Download Paths

| Variable | Description |
|----------|-------------|
| `DOWNLOAD_PATH_MUSIC` | Music download directory |
| `DOWNLOAD_PATH_BOOKS` | Books download directory |
| `DOWNLOAD_PATH_COMICS` | Comics download directory |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PATH` | `data/organization.json` | Main database |
| `DATABASE_BACKUP_ENABLED` | `true` | Enable backups |
| `DATABASE_BACKUP_KEEP_DAYS` | `7` | Backup retention |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FILE` | `logs/organizer.log` | Log file path |
| `LOG_MAX_SIZE_MB` | `50` | Max log file size |
| `LOG_BACKUP_COUNT` | `5` | Backup count |
