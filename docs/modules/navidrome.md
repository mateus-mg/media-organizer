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

Navidrome smart playlists in `.nsp` format use the official Navidrome JSON structure:

```json
{
  "name": "My Smart Playlist",
  "all": [
    {"contains": {"genre": "Rock"}},
    {"gt": {"year": 2020}}
  ],
  "sort": "-rating,title",
  "order": "asc",
  "limit": 50
}
```

**Root clauses:** `all` (AND) or `any` (OR).

**Operators:** `is`, `isNot`, `gt`, `lt`, `contains`, `notContains`, `startsWith`, `endsWith`, `inTheRange`, `before`, `after`, `inTheLast`, `notInTheLast`, `inPlaylist`, `notInPlaylist`.

## Smart Playlist Builder API

Create smart playlists programmatically:

```python
from app.services import PlaylistService
from app.features.smart_playlists import SmartPlaylistBuilder

builder = SmartPlaylistBuilder("Rock 80s")
builder.all_of(
    builder.field("genre").contains("rock"),
    builder.field("year").in_the_range(1980, 1989),
    builder.field("rating").gt(3),
).sort("-rating", "title").limit(50)

service = PlaylistService(config)
service.create_smart_playlist(name="Rock 80s", builder=builder)
```

## Query String Syntax

Quick creation with query strings:

```python
service.create_smart_playlist(
    name="EDM",
    query="genre:edm year:gt:2020 rating:gt:3",
    sort="-playcount",
    limit=100,
)
```

Syntax: `field:value` or `field:operator:value`. Conditions separated by space = AND.

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
