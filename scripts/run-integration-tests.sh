#!/bin/bash
# Integration test runner for Navidrome

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker compose.test.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🎵 Navidrome Integration Tests"
echo "=============================="

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running${NC}"
    exit 1
fi

# Create test music fixtures if needed
if [ ! -d "${PROJECT_ROOT}/tests/integration/fixtures/music" ]; then
    mkdir -p "${PROJECT_ROOT}/tests/integration/fixtures/music"
fi

# Clean previous data to ensure fresh state
rm -rf "${PROJECT_ROOT}/tests/integration/fixtures/data"/*

# Start Navidrome test container
echo ""
echo "🚀 Starting Navidrome test server..."
docker compose -f "${COMPOSE_FILE}" up -d

# Wait for Navidrome to be ready
echo ""
echo "⏳ Waiting for Navidrome to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0
while ! curl -s -o /dev/null -w "%{http_code}" http://localhost:4534/app | grep -q "200"; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ Navidrome failed to start after ${MAX_RETRIES} attempts${NC}"
        docker compose -f "${COMPOSE_FILE}" logs
        docker compose -f "${COMPOSE_FILE}" down -v
        exit 1
    fi
    echo "   Attempt ${RETRY_COUNT}/${MAX_RETRIES}..."
    sleep 2
done

echo -e "${GREEN}✅ Navidrome is ready!${NC}"

# Create first admin user
echo ""
echo "👤 Creating test admin user..."
"${PROJECT_ROOT}/.venv/bin/python" "${PROJECT_ROOT}/tests/integration/setup_navidrome_user.py"
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to create admin user${NC}"
    docker compose -f "${COMPOSE_FILE}" down -v
    exit 1
fi

# Run tests
echo ""
echo "🧪 Running integration tests..."
cd "${PROJECT_ROOT}"
"${PROJECT_ROOT}/.venv/bin/python" -m pytest tests/integration/test_navidrome_integration.py -v \
    --tb=short

# Show results
echo ""
echo "=============================="
TEST_RESULT=$?

if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ All integration tests passed!${NC}"
else
    echo -e "${YELLOW}⚠️  Some tests failed (see output above)${NC}"
fi

# Stop container
echo ""
echo "🛑 Stopping Navidrome test server..."
docker compose -f "${COMPOSE_FILE}" down -v

echo ""
echo "Done!"

exit $TEST_RESULT
