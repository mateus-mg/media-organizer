# Orchestrator (`core/orchestrator.py`)

`Orquestrador` is the main workflow coordinator.

## Class: Orquestrador

### Initialization

```python
def __init__(
    self,
    config: Config,
    database: OrganizationDatabase,
    link_registry: LinkRegistry,
    scanners: dict[MediaType, FileScannerInterface],
    classifiers: dict[MediaType, MediaClassifierInterface],
    validators: list[ValidatorInterface],
    organizers: dict[MediaType, OrganizadorInterface],
    metadata_enricher: MetadataEnricher | None = None,
    genre_guard: GenreGuard | None = None,
    trash_manager: TrashManager | None = None,
)
```

### Main Methods

| Method | Description |
|--------|-------------|
| `processar_novos_medias()` | Execute full organization cycle |
| `verificar_e_organizar()` | Process single file |
| `obter_estatisticas()` | Get operation statistics |

### Processing Cycle

1. Scan download directories
2. Filter already organized files
3. Validate file completeness
4. Classify media type
5. Apply global validators
6. Enrich metadata (if enabled)
7. Route to type-specific organizer
8. Track in database
