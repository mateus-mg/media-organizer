# Trash Manager (`infrastructure/trash_manager.py`)

Safe file deletion with quarantine and audit trail.

## Class: TrashManager

```python
class TrashManager:
    def __init__(self, config: Config)
    def mover_para_lixeira(self, caminho: Path, motivo: str) -> str
    def restaurar(self, item_id: str) -> Path
    def esvaziar_lixeira(self)
    def obter_itens_lixeira(self) -> list[TrashItem]
```

## Features

### Quarantine

- Moves files to `TRASH_PATH` directory
- Preserves original path in metadata
- Timestamps all entries

### Retention Policy

- Configurable retention period (default: 30 days)
- Automatic cleanup of expired items
- Audit trail for all deletions

### Audit Trail

Every trash operation records:
- Original path
- Move timestamp
- Reason/motive
- Operation ID

## Trash Item Schema

```json
{
  "id": "uuid",
  "original_path": "/library/Music/Artist/Album/Track.mp3",
  "trash_path": "/trash/uuid/Track.mp3",
  "moved_at": "2026-04-19T10:30:00",
  "reason": "duplicate_organization",
  "expires_at": "2026-05-19T10:30:00"
}
```

## Configuration

| Variable | Description |
|----------|-------------|
| `TRASH_ENABLED` | Enable trash system |
| `TRASH_PATH` | Trash directory location |
| `TRASH_RETENTION_DAYS` | Days before permanent deletion |
