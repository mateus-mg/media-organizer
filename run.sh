#!/bin/bash
# Quick start script for Media Organization System

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Load environment overrides from .env (if present)
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$SCRIPT_DIR/.env"
    set +a
fi

VENV_DIR="${MEDIA_ORG_VENV_DIR:-$SCRIPT_DIR/venv}"
PYTHON_BIN="${MEDIA_ORG_PYTHON_BIN:-python3}"
DATA_DIR="${MEDIA_ORG_DATA_DIR:-$SCRIPT_DIR/data}"
LOGS_DIR="${MEDIA_ORG_LOGS_DIR:-$SCRIPT_DIR/logs}"
BACKUPS_DIR="${MEDIA_ORG_BACKUPS_DIR:-$SCRIPT_DIR/data/backups}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Media Organization System${NC}"
echo "==============================="

# Check if Python is available
if ! command -v "$PYTHON_BIN" &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Set PYTHONPATH to include project root
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Check if dependencies are installed
if ! python -c "import rich" &> /dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install --upgrade pip
    pip install -r "$SCRIPT_DIR/requirements.txt"
fi

# Check if .env exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        echo -e "${YELLOW}Creating .env file from template...${NC}"
        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        echo -e "${YELLOW}⚠ Please edit .env file with your paths and API keys${NC}"
        echo ""
    else
        echo -e "${RED}Warning: .env file not found and no .env.example template${NC}"
        echo "Create a .env file with your configuration."
    fi
fi

# Create necessary directories
mkdir -p "$DATA_DIR"
mkdir -p "$LOGS_DIR"
mkdir -p "$BACKUPS_DIR"

echo -e "${GREEN}Environment ready!${NC}"
echo ""

# Run the application with all arguments
python -m app.main "$@"