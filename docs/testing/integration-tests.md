# Navidrome Integration Tests

## Quick Start

Run integration tests against a real Navidrome server:

```bash
# One command - starts server, runs tests, stops server
./scripts/run-integration-tests.sh

# Or manually:
docker-compose -f docker-compose.test.yml up -d
python -m pytest tests/integration/ -v
docker-compose -f docker-compose.test.yml down -v
```

## What This Tests

Unlike unit tests that use mocks, integration tests verify:

- **Real API calls** to Navidrome Subsonic endpoints
- **File serialization** - actual `.nsp` files are written and read
- **Validation** - invalid fields/operators are rejected before reaching Navidrome
- **End-to-end workflows** - from Python API to filesystem to Navidrome

## Test Server

- **Image:** `deluan/navidrome:latest`
- **Port:** `localhost:4534`
- **Credentials:** `admin` / `test123`
- **Data:** Isolated in `tests/integration/fixtures/`
- **Lifecycle:** Created before tests, destroyed after

## Running Tests Without Docker

If you have a real Navidrome server:

```bash
export NAVIDROME_TEST_URL="http://your-server:4533"
export NAVIDROME_TEST_USER="admin"
export NAVIDROME_TEST_PASS="yourpassword"
python -m pytest tests/integration/ -v
```

**Warning:** Tests create/delete playlists with prefix `TEST_`.
