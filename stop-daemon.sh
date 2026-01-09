#!/bin/bash

# Media Organizer - Stop Daemon
# Stops the running daemon process

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if PID file exists
if [ ! -f ".daemon.pid" ]; then
    echo "Error: Daemon is not running (no PID file found)"
    exit 1
fi

# Read PID
DAEMON_PID=$(cat .daemon.pid)

# Check if process is running
if ! ps -p $DAEMON_PID > /dev/null 2>&1; then
    echo "Warning: Daemon process (PID: $DAEMON_PID) is not running"
    rm .daemon.pid
    exit 1
fi

# Stop daemon
echo "Stopping Media Organizer Daemon (PID: $DAEMON_PID)..."
kill $DAEMON_PID

# Wait for process to stop (max 10 seconds)
for i in {1..10}; do
    if ! ps -p $DAEMON_PID > /dev/null 2>&1; then
        echo "✓ Daemon stopped successfully"
        rm .daemon.pid
        exit 0
    fi
    sleep 1
done

# Force kill if still running
echo "Warning: Daemon did not stop gracefully, forcing..."
kill -9 $DAEMON_PID
rm .daemon.pid
echo "✓ Daemon force-stopped"
