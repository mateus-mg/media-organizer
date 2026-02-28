# Trash & Deletion Manager Guide

## Overview

The Trash & Deletion Manager provides safe deletion of files in hardlink-based environments. It solves the problem where deleting one hardlink doesn't actually free disk space because other hardlinks still exist.

## Features

- **Link Registry**: Tracks all hardlinks by inode
- **Trash System**: Safe, reversible deletion with configurable retention
- **Permanent Deletion**: Direct deletion with confirmation
- **Preview Mode**: Dry-run to see what would be deleted
- **Database Backup**: Automatic backup before destructive operations
- **Filesystem Scan**: Rebuild registry from existing files

## Quick Start

### Access via Menu

```bash
./run.sh organize
# Select option 9: Trash & Deletion
```

### Direct Commands

```bash
# Show help
media-organizer trash --help

# List trash items
media-organizer trash list

# Delete file to trash (safe)
media-organizer trash delete /path/to/file.mkv

# Delete permanently (irreversible)
media-organizer trash delete-permanent /path/to/file.mkv

# Preview deletion (dry-run)
media-organizer trash delete /path/to/file.mkv --dry-run

# Restore from trash
media-organizer trash restore abc12345

# Empty trash
media-organizer trash empty

# Show status
media-organizer trash status

# Lookup all hardlinks for a file
media-organizer trash lookup /path/to/file.mkv

# Scan filesystem to rebuild registry
media-organizer trash scan
```

## How It Works

### Hardlink Problem

In your current system:
```
Original: /downloads/movies/Foo.mkv
         ↓ (hard link - same inode)
Organized: /library/movies/Foo (2020)/Foo.mkv
```

When you delete `/downloads/movies/Foo.mkv`, the file still exists via `/library/movies/Foo (2020)/Foo.mkv`. The disk space is NOT freed.

### Solution

The Deletion Manager:
1. **Tracks all hardlinks** in `data/link_registry.json`
2. **Identifies all links** when you request deletion
3. **Removes ALL hardlinks** to actually free disk space
4. **Optionally stores one copy** in trash for recovery

### Deletion Flow (Trash Mode)

```
1. User requests deletion of /library/movies/Foo.mkv
         ↓
2. System looks up inode in Link Registry
         ↓
3. Finds all hardlinks:
   - /downloads/movies/Foo.mkv
   - /library/movies/Foo (2020)/Foo.mkv
         ↓
4. Copies one file to data/trash/files/{id}/Foo.mkv
         ↓
5. Removes ALL original hardlinks
         ↓
6. Updates organization database
         ↓
7. File can be restored within retention period (30 days)
```

### Deletion Flow (Permanent Mode)

```
1. User requests permanent deletion
         ↓
2. Creates database backup (safety)
         ↓
3. Removes ALL hardlinks directly
         ↓
4. Updates organization database
         ↓
5. File is GONE (cannot be recovered)
```

## Configuration

Add to your `.env` file:

```bash
# Trash & Deletion Settings
TRASH_ENABLED="true"                    # Enable trash system
TRASH_PATH="./data/trash"               # Trash directory
TRASH_RETENTION_DAYS="30"               # Days to keep in trash
LINK_REGISTRY_PATH="./data/link_registry.json"
DELETE_CONFIRMATION_REQUIRED="true"     # Require 'DELETE' confirmation
DELETE_DRY_RUN_DEFAULT="true"           # Preview before deleting
```

## Interactive Menu

```
🗑️  Trash & Deletion Manager

Select an operation:

  [1] Delete file (to trash)        # Safe, reversible
  [2] Delete permanent (direct)     # Irreversible
  [3] List trash items              # View trashed files
  [4] Restore from trash            # Recover deleted file
  [5] Empty trash                   # Permanently remove all
  [6] Trash status                  # Statistics and info
  [7] Scan filesystem               # Rebuild registry
  [8] Link lookup                   # Find all hardlinks
  [0] Back to main menu
```

## Command Reference

### `delete` - Delete to Trash

Move file to trash (safe, reversible).

```bash
# Interactive confirmation
media-organizer trash delete /path/to/file.mkv

# Preview only (dry-run)
media-organizer trash delete /path/to/file.mkv --dry-run
```

### `delete-permanent` - Permanent Deletion

Delete file permanently (irreversible).

```bash
# With confirmation prompt
media-organizer trash delete-permanent /path/to/file.mkv

# Skip confirmation (DANGEROUS)
media-organizer trash delete-permanent /path/to/file.mkv --force

# Preview only
media-organizer trash delete-permanent /path/to/file.mkv --dry-run
```

### `list` - List Trash Items

```bash
# Active items only
media-organizer trash list

# All items (including restored)
media-organizer trash list --all
```

Output:
```
ID       Original Path                          Size     Created     Days Left
─────    ─────────────────────────────────────  ───────  ──────────  ─────────
abc123   /library/movies/Foo (2020)/Foo.mkv     2.1 GB   2026-02-28  28
def456   /library/tv/Bar S01E01.mkv             1.5 GB   2026-02-25  25
```

### `restore` - Restore from Trash

```bash
media-organizer trash restore abc12345
```

Restores file to original location(s) and re-registers in Link Registry.

### `empty` - Empty Trash

```bash
# Remove all items
media-organizer trash empty

# Remove only items older than 7 days
media-organizer trash empty --older-than 7
```

### `status` - Show Statistics

```bash
media-organizer trash status
```

Output:
```
Trash Statistics
────────────────────────────────────
Total Items:      5
Active Items:     3
Total Size:       8.5 GB
Retention Days:   30

Link Registry Statistics
────────────────────────────────────
Total Inodes:     1234
Total Links:      2468
Total Size:       500.0 GB
```

### `lookup` - Find All Hardlinks

```bash
media-organizer trash lookup /path/to/file.mkv
```

Output:
```
Deletion Preview

Inode: 12345678
Hardlink count: 2

All hardlinks:
  ✓ /downloads/movies/Foo.mkv (original)
  ✓ /library/movies/Foo (2020)/Foo.mkv (organized)

Total: 2 link(s)
```

### `scan` - Rebuild Registry

```bash
media-organizer trash scan
```

Scans all configured directories and registers found hardlinks.

## Re-organization After Deletion

### Scenario 1: Deleted to Trash (Not Yet Emptied)

Restore from trash:
```bash
media-organizer trash restore abc12345
```

File is restored to original locations with hardlinks intact.

### Scenario 2: Deleted Permanently or Trash Emptied

File no longer exists. To re-organize:
1. Obtain the file again (download, copy, etc.)
2. Run organization:
   ```bash
   media-organizer organize
   ```
3. System treats it as a new file and creates fresh hardlinks

## Safety Features

### 1. Database Backup

Before permanent deletion, the system automatically creates a backup of the organization database:

```
data/backups/
└── organization_2026-02-28_15-30-00.json  # Pre-deletion backup
```

If something goes wrong, restore manually:
```bash
cp data/backups/organization_2026-02-28_15-30-00.json data/organization.json
```

### 2. Confirmation Prompts

**Trash deletion:**
```
🗑️  Move to Trash

The following hard links will be REMOVED:
  • /downloads/movies/Foo.mkv
  • /library/movies/Foo (2020)/Foo.mkv

A copy will be stored in trash for 30 days.

Are you sure? [y/N]:
```

**Permanent deletion:**
```
⚠️  PERMANENT DELETION WARNING

The following files will be PERMANENTLY DELETED:
  • /downloads/movies/Foo.mkv (2.0 GB)
  • /library/movies/Foo (2020)/Foo.mkv (2.0 GB)

This action CANNOT be undone.

Type 'DELETE' to confirm:
```

### 3. Dry-Run Mode

Always preview before deleting:
```bash
media-organizer trash delete /path/to/file.mkv --dry-run
```

## Troubleshooting

### "File not in registry"

If a file isn't in the registry, only that specific file will be deleted (no other hardlinks found).

**Solution:** Run a filesystem scan:
```bash
media-organizer trash scan
```

### "Trash is full" / Disk Space Issues

Empty old trash items:
```bash
# Remove items older than 7 days
media-organizer trash empty --older-than 7
```

### Registry Corruption

Rebuild from filesystem:
```bash
media-organizer trash scan
```

### Restore Failed

Check if trash file exists:
```bash
ls -la data/trash/files/{trash_id}/
```

If missing, file cannot be restored.

## Best Practices

1. **Always use trash mode first** - Permanent deletion should be last resort
2. **Regular trash emptying** - Set a schedule (e.g., monthly)
3. **Preview before deleting** - Use `--dry-run` to verify
4. **Keep backups** - Database backups are automatic, but consider file backups too
5. **Scan periodically** - Run `trash scan` monthly to keep registry updated

## Architecture

```
src/deletion/
├── __init__.py              # Module exports
├── link_registry.py         # Inode tracking
├── trash_manager.py         # Trash operations
├── deletion_manager.py      # Deletion orchestration
└── cli.py                   # CLI interface

data/
├── link_registry.json       # Hardlink database
└── trash/
    ├── index.json           # Trash index
    └── files/               # Trashed files
```

## API Reference

### LinkRegistry

```python
from src.deletion import LinkRegistry

registry = LinkRegistry(Path("data/link_registry.json"))

# Register a new hardlink
registry.register_link(source_path, dest_path, metadata)

# Get all hardlinks for a file
links = registry.get_all_links(path)

# Unregister a link
registry.unregister_link(path)

# Get inode
inode = registry.get_inode(path)

# Scan filesystem
stats = registry.scan_filesystem(directories)
```

### TrashManager

```python
from src.deletion import TrashManager

trash = TrashManager(Path("data/trash"), retention_days=30)

# Move to trash
trash_id = trash.move_to_trash(primary_path, all_links, metadata)

# Restore from trash
success = trash.restore_from_trash(trash_id)

# Empty trash
result = trash.empty_trash()

# List items
items = trash.list_items()

# Get stats
stats = trash.get_stats()
```

### DeletionManager

```python
from src.deletion import DeletionManager

deletion = DeletionManager(link_registry, trash_manager, database)

# Preview deletion
preview = await deletion.get_deletion_preview(path)

# Delete to trash
result = await deletion.delete_to_trash(path, metadata)

# Delete permanently
result = await deletion.delete_permanent(path, dry_run=False, force=False)

# Restore from trash
success = await deletion.restore_from_trash(trash_id)
```

## Support

For issues or questions, check the main README.md or open an issue in the project repository.
