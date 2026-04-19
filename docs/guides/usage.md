# Usage Guide

Common usage patterns for Media Organizer.

## Interactive Mode

```bash
./run.sh interactive
```

Opens a menu with all available operations.

## Batch Processing

### Process All New Media

```bash
./run.sh process-new-media
```

### Process Specific Types

```bash
./run.sh organize
# Then select:
# [1] Music only
# [2] Books only
# [3] Comics only
```

## Metadata Operations

### Preview Music Metadata

```bash
./run.sh preview-music-metadata
```

### Normalize Album Metadata

```bash
./run.sh music-metadata-normalize-albums --dry-run
./run.sh music-metadata-normalize-albums --execute
```

## Filename Suggestions

### Generate Suggestions

```bash
./run.sh suggest-filenames
```

### Review and Edit

```bash
./run.sh edit-filename-suggestion
```

### Apply Changes

```bash
./run.sh apply-filename-suggestions --dry-run
./run.sh apply-filename-suggestions --execute
```

## Playlist Management

### Navidrome Integration

```bash
# Test connection
./run.sh navidrome-test

# List playlists
./run.sh navidrome-playlists

# Sync by filters
./run.sh navidrome-sync-simple --genre="Rock" --year=2020
```

## Database Operations

### Check Statistics

```bash
./run.sh stats
```

### Backup Integrity

```bash
./run.sh backup-integrity
./run.sh backup-integrity --cleanup
```

## System Maintenance

### Run Tests

```bash
./run.sh test
```

### View Logs

```bash
tail -f logs/organizer.log
```
