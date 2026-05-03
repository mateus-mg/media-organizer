# Task 7 Learnings

## Implementation
- Added `analyze-genres` CLI command to `app/main.py`
- Command is read-only: only reads database, never modifies files or databases
- Uses `Config.database_path` (not `data_dir`) to locate the organization database
- Filters `media_type == "music"` records from `db["media"]` dict (not a `music` list)
- Integrates with existing `GenreExpander.infer_parent()` from smart_playlists feature

## QA Results
- `./run.sh analyze-genres --help` works correctly
- Empty library returns "Nenhum genero encontrado na biblioteca"
- Simulated data correctly groups genres (rock, electronic) and shows ungrouped (jazz)
- All 198 existing unit tests pass after change

## Commit
- Message: feat(cli): add analyze-genres command
- Files: app/main.py, .sisyphus/evidence/task-7-cli-test.txt
