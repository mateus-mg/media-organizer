# Data Flow

## Media Organization Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI as cli_manager.py
    participant Orch as orchestrator.py
    participant Scan as FileScanner
    participant Class as MediaClassifier
    participant Org as Organizer
    participant DB as OrganizationDatabase

    User->>CLI: process-new-media --dry-run
    CLI->>Orch: processar_novos_medias()
    Orch->>Scan: escanear_diretorio()
    Scan-->>Orch: [file1, file2, ...]
    Orch->>Class: classificar_tipo_midia()
    Class-->>Orch: MUSIC/BOOK/COMIC
    Orch->>Org: organizar()
    Org->>Org: _obter_caminho_destino()
    Org->>Org: _validar()
    Org->>Org: _criar_hardlink()
    Org->>DB: adicionar()
    DB-->>Org: success
    Org-->>Orch: ResultadoOrganizacao
    Orch-->>CLI: report
    CLI-->>User: Summary
```

## Validation Pipeline

```mermaid
flowchart TD
    A[New File] --> B{File exists?}
    B -->|No| C[Skip - Error]
    B -->|Yes| D{Extension valid?}
    D -->|No| E[Skip - Invalid type]
    D -->|Yes| F{Incomplete file?}
    F -->|Yes| G[Skip - Incomplete]
    F -->|No| H{Junk file?}
    H -->|Yes| I[Skip - Junk]
    H -->|No| J{Complete?}
    J -->|No| K[Skip - Incomplete]
    J -->|Yes| L[Pass Validation]
    C --> M[Logged to database]
    E --> M
    G --> M
    I --> M
    K --> M
    L --> N[Continue to organization]
```

## Music Organization Detail

```mermaid
flowchart TD
    A[Audio File] --> B[Extract Metadata]
    B --> C{MusicBrainz enabled?}
    C -->|Yes| D[Search MusicBrainz]
    D --> E[Get Release Info]
    E --> F[Merge Genres]
    C -->|No| G[Use local metadata]
    F --> H{Genre Guard enabled?}
    H -->|Yes| I[Validate Genre]
    I --> J{Valid genre?}
    J -->|No| K[Quarantine genre]
    J -->|Yes| L[Continue]
    K --> L
    H -->|No| L
    G --> L
    L --> M[MusicOrganizer]
    M --> N[Artist/Album/Track structure]
    N --> O[Create hardlink]
    O --> P[Update database]
```

## Book/Comic Organization Detail

```mermaid
flowchart TD
    A[Book/Comic File] --> B[Parse filename schema]
    B --> C{Valid schema?}
    C -->|No| D[Skip - Invalid format]
    C -->|Yes| E[Extract metadata]
    E --> F{Online enrichment?}
    F -->|Yes| G[OpenLibrary/Google Books]
    G --> H[Update metadata]
    F -->|No| I[Use filename metadata]
    H --> I
    I --> J[BookOrganizer]
    J --> K[Author/Title structure]
    K --> L[Create hardlink]
    L --> M[Update database]
```

## Hardlink Creation Flow

```mermaid
flowchart TD
    A[Source File] --> B{Same filesystem?}
    B -->|Yes| C[Create hardlink]
    B -->|No| D[Copy file]
    C --> E{Link created?}
    D --> E
    E -->|Yes| F[Register in LinkRegistry]
    E -->|No| G{Conflict strategy?}
    G -->|skip| H[Skip file]
    G -->|rename| I[Rename with suffix]
    I --> C
    G -->|overwrite| J[Overwrite]
    J --> C
    F --> K[Record in database]
    H --> L[Log skipped]
    K --> M[Success]
    L --> M
```

## Navidrome Playlist Sync

```mermaid
sequenceDiagram
    participant User
    participant CLI as navidrome-sync-simple
    participant Svc as PlaylistService
    participant Client as NavidromeClient
    participant DB as OrganizationDatabase

    User->>CLI: --name "Rock 2020" --genre Rock
    CLI->>Svc: sync_simple_playlist_from_organization()
    Svc->>DB: query_music_files(genre=Rock)
    DB-->>Svc: [tracks...]
    Svc->>Client: get_playlists()
    Client-->>Svc: [playlists...]
    Svc->>Svc: calculate_diff()
    Svc->>Client: create_playlist() or update_playlist()
    Client-->>Svc: playlist_id
    Svc-->>CLI: report
    CLI-->>User: Summary
```

## Backup Creation Flow

```mermaid
flowchart TD
    A[Backup Triggered] --> B{Create backup?}
    B -->|No| C[Exit]
    B -->|Yes| D[Open database]
    D --> E[Get enabled sources]
    E --> F{More sources?}
    F -->|Yes| G[Select next source]
    G --> H[Validate path]
    H -->|Invalid| I[Log error]
    I --> F
    H -->|Valid| J[Execute rsync]
    J --> K{rsync success?}
    K -->|No| L[Log error]
    L --> F
    K -->|Yes| M[Parse stats]
    M --> N[Write metadata]
    N --> O[Update state]
    O --> F
    F -->|No| P[Cleanup old backups]
    P --> Q[Write history]
    Q --> R[Backup complete]
```

## Genre Guard Validation

```mermaid
flowchart TD
    A[Raw Genre String] --> B[Normalize]
    B --> C{Exact match invalid?}
    C -->|Yes| D[REJECT - Quarantine]
    C -->|No| E{Exact match exception?}
    E -->|Yes| F[ACCEPT - Keep]
    E -->|No| G{Compound genre?}
    G -->|Yes| H[Split tokens]
    H --> I[Validate each token]
    I --> J{All tokens valid?}
    J -->|No| K[Partial quarantine]
    J -->|Yes| F
    G -->|No| L[Check keywords]
    L --> M{Token in keywords?}
    M -->|Yes| F
    M -->|No| N[Heuristic scoring]
    N --> O{Confidence score?}
    O -->|High| F
    O -->|Low| D
```
