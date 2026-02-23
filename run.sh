#!/bin/bash
# Quick start script for Media Organization System

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Media Organization System${NC}"
echo "==============================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$SCRIPT_DIR/venv"
fi

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Set PYTHONPATH to include project root
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"

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
mkdir -p "$SCRIPT_DIR/data"
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/data/backups"

echo -e "${GREEN}Environment ready!${NC}"
echo ""

# Run the application with all arguments
python -m src.main "$@"