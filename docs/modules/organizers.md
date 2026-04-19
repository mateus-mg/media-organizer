# Organizers (`services/organizers.py`)

Type-specific organization logic implementing `OrganizadorInterface`.

## Base Class: BaseOrganizer

```python
class BaseOrganizer:
    def organizar(self, arquivo: Path, metadados: dict) -> ResultadoOrganizacao
    def obter_caminho_destino(self, metadados: dict) -> Path
    def validar(self, arquivo: Path) -> bool
```

## MusicOrganizer

Organizes audio files into `Artist/Album/Track.ext` structure.

### Path Pattern

```
{LIBRARY_PATH_MUSIC}/
  {Artist}/
    {Album}/
      {Track Number} - {Title}.ext
```

### Features

- Artist/Album/Track hierarchy
- Compilation handling (Various Artists)
- Multi-disc support
- Genre validation via Genre Guard
- Lyrics pairing

## BookOrganizer

Organizes books into `Author/Title.ext` structure.

### Path Pattern

```
{LIBRARY_PATH_BOOKS}/
  {Author}/
    {Title}.ext
```

### Features

- Author/Title hierarchy
- Book/comic differentiation via `book_type`
- Series detection
- Cover art management

## ComicOrganizer

Organizes comics into `Title (Year) - Series #Issue.ext` structure.

### Path Pattern

```
{LIBRARY_PATH_COMICS}/
  {Title} ({Year})/
    {Title} ({Year}) - {Series} #{Issue}.ext
```

### Schema Validation

Required fields:
- `title` - Comic title
- `year` - Publication year
- `issue_number` - Issue number

## LyricsOrganizer

Pairs lyrics files (.lrc) with music tracks by filename similarity.

## ArtworkOrganizer

Organizes cover art matched to albums/books.

## RenamerOrganizer

Batch rename operations for existing organized files.
