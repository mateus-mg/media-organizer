# CLI Commands

Complete reference for all CLI commands.

## Main Commands

| Command | Description |
|---------|-------------|
| `./run.sh organize` | Interactive organize menu |
| `./run.sh interactive` | Full interactive menu |
| `./run.sh process-new-media` | Full organization cycle |

## Organization Commands

```bash
# Process new media (full cycle)
./run.sh process-new-media [--dry-run]

# Organize specific media
./run.sh organize
# Select: [1] Music, [2] Books, [3] Comics
```

## Metadata Commands

```bash
# Preview music metadata enrichment
./run.sh preview-music-metadata

# Normalize album metadata
./run.sh music-metadata-normalize-albums [--execute]

# Backfill book covers
./run.sh backfill-book-covers

# Backfill book years
./run.sh backfill-book-years
```

## Genre Commands

```bash
# Preview genre fixes
./run.sh music-genre-backfill

# Execute genre fixes
./run.sh music-genre-backfill --execute
```

## Filename Commands

```bash
# Generate filename suggestions
./run.sh suggest-filenames

# Edit suggestion report
./run.sh edit-filename-suggestion

# Apply suggestions
./run.sh apply-filename-suggestions [--execute]
```

## Navidrome Commands

```bash
# Test connection
./run.sh navidrome-test

# List playlists
./run.sh navidrome-playlists

# Sync playlists
./run.sh navidrome-sync-simple
```

## System Commands

```bash
# Show statistics
./run.sh stats

# Run test suite
./run.sh test

# Check backup integrity
./run.sh backup-integrity [--cleanup]

# Validate configuration
./run.sh validate-config
```

## Global Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview without making changes |
| `--help` | Show help message |
| `--verbose` | Enable verbose output |
