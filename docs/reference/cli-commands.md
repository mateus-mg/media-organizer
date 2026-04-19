# CLI Commands Reference

Detailed reference for all CLI commands.

## Command: process-new-media

Processes new media files from download directories.

```bash
./run.sh process-new-media [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview changes without executing |
| `--media-type TYPE` | Process specific type (music/book/comic) |
| `--verbose` | Enable verbose output |

### Examples

```bash
# Process all new media
./run.sh process-new-media

# Preview without executing
./run.sh process-new-media --dry-run

# Process only music
./run.sh process-new-media --media-type music
```

## Command: organize

Opens interactive organization menu.

```bash
./run.sh organize
```

## Command: interactive

Opens full interactive menu with all operations.

```bash
./run.sh interactive
```

## Command: music-genre-backfill

Fixes genres in the database.

```bash
./run.sh music-genre-backfill [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--execute` | Apply changes (default is preview) |
| `--dry-run` | Preview changes |

## Command: suggest-filenames

Generates filename improvement suggestions.

```bash
./run.sh suggest-filenames
```

## Command: apply-filename-suggestions

Applies filename suggestions.

```bash
./run.sh apply-filename-suggestions [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--execute` | Apply changes (default is preview) |
| `--dry-run` | Preview changes |

## Command: navidrome-test

Tests Navidrome connection.

```bash
./run.sh navidrome-test
```

## Command: navidrome-sync-simple

Syncs playlists to Navidrome.

```bash
./run.sh navidrome-sync-simple [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--genre TEXT` | Filter by genre |
| `--year YEAR` | Filter by year |
| `--artist TEXT` | Filter by artist |
| `--playlist-name NAME` | Target playlist name |

### Examples

```bash
# Sync all rock music
./run.sh navidrome-sync-simple --genre="Rock"

# Sync 2024 releases
./run.sh navidrome-sync-simple --year=2024
```

## Command: stats

Shows organization statistics.

```bash
./run.sh stats [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--genre-quality` | Show genre quality report |

## Command: backup-integrity

Verifies backup integrity.

```bash
./run.sh backup-integrity [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--cleanup` | Remove old backups |

## Command: test

Runs the test suite.

```bash
./run.sh test
```
