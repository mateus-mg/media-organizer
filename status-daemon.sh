#!/bin/bash

# Media Organizer - Check Daemon Status
# Shows if daemon is running and its details

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Media Organizer Daemon Status ==="
echo ""

# Check if PID file exists
if [ ! -f ".daemon.pid" ]; then
    echo "Status: ❌ NOT RUNNING (no PID file)"
    exit 0
fi

# Read PID
DAEMON_PID=$(cat .daemon.pid)

# Check if process is running
if ! ps -p $DAEMON_PID > /dev/null 2>&1; then
    echo "Status: ❌ NOT RUNNING (stale PID: $DAEMON_PID)"
    echo ""
    echo "Cleaning up stale PID file..."
    rm .daemon.pid
    exit 0
fi

# Get process info
PROCESS_INFO=$(ps -p $DAEMON_PID -o pid,etime,cmd --no-headers)

echo "Status: ✓ RUNNING"
echo "PID: $DAEMON_PID"
echo "Uptime: $(echo $PROCESS_INFO | awk '{print $2}')"
echo "Log file: logs/daemon.log"
echo ""
echo "Commands:"
echo "  View live logs:  tail -f logs/daemon.log"
echo "  Stop daemon:     ./stop-daemon.sh"
echo ""
echo "Recent log entries:"
echo "-------------------"
tail -n 10 logs/daemon.log 2>/dev/null || echo "(No log file yet)"
