# Genre Guard (`features/genre_guard/`)

Intelligent genre validation and sanitization system.

## Overview

Instead of maintaining an 800+ genre whitelist, Genre Guard uses:
- **Musical Keywords** (548 terms) - covers 99%+ of valid genres
- **Genre Exceptions** (7 items) - niche genres not in keywords
- **Invalid Genres** - explicitly blacklisted terms

## Class: GenreGuard

```python
class GenreGuard:
    def __init__(self, config: Config)
    def validar_genero(self, genero: str) -> ValidationResult
    def sanitizar_genero(self, genero: str) -> str
    def obter_genero_canonico(self, genero: str) -> str
```

## Validation Logic

1. Normalize input (lowercase, trim)
2. Check exact match in invalid list → REJECT
3. Check exact match in exceptions → ACCEPT
4. Check compound genre (split by `/`, `;`, `&`) → validate each
5. Check all tokens in musical keywords → ACCEPT
6. Apply heuristic scoring for uncertain cases

### Heuristic Scoring

Editorial tokens increase confidence:
- `top`, `chart`, `playlist`, `hits`, `best`, `greatest`
- Geographic markers: `uk`, `brazilian`, `american`
- Mood markers: `chill`, `relax`, `party`

## Data Files

| File | Purpose |
|------|---------|
| `data/invalid_music_genres.json` | Blacklist |
| `data/suspect_music_genres.json` | Suspicious but kept |
| `data/genre_exceptions.json` | Explicit exceptions |
| `data/musical_keywords.json` | Valid genre keywords |

## CLI Commands

```bash
./run.sh music-genre-backfill        # Preview genre fixes
./run.sh music-genre-backfill --execute  # Apply fixes
```
