# Filename Suggestions (`features/filename_suggestions.py`)

AI-powered filename improvement suggestions for books and comics.

## Class: FilenameSuggestionEngine

```python
class FilenameSuggestionEngine:
    def gerar_sugestoes(self, arquivos: list[Path]) -> list[Suggestion]
    def aplicar_sugestoes(self, sugestoes: list[Suggestion], execute: bool)
    def editar_sugestao(self, suggestion_id: str, novo_nome: str)
```

## Suggestion Types

| Type | Description |
|------|-------------|
| `TITLE_YEAR_ADDED` | Added missing year to title |
| `SERIES_NORMALIZED` | Standardized series format |
| `ISSUE_PADDED` | Zero-padded issue numbers |
| `AUTHOR_ADDED` | Added author to path |

## Schema Patterns

### Books

```
Author/Title.ext
Title (Year).ext
Title - Author.ext
```

### Comics

```
Title (Year) - Series #Issue.ext
```

## CLI Commands

```bash
./run.sh suggest-filenames           # Generate suggestions
./run.sh edit-filename-suggestion   # Edit suggestion report
./run.sh apply-filename-suggestions # Apply changes
./run.sh apply-filename-suggestions --execute  # Execute changes
```

## Report Format

Suggestions are saved to `data/filename_suggestions_report.json`:

```json
{
  "suggestions": [
    {
      "id": "uuid",
      "original_path": "/downloads/book.epub",
      "suggested_path": "/library/Author/Title.epub",
      "confidence": 0.95,
      "reason": "Added year to title",
      "status": "pending"
    }
  ]
}
```
