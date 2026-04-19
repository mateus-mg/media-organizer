# Infrastructure

## OrganizationDatabase (`infrastructure/database.py`)

TinyDB-based persistence for organized media.

### Features

- Automatic backups before modifications
- Backup rotation (keeps 7 days by default)
- Thread-safe operations via RLock
- Statistics tracking

### Tables

```python
# media - All organized media records
# statistics - Operation statistics
# failed_operations - Failed organization attempts
```

## LinkRegistry (`infrastructure/link_registry.py`)

Tracks hardlinks by device+inode for safe deletion.

### Key Methods

| Method | Description |
|--------|-------------|
| `registrar_link()` | Record a hardlink |
| `verificar_inode_existe()` | Check if inode is tracked |
| `obter_caminhos_por_inode()` | Get all paths for an inode |

### Thread Safety

Uses `RLock` per database file to ensure thread-safe operations.

## TrashManager (`infrastructure/trash_manager.py`)

Soft-delete system with quarantine and audit trail.

### Features

- Moves files to quarantine directory
- Maintains index of trashed files
- Retention policy (configurable days)
- Audit trail for all deletions

## NavidromeClient (`infrastructure/navidrome_client.py`)

Subsonic API client for Navidrome integration.

### Capabilities

- Authentication with Navidrome server
- Playlist creation and sync
- Smart playlist generation (.nsp files)
