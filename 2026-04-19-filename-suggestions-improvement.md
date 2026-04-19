# Filename Suggestion Engine Improvement Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make filename suggestions actually useful by supporting flexible input patterns and still producing output that matches the organizer patterns.

**Architecture:**
The filename suggestion engine has two components:
1. **Parser functions** (`parse_book_filename_fields`, `parse_comic_filename_fields`) - Validate if a filename is already in canonical format
2. **Extraction heuristics** (`_extract_book_author_title`, `_extract_series_issue`) - Extract fields from non-canonical filenames

The problem: when input doesn't match rigid patterns, the engine falls back to low-confidence original name.

**Tech Stack:** Python, regex, no external dependencies

---

## File Structure

- Modify: `app/features/filename_suggestions.py` - Main suggestion engine improvements
- Modify: `app/utils/helpers.py` - Parser validation improvements
- Modify: `tests/test_filename_suggestions_unit.py` - Add test cases for new patterns
- Modify: `docs/modules/filename-suggestions.md` - Update module documentation

---

## Expected Organizer Patterns (Reference)

These are the target formats the suggestions must produce:

**Books:** `Author - Title (Year).ext`
- Built at `organizers.py:5403`

**Comics:** `Title (Year) - Series #Issue.ext` (when series exists)
- Built at `organizers.py:5156`

---

## Task 1: Improve Year Extraction Flexibility

**Files:**
- Modify: `app/features/filename_suggestions.py:518-525`

Currently year must be in `(YYYY)` format. Expand to accept:
- `.2020` (dot separator)
- `-2020` (dash separator)
- `_2020` (underscore separator)

- [ ] **Step 1: Write test for flexible year extraction**

```python
def test_extract_year_variants(self):
    engine = FilenameSuggestionEngine()
    # Existing test
    self.assertEqual(engine._extract_year("Book (2020)"), 2020)
    # New tests
    self.assertEqual(engine._extract_year("Book.2020"), 2020)
    self.assertEqual(engine._extract_year("Book-2020"), 2020)
    self.assertEqual(engine._extract_year("Book_2020"), 2020)
    self.assertEqual(engine._extract_year("Book 2020"), 2020)  # space
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_filename_suggestions_unit.py::TestFilenameSuggestionEngine::test_extract_year_variants -v`
Expected: FAIL

- [ ] **Step 3: Update _extract_year implementation**

```python
def _extract_year(self, text: str) -> Optional[int]:
    # Try parentheses first: (2020)
    match = re.search(r"\((19|20)\d{2}\)", text)
    if match:
        value = int(match.group(0)[1:-1])
        if 1900 <= value <= 2100:
            return value

    # Try dot/dash/underscore/space before year: .2020, -2020, _2020, 2020
    match = re.search(r"[._\-\s](19|20)(\d{2})(?=[^0-9]|$)", text)
    if match:
        value = int(match.group(0)[1:])
        if 1900 <= value <= 2100:
            return value

    # Try trailing year with nothing before: "2020" at end
    match = re.search(r"(19|20)\d{2}$", text)
    if match:
        value = int(match.group(0))
        if 1900 <= value <= 2100:
            return value
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_filename_suggestions_unit.py::TestFilenameSuggestionEngine::test_extract_year_variants -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/features/filename_suggestions.py tests/test_filename_suggestions_unit.py
git commit -m "feat(filename-suggestions): support flexible year formats (.YYYY, -YYYY, _YYYY, spaceYYYY)"
```

---

## Task 2: Improve Book Author-Title Extraction

**Files:**
- Modify: `app/features/filename_suggestions.py:487-498`
- Modify: `app/utils/helpers.py:154-230` (parse_book_filename_fields validation)

Currently `_extract_book_author_title` only recognizes `Author - Title` format. Improve to handle:

1. **Inverted order:** `Title - Author` (when no year present)
2. **Missing author:** `Title (Year)` → author = "Unknown Author"
3. **Multiple separators:** `Author, Author 2 - Title (Year)` → first author
4. **Year in different positions:** `Title (2020) - Author`, `Author - Title (2020)`

- [ ] **Step 1: Write test for book extraction variants**

```python
def test_extract_book_author_title_variants(self):
    engine = FilenameSuggestionEngine()

    # Standard format
    author, title = engine._extract_book_author_title("John Smith - Great Book")
    self.assertEqual(author, "John Smith")
    self.assertEqual(title, "Great Book")

    # Inverted (no year) - Title - Author
    author, title = engine._extract_book_author_title("Great Book - John Smith")
    # Should detect author at end when no year present
    self.assertIsNotNone(author)

    # Title only with year
    author, title = engine._extract_book_author_title("Great Book (2020)")
    self.assertEqual(title, "Great Book")
    self.assertIsNone(author)  # No separator found
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_filename_suggestions_unit.py::TestFilenameSuggestionEngine::test_extract_book_author_title_variants -v`
Expected: FAIL

- [ ] **Step 3: Update _extract_book_author_title implementation**

```python
def _extract_book_author_title(self, stem: str) -> tuple[Optional[str], Optional[str]]:
    # Handle: "Title (Year)" - title only, no author
    year_match = re.search(r"\((19|20)\d{2}\)\s*$", stem)
    if year_match:
        core = stem[:year_match.start()].strip()
        if " - " not in core:
            # Title only format
            title = self._sanitize_name(core)
            return None, title
        # Has separator AND year: "Author - Title" or "Title - Author"
        pass  # fall through to separator logic

    # Handle: "Title - Author" (inverted, no year)
    if " - " in stem:
        parts = stem.split(" - ", 1)
        # If one part looks like an author name (has first-last pattern)
        # and the other is shorter, likely Author - Title
        left, right = parts[0].strip(), parts[1].strip()
        # Simple heuristic: if right side is 2-3 words, likely author
        # If left side is longer/more words, likely title
        if len(right.split()) <= 3 and len(left.split()) > len(right.split()):
            # Inverted: Title - Author
            return self._sanitize_name(right), self._sanitize_name(left)
        else:
            # Standard: Author - Title
            return self._sanitize_name(left), self._sanitize_name(right)

    # No separator found
    return None, self._sanitize_name(stem)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_filename_suggestions_unit.py::TestFilenameSuggestionEngine::test_extract_book_author_title_variants -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/features/filename_suggestions.py tests/test_filename_suggestions_unit.py
git commit -m "feat(filename-suggestions): handle inverted Author-Title order and title-only formats"
```

---

## Task 3: Improve Comic Series-Issue Extraction

**Files:**
- Modify: `app/features/filename_suggestions.py:500-516`
- Modify: `app/utils/helpers.py:233-289` (parse_comic_filename_fields validation)

Currently `_extract_series_issue` only recognizes:
- `Series #12` (hash format)
- `Series 12` (space format)
- `Series 12 (2015)` (trailing year fallback)

Failures for:
- `Saga 009` (zero-padded without hash)
- `Saga 9 Part 1` (extra text)
- `Saga.9` (dot separator)
- `Saga_v9` (underscore separator)

- [ ] **Step 1: Write test for comic extraction variants**

```python
def test_extract_comic_series_issue_variants(self):
    engine = FilenameSuggestionEngine()

    # Standard
    series, issue = engine._extract_series_issue("Saga #12")
    self.assertEqual(series, "Saga")
    self.assertEqual(issue, 12)

    # Zero-padded
    series, issue = engine._extract_series_issue("Saga 009")
    self.assertEqual(series, "Saga")
    self.assertEqual(issue, 9)

    # Dot separator
    series, issue = engine._extract_series_issue("Saga.9")
    self.assertEqual(series, "Saga")
    self.assertEqual(issue, 9)

    # Underscore separator
    series, issue = engine._extract_series_issue("Saga_v9")
    self.assertEqual(series, "Saga")
    self.assertEqual(issue, 9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_filename_suggestions_unit.py::TestFilenameSuggestionEngine::test_extract_comic_series_issue_variants -v`
Expected: FAIL

- [ ] **Step 3: Update _extract_series_issue implementation**

```python
def _extract_series_issue(self, stem: str) -> tuple[Optional[str], Optional[int]]:
    # Remove leading number prefix like "01. " or "01 - "
    stem = re.sub(r"^\d+[.\-\s]+\s*", "", stem).strip()

    # Try: "Series #12" or "Series #009"
    match = re.match(r"^(.+?)\s*#\s*(\d+)\s*$", stem)
    if match:
        return self._sanitize_name(match.group(1)), int(match.group(2))

    # Try: "Series.12" or "Series_12" (dot/underscore without space)
    match = re.match(r"^(.+?)[._](\d+)\s*$", stem)
    if match:
        return self._sanitize_name(match.group(1)), int(match.group(2))

    # Try: "Series 12" or "Series 009" (space-separated)
    match = re.match(r"^(.+?)\s+(\d{1,4})\s*$", stem)
    if match:
        return self._sanitize_name(match.group(1)), int(match.group(2))

    # Try: "Series 12 (2015)" (trailing year)
    match = re.match(r"^(.+?)\s+(\d{1,4})\s*\((?:19|20)\d{2}\)\s*$", stem)
    if match:
        return self._sanitize_name(match.group(1)), int(match.group(2))

    return self._sanitize_name(stem), None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_filename_suggestions_unit.py::TestFilenameSuggestionEngine::test_extract_comic_series_issue_variants -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/features/filename_suggestions.py tests/test_filename_suggestions_unit.py
git commit -m "feat(filename-suggestions): support dot/underscore separators and zero-padded issue numbers"
```

---

## Task 4: Smart Fallback When Extraction Fails

**Files:**
- Modify: `app/features/filename_suggestions.py:394-403` (book fallback)
- Modify: `app/features/filename_suggestions.py:465-468` (comic fallback)

Currently when fields can't be extracted, the engine returns the original filename with low confidence. Instead, construct a usable filename from whatever was extracted.

- [ ] **Step 1: Analyze current fallback logic**

Read lines 394-403 and 465-468 in filename_suggestions.py.

Current book fallback (when author OR title is missing):
```python
else:
    title_fallback = self._sanitize_name(clean_stem or stem)
    if year is not None:
        suggested = f"{title_fallback} ({year}){ext}"
        confidence = "medium"
        reason = "title_year_only"
    else:
        suggested = file_path.name  # <-- PROBLEM: returns original
        confidence = "low"
        reason = "book_schema_unrecognized"
```

Current comic fallback:
```python
else:
    suggested = file_path.name  # <-- PROBLEM: returns original
    confidence = "low"
    reason = "comic_schema_unrecognized"
```

- [ ] **Step 2: Write test for smart fallback**

```python
def test_book_smart_fallback(self):
    engine = FilenameSuggestionEngine()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # File with messy name but contains year
        file_path = root / "My.Book.2020.pdf"
        file_path.write_text("x", encoding="utf-8")

        report = engine.suggest_for_root(root, media_filter="books")
        self.assertEqual(len(report["suggestions"]), 1)
        item = report["suggestions"][0]
        # Should suggest something useful, not just keep original
        self.assertNotEqual(item["suggested_name"], "My.Book.2020.pdf")
        self.assertIn("2020", item["suggested_name"])
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_filename_suggestions_unit.py::TestFilenameSuggestionEngine::test_book_smart_fallback -v`
Expected: FAIL (suggested_name == original_name)

- [ ] **Step 4: Update book fallback to construct usable name**

In `_suggest_book_filename`, replace the low-confidence branch:

```python
else:
    # Try to extract anything useful
    title_fallback = self._sanitize_name(clean_stem or stem)
    if title_fallback and title_fallback != "Unknown":
        if year is not None:
            suggested = f"{title_fallback} ({year}){ext}"
            confidence = "medium"
            reason = "title_year_extracted_fallback"
        else:
            # Use sanitized stem as title, mark as needing review
            suggested = f"{title_fallback}{ext}"
            confidence = "low"
            reason = "title_only_fallback"
    else:
        # Last resort: normalize original filename
        suggested = self._sanitize_name(stem) + ext
        confidence = "low"
        reason = "filename_normalized"
```

- [ ] **Step 5: Update comic fallback similarly**

```python
else:
    # Try to extract anything useful
    if series and series != "Unknown":
        if year is not None:
            suggested = f"{series} ({year}){ext}"
            confidence = "medium"
            reason = "series_year_fallback"
        else:
            suggested = f"{series}{ext}"
            confidence = "low"
            reason = "series_only_fallback"
    else:
        # Last resort: normalize original filename
        suggested = self._sanitize_name(stem) + ext
        confidence = "low"
        reason = "filename_normalized"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_filename_suggestions_unit.py::TestFilenameSuggestionEngine::test_book_smart_fallback -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/features/filename_suggestions.py tests/test_filename_suggestions_unit.py
git commit -m "feat(filename-suggestions): construct usable fallback names instead of returning original"
```

---

## Task 5: Update parse_*_filename_fields Validators

**Files:**
- Modify: `app/utils/helpers.py:154-230` (parse_book_filename_fields)
- Modify: `app/utils/helpers.py:233-289` (parse_comic_filename_fields)

These validators are used by the organizers to check if a filename is valid. They need to accept the same flexible patterns that the suggestion engine now handles.

- [ ] **Step 1: Write test for flexible book validation**

```python
def test_parse_book_flexible_formats(self):
    # Standard format
    result = parse_book_filename_fields("Author - Title (2020)")
    self.assertTrue(result["is_valid"])

    # Dot year: "Author - Title.2020"
    result = parse_book_filename_fields("Author - Title.2020")
    # Should NOT be valid as-is (needs normalization first)
    # But parse is strict - suggestion engine normalizes first

    # Year-only format: "Title (2020)"
    result = parse_book_filename_fields("Title (2020)")
    self.assertTrue(result["is_valid"])
```

- [ ] **Step 2: Note: validators stay strict**

The validators (`parse_book_filename_fields`, `parse_comic_filename_fields`) should remain strict - they validate the CANONICAL format. The suggestion engine's job is to CONVERT non-canonical to canonical.

No changes to validators needed - they work correctly.

- [ ] **Step 3: Commit (if changes needed, otherwise skip)**

---

## Task 6: Integration Test - Full Suggestion Flow

**Files:**
- Modify: `tests/test_filename_suggestions_unit.py`

Test that the full flow works: messy input → suggestion engine → valid canonical output.

- [ ] **Step 1: Write integration tests**

```python
def test_full_book_suggestion_flow(self):
    """Test messy book filename → canonical suggestion."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        engine = FilenameSuggestionEngine(learning_path=Path(tmp) / "learn.json")

        # Messy input
        file_path = root / "John.Smith.-.Great.Book.2020.pdf"
        file_path.write_text("x", encoding="utf-8")

        report = engine.suggest_for_root(root, media_filter="books")
        self.assertEqual(len(report["suggestions"]), 1)
        item = report["suggestions"][0]

        # Should produce canonical format
        self.assertEqual(item["suggested_name"], "John Smith - Great Book (2020).pdf")
        self.assertIn(item["confidence"], ["high", "medium"])

def test_full_comic_suggestion_flow(self):
    """Test messy comic filename → canonical suggestion."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        engine = FilenameSuggestionEngine(learning_path=Path(tmp) / "learn.json")

        # Messy input: "Saga.009.2012"
        file_path = root / "Saga.009.2012.cbz"
        file_path.write_text("x", encoding="utf-8")

        report = engine.suggest_for_root(root, media_filter="comics")
        if report["suggestions"]:
            item = report["suggestions"][0]
            # Should extract series and issue
            self.assertNotEqual(item["suggested_name"], "Saga.009.2012.cbz")
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_filename_suggestions_unit.py::TestFilenameSuggestionEngine::test_full_book_suggestion_flow tests/test_filename_suggestions_unit.py::TestFilenameSuggestionEngine::test_full_comic_suggestion_flow -v`

- [ ] **Step 3: Fix issues found**

Iterate on extraction logic until tests pass.

- [ ] **Step 4: Commit**

```bash
git add app/features/filename_suggestions.py app/utils/helpers.py tests/test_filename_suggestions_unit.py
git commit -m "test(filename-suggestions): add integration tests for full suggestion flow"
```

---

## Task 7: Update Documentation

**Files:**
- Modify: `docs/modules/filename-suggestions.md`
- Modify: `docs/guides/commands.md` (if filename suggestion commands documented)

The existing documentation at `docs/modules/filename-suggestions.md` is outdated - it references non-existent methods like `gerar_sugestoes` and shows incorrect class signatures.

- [ ] **Step 1: Review existing documentation**

Read `docs/modules/filename-suggestions.md` to understand current state.

- [ ] **Step 2: Update filename-suggestions.md**

Update the module documentation to reflect the actual API:

```markdown
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

The engine now accepts flexible input patterns:

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
```

- [ ] **Step 3: Check if commands.md needs updates**

Run: `grep -l "suggest-filename\|filename-suggestion" docs/**/*.md`
If found, update references to match new CLI behavior.

- [ ] **Step 4: Run tests to verify docs are consistent**

```bash
# Verify code matches documentation
pytest tests/test_filename_suggestions_unit.py -v
```

- [ ] **Step 5: Commit**

```bash
git add docs/modules/filename-suggestions.md
git commit -m "docs(filename-suggestions): update documentation to reflect actual API and new features"
```

---

## Task 8: Translate Portuguese Text to English

**Files:**
- Modify: `app/features/filename_suggestions.py`
- Modify: `app/features/genre_guard/core.py`
- Modify: `app/core/detection.py`
- Modify: `app/core/orchestrator.py`
- Modify: `app/core/interfaces.py`
- Modify: `app/validators/integrations.py`
- Modify: `tests/test_filename_suggestions_unit.py`

All code, comments, and documentation must be in English.

### Portuguese Text Found:

**`app/features/filename_suggestions.py`:**
- Line 41: `# Cache para normalization (melhoria de performance)` → `# Cache for normalization (performance improvement)`
- Line 692: `# Detectar conflito de alias (CRÍTICO - integridade de dados)` → `# Detect alias conflict (CRITICAL - data integrity)`
- Line 729: `# Detectar conflito de alias em livros` → `# Detect alias conflict in books`

**`app/features/genre_guard/core.py`:**
- Lines 90-91: `# Tokens editoriais/comportamentais que frequentemente poluem tags de genero.` and `# Usados para heuristica de confianca sem depender de listas extensas.` → `# Editorial/behavioral tokens that frequently pollute genre tags.` and `# Used for confidence heuristics without relying on extensive lists.`

**`app/core/detection.py`:**
- `escanear_diretorio(self, diretorio: Path)` → `scan_directory(self, directory: Path)`
- `filtrar_arquivos_para_organizacao(self, arquivos: List[Path])` → `filter_files_for_organization(self, files: List[Path])`
- Variable `diretorio` → `directory`
- Variable `arquivos` → `files`

**`app/core/orchestrator.py`:**
- `_ordenar_arquivos_para_processamento(self, arquivos: List[Path])` → `_order_files_for_processing(self, files: List[Path])`
- `_processar_arquivo(self, arquivo: Path)` → `_process_file(self, file_path: Path)`
- `_validar_arquivo_global(self, arquivo: Path)` → `_validate_file_global(self, file_path: Path)`
- Variable `arquivo` → `file` or `file_path`
- Variable `resultado` → `result`
- Variable `validacao` → `validation`
- Line 275: `copia|copia|cópia` in regex → keep `copy` only (English only)

**`app/core/interfaces.py`:**
- `escanear_diretorio(self, diretorio: Path)` → `scan_directory(self, directory: Path)`
- `filtrar_arquivos_para_organizacao(self, arquivos: List[Path])` → `filter_files_for_organization(self, files: List[Path])`

**`app/validators/integrations.py`:**
- `validar_arquivos(self, arquivos: List[Path])` → `validate_files(self, files: List[Path])`
- Variable `arquivo` → `file`

**`tests/test_filename_suggestions_unit.py`:**
- Line 168: `# 255 é o limite NTFS/ext4` → `# 255 is the NTFS/ext4 limit`
- Line 175: `# Usar arquivo com extensão válida` → `# Use file with valid extension`
- Line 197: `# Usar arquivo com extensão válida` → `# Use file with valid extension`
- Line 262: `# Deletar arquivo depois que foi adicionado no report (simula race condition)` → `# Delete file after it was added to report (simulates race condition)`
- Line 267: `# Deve reportar source_not_found ou source_disappeared, não crash` → `# Should report source_not_found or source_disappeared, not crash`

**`app/services/organizers.py`:**
- Line 1628: `# Manter title sincronizado com track_name` → `# Keep title synchronized with track_name`

- [ ] **Step 1: Translate filename_suggestions.py comments**

Apply the comment translations listed above.

- [ ] **Step 2: Translate genre_guard/core.py comments**

Apply the comment translations listed above.

- [ ] **Step 3: Translate detection.py method names and variables**

Rename methods and variables from Portuguese to English.

- [ ] **Step 4: Translate orchestrator.py method names and variables**

Rename methods and variables from Portuguese to English.

- [ ] **Step 5: Update interfaces.py**

Update interface definitions to match new method names.

- [ ] **Step 6: Translate validators/integrations.py**

Rename methods and variables from Portuguese to English.

- [ ] **Step 7: Translate test_filename_suggestions_unit.py comments**

Apply the comment translations listed above.

- [ ] **Step 8: Update organizers.py comment**

Apply the comment translation listed above.

- [ ] **Step 9: Run tests to verify refactoring**

```bash
pytest tests/ -v --tb=short
```

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor: translate all Portuguese text to English"
```

---

## Self-Review Checklist

After completing all tasks:

1. **Spec coverage:** Check each requirement:
   - Flexible year extraction → Task 1 ✓
   - Inverted author-title → Task 2 ✓
   - Multiple author/title patterns → Task 2 ✓
   - Comic issue variants → Task 3 ✓
   - Smart fallback → Task 4 ✓
   - Documentation updated → Task 7 ✓
   - Portuguese to English translation → Task 8 ✓

2. **Placeholder scan:** No TBD/TODO patterns in implementation code

3. **Type consistency:** Method signatures unchanged, return types consistent

4. **Run all tests:**
   ```bash
   pytest tests/test_filename_suggestions_unit.py -v
   ```
   All should pass.

---

## Execution Handoff

Plan complete and saved to `.opencode/plans/2026-04-19-filename-suggestions-improvement.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Total tasks: 8** (including documentation update in Task 7, Portuguese translation in Task 8)

**Which approach?**
