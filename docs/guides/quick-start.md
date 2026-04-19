# Quick Start

Get started with Media Organizer in 5 minutes.

## Step 1: First Organization

```bash
./run.sh organize
```

This opens an interactive menu where you can:
- Organize all media types
- Organize specific types (music, books, comics)
- Preview changes before applying

## Step 2: Dry Run

Always preview first:

```bash
./run.sh process-new-media --dry-run
```

This shows what would be organized without making changes.

## Step 3: Execute Organization

```bash
./run.sh process-new-media
```

## Step 4: Verify Results

Check the database:

```bash
./run.sh stats
```

View organized files:

```bash
ls -la /path/to/library/music
```

## Common Workflows

### Daily Organization

```bash
# Check for new media
./run.sh process-new-media --dry-run

# If preview looks good, execute
./run.sh process-new-media
```

### Navidrome Sync

```bash
# Test connection
./run.sh navidrome-test

# List playlists
./run.sh navidrome-playlists

# Sync playlists
./run.sh navidrome-sync-simple
```

### Genre Quality Check

```bash
# Generate report
./run.sh stats --genre-quality

# Apply fixes
./run.sh music-genre-backfill --execute
```
