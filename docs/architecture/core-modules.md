# Core Modules

## Orchestrator (`core/orchestrator.py`)

The `Orquestrador` class is the main workflow coordinator.

### Responsibilities

- Scan download directories for new media
- Coordinate validation and classification
- Delegate to appropriate organizer
- Track results in database

### Key Methods

| Method | Description |
|--------|-------------|
| `processar_novos_medias()` | Main processing cycle |
| `verificar_e_organizar()` | Single file organization |
| `_validar_arquivo()` | Run all validators |
| `_classificar_e_organizar()` | Route to correct organizer |

## Media Detection (`core/detection.py`)

### MediaClassifier

Classifies files by extension into media types.

```python
class MediaClassifier:
    AUDIO_EXTS = {".mp3", ".flac", ".wav", ".m4a", ".ogg", ".opus", ...}
    BOOK_EXTS = {".epub", ".pdf", ".mobi", ".azw", ".azw3"}
    COMIC_EXTS = {".cbz", ".cbr", ".cb7", ".cbt"}
```

### FileScanner

Recursively scans directories for media files.

```python
class FileScanner:
    def escanear_diretorio(self, caminho: Path) -> list[Path]
```

## Types (`core/types.py`)

Core enums and data classes:

```python
class MediaType(Enum):
    MUSIC = "music"
    LYRICS = "lyrics"
    ARTWORK = "artwork"
    BOOK = "book"
    COMIC = "comic"
    RENAMER = "renamer"
    UNKNOWN = "unknown"
```

## Interfaces (`core/interfaces.py`)

Abstract contracts for the system:

| Interface | Methods |
|-----------|---------|
| `OrganizadorInterface` | `organizar()`, `validar()`, `obter_caminho_destino()` |
| `ValidatorInterface` | `validar()` |
| `DatabaseInterface` | `adicionar()`, `buscar()`, `remover()` |
