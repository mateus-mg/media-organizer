# Architecture Overview

## System Design

Media Organizer is designed around a **workflow orchestration pattern** where a central coordinator manages the lifecycle of each media file from discovery to organization.

## Core Principles

1. **Single Responsibility** - Each module has one clear purpose
2. **Interface Contracts** - All modules communicate through abstract interfaces
3. **Database Isolation** - Persistence layer is abstracted behind repositories
4. **Parallel Processing** - Concurrent operations for performance
5. **Failure Tracking** - Comprehensive logging of failed operations

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| CLI | Click | Command-line interface |
| Database | TinyDB | JSON-based document storage |
| Metadata | mutagen, music-tag, PyPDF2, ebooklib | Media metadata extraction |
| HTTP | aiohttp, requests | Online metadata enrichment |
| Logging | Python logging | Runtime diagnostics |
| UI | Rich | Terminal formatting |

## Module Layers

```
┌─────────────────────────────────────────┐
│              CLI Layer                  │
│         (click, rich, cli_manager)      │
├─────────────────────────────────────────┤
│           Core Layer                     │
│    (orchestrator, detection, types)      │
├─────────────────────────────────────────┤
│          Services Layer                  │
│        (organizers, playlists)          │
├─────────────────────────────────────────┤
│         Features Layer                  │
│   (genre_guard, metadata, suggestions)  │
├─────────────────────────────────────────┤
│       Infrastructure Layer               │
│ (database, link_registry, navidrome)   │
└─────────────────────────────────────────┘
```

## Data Flow

The system processes media through a pipeline:

1. **Scan** - Discover files in download directories
2. **Classify** - Determine media type by extension
3. **Validate** - Check file completeness and quality
4. **Enrich** - Fetch additional metadata online
5. **Organize** - Create hardlinks in library structure
6. **Track** - Record in database for future reference
