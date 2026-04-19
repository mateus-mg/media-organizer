# Navidrome Client (`infrastructure/navidrome_client.py`)

Subsonic API client for Navidrome integration.

## Class: NavidromeClient

```python
class NavidromeClient:
    def __init__(self, config: Config)
    def ping() -> bool
    def get_playlists() -> list[Playlist]
    def create_playlist(name: str, path: Path) -> str
    def sync_playlist(playlist_id: str, paths: list[Path])
```

## Features

### Playlist Sync

- Sync organized media to Navidrome playlists
- Support for smart playlists (.nsp format)
- Automatic playlist updates

### .nsp Smart Playlists

Navidrome smart playlists in `.nsp` format:

```nsp
{
  "name": "My Smart Playlist",
  "rules": [
    {"field": "genre", "operator": "contains", "value": "Rock"},
    {"field": "year", "operator": "greaterThan", "value": "2020"}
  ],
  "match": "all"
}
```

## CLI Commands

```bash
./run.sh navidrome-test           # Test connection
./run.sh navidrome-playlists     # List playlists
./run.sh navidrome-sync-simple    # Sync by filters
```

## Configuration

| Variable | Description |
|----------|-------------|
| `NAVIDROME_ENABLED` | Enable Navidrome integration |
| `NAVIDROME_BASE_URL` | Navidrome server URL |
| `NAVIDROME_USERNAME` | API username |
| `NAVIDROME_PASSWORD` | API password |
| `NAVIDROME_API_VERSION` | Subsonic API version |
