# Metadata (`metadata/metadata.py`)

Metadata extraction and online enrichment.

## Class: MetadataEnricher

```python
class MetadataEnricher:
    def __init__(self, config: Config)
    def enrich_music(self, arquivo: Path) -> MusicMetadata
    def enrich_book(self, arquivo: Path) -> BookMetadata
    def enrich_comic(self, arquivo: Path) -> ComicMetadata
```

## Music Metadata

### Local Extraction (mutagen/music-tag)

- Title, Artist, Album
- Genre, Year, Track number
- Duration, Bitrate
- Album art

### Online Enrichment

| Provider | Data |
|----------|------|
| MusicBrainz | Release IDs, artist IDs, genres |
| Last.fm | Genre tags, similarity data |
| Spotify | (via Subsonic) |

### Enrichment Flow

1. Extract local metadata
2. Search MusicBrainz for recording
3. Get release info
4. Merge genres
5. Enrich with Last.fm tags

## Book Metadata

### Local Extraction (PyPDF2, ebooklib)

- Title, Author
- ISBN, Publisher
- Page count, Language

### Online Enrichment

| Provider | Data |
|----------|------|
| OpenLibrary | ISBN lookup, cover URLs |
| Google Books | Description, categories |

## Comic Metadata

### Extraction

- Parsed from filename schema
- Title, Year, Issue number
- Series, Publisher

### Format

```
{Title} ({Year}) - {Series} #{Issue}.ext
```
