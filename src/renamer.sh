#!/bin/bash
# Renamer - Media File Renamer for Media Organizer System
# Wrapper script for standalone Renamer CLI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set PYTHONPATH
export PYTHONPATH="$SCRIPT_DIR/..:$PYTHONPATH"

# Run renamer Python module directly
python -m src.renamer "$@"
