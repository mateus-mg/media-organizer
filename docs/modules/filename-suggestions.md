# Filename Suggestions (`features/filename_suggestions.py`)

AI-powered filename improvement suggestions for books and comics.

## Class: FilenameSuggestionEngine

### Constructor

```python
class FilenameSuggestionEngine:
    def __init__(
        self,
        classifier: Optional[MediaClassifier] = None,
        learning_path: Optional[Path] = None,
    )
```

### Key Methods

| Method | Description |
|--------|-------------|
| `suggest_for_root(root_path, media_filter)` | Scan directory recursively and generate suggestions |
| `learn_from_report(report, only_manual)` | Learn from user-accepted suggestions |
| `apply_report(report, dry_run)` | Apply suggestions to rename files |
| `update_report_suggestion(report, index, new_name)` | Manually edit a suggestion |

### Supported Input Patterns

The engine accepts flexible input patterns:

**Books:**
- `Author - Title (Year).ext` (canonical)
- `Author - Title.YYYY.ext` (dot year)
- `Author - Title-YYYY.ext` (dash year)
- `Title (Year).ext` (title only)

**Comics:**
- `Title (Year) - Series #Issue.ext` (canonical)
- `Series #Issue.ext` (without year)
- `Series.ISSUE.ext` (dot separator)
- `Series_ISSUE.ext` (underscore separator)
- `Series ISSUE.ext` (zero-padded without hash)

### Confidence Levels

| Level | Meaning |
|-------|---------|
| `high` | Author/title/series/issue/year all extracted correctly |
| `medium` | Some fields extracted, suggestion may need review |
| `low` | Fallback mode, suggestion needs manual review |
| `manual` | User manually corrected the suggestion |

### CLI Commands

```bash
# Generate suggestions report
./run.sh suggest-filenames --media books

# View and edit suggestions
./run.sh edit-filename-suggestion

# Apply suggestions (dry-run)
./run.sh apply-filename-suggestions

# Apply suggestions (execute)
./run.sh apply-filename-suggestions --execute
```

### Report Format

Suggestions are saved to `data/filename_suggestions_report.json`:

```json
{
  "total_files_scanned": 100,
  "matched_media_files": 50,
  "changed_suggestions": 25,
  "suggestions": [
    {
      "original_path": "/downloads/book.epub",
      "original_name": "John.Smith.-.Great.Book.2020.pdf",
      "media_type": "BOOK",
      "suggested_name": "John Smith - Great Book (2020).pdf",
      "confidence": "high",
      "reason": "author_title_year_extracted",
      "changed": true
    }
  ]
}
```

### Learning System

The engine learns from user corrections:
- `exact_overrides`: Direct filename mappings
- `series_aliases`: Comic series name normalization
- `author_aliases`: Book author name normalization

Data stored in `data/filename_suggestion_learning.json`.
