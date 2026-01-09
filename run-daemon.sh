#!/bin/bash

# Media Organizer - Daemon Runner
# Executes media organization continuously with configured interval

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Run setup first."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Check if daemon is already running
if [ -f ".daemon.pid" ]; then
    OLD_PID=$(cat .daemon.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "Error: Daemon is already running (PID: $OLD_PID)"
        echo "Stop it first with: kill $OLD_PID"
        exit 1
    else
        # Remove stale PID file
        rm .daemon.pid
    fi
fi

# Run daemon mode in background with nohup
echo "Starting Media Organizer Daemon in background..."
nohup python -m src.main daemon > logs/daemon.log 2>&1 &

# Save PID
DAEMON_PID=$!
echo $DAEMON_PID > .daemon.pid

echo "✓ Daemon started successfully!"
echo "  PID: $DAEMON_PID"
echo "  Log: logs/daemon.log"
echo ""
echo "Commands:"
echo "  View logs:  tail -f logs/daemon.log"
echo "  Stop daemon: kill $DAEMON_PID"
echo "  Or use:      kill \$(cat .daemon.pid)"
