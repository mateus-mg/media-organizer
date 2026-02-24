#!/bin/bash
# Subtitle Daemon Manager
# Controls the Subtitle Downloader Daemon

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

# Paths
PID_FILE=".subtitle_daemon.pid"
LOG_FILE="logs/subtitle_downloader.log"
ENV_FILE=".env"

# Ensure log directory exists
mkdir -p logs

# Check if daemon is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            # Stale PID file
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Check setup
check_setup() {
    if [ ! -d "venv" ]; then
        echo -e "${RED}Error: Virtual environment not found. Run ./run.sh first.${NC}"
        exit 1
    fi

    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${RED}Error: .env file not found${NC}"
        exit 1
    fi

    # Check if OpenSubtitles is configured
    if ! grep -q "OPENSUBTITLES_API_KEY" "$ENV_FILE" || \
       grep -q "OPENSUBTITLES_API_KEY=\"your_api_key_here\"" "$ENV_FILE"; then
        echo -e "${YELLOW}Warning: OpenSubtitles API not configured${NC}"
        echo "Please edit .env and set:"
        echo "  OPENSUBTITLES_API_KEY=your_key"
        echo "  OPENSUBTITLES_USERNAME=your_username"
        echo "  OPENSUBTITLES_PASSWORD=your_password"
        echo ""
    fi
}

# ============================================
# COMMANDS
# ============================================

case "$1" in
    "start")
        echo -e "${CYAN}Starting Subtitle Daemon...${NC}"

        if is_running; then
            PID=$(cat "$PID_FILE")
            echo -e "${RED}Error: Daemon already running (PID: $PID)${NC}"
            exit 1
        fi

        check_setup

        # Activate venv
        source venv/bin/activate

        # Run in background
        nohup python -m src.subtitle_daemon >> "$LOG_FILE" 2>&1 &

        # Save PID
        DAEMON_PID=$!
        echo "$DAEMON_PID" > "$PID_FILE"

        sleep 2

        if is_running; then
            echo -e "${GREEN}✓ Daemon started successfully!${NC}"
            echo ""
            echo "  PID:      $DAEMON_PID"
            echo "  Log:      $LOG_FILE"
            echo "  Config:   $SCRIPT_DIR/$ENV_FILE"
            echo ""
            echo "Commands:"
            echo "  subtitle-daemon status  # Check status"
            echo "  subtitle-daemon stop    # Stop daemon"
            echo "  tail -f $LOG_FILE       # View logs"
        else
            echo -e "${RED}✗ Failed to start daemon${NC}"
            echo "Check logs: $LOG_FILE"
            rm -f "$PID_FILE"
            exit 1
        fi
        ;;

    "stop")
        echo -e "${CYAN}Stopping Subtitle Daemon...${NC}"

        if ! is_running; then
            echo -e "${YELLOW}Daemon is not running${NC}"
            exit 0
        fi

        PID=$(cat "$PID_FILE")

        # Try graceful stop
        kill "$PID"

        # Wait up to 10 seconds
        for i in {1..10}; do
            if ! is_running; then
                echo -e "${GREEN}✓ Daemon stopped gracefully${NC}"
                rm -f "$PID_FILE"
                exit 0
            fi
            sleep 1
        done

        # Force stop
        echo -e "${YELLOW}Warning: Forcing stop...${NC}"
        kill -9 "$PID" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo -e "${GREEN}✓ Daemon force-stopped${NC}"
        ;;

    "restart")
        echo -e "${CYAN}Restarting Subtitle Daemon...${NC}"

        # Stop if running
        if is_running; then
            "$0" stop > /dev/null 2>&1
            sleep 2
        fi

        # Start
        "$0" start
        ;;

    "status")
        echo -e "${CYAN}Subtitle Daemon Status${NC}"
        echo "================================"

        if ! is_running; then
            echo -e "${RED}Status: NOT RUNNING${NC}"

            # Check for stale PID file
            if [ -f "$PID_FILE" ]; then
                OLD_PID=$(cat "$PID_FILE")
                echo -e "${YELLOW}Stale PID file found: $OLD_PID (cleaning up)${NC}"
                rm -f "$PID_FILE"
            fi

            echo ""
            echo "To start: subtitle-daemon start"
            exit 0
        fi

        PID=$(cat "$PID_FILE")

        # Get process info
        if PROC_INFO=$(ps -p "$PID" -o pid,etime,pcpu,pmem,cmd --no-headers 2>/dev/null); then
            UPTIME=$(echo "$PROC_INFO" | awk '{print $2}')
            CPU=$(echo "$PROC_INFO" | awk '{print $3}')
            MEM=$(echo "$PROC_INFO" | awk '{print $4}')

            echo -e "${GREEN}Status: RUNNING ✓${NC}"
            echo "  PID:      $PID"
            echo "  Uptime:   $UPTIME"
            echo "  CPU:      $CPU%"
            echo "  Memory:   $MEM%"
            echo "  Log file: $LOG_FILE"
        else
            echo -e "${RED}Status: ERROR (can't get process info)${NC}"
        fi

        echo ""

        # Show recent log entries
        if [ -f "$LOG_FILE" ]; then
            echo "Recent log entries:"
            echo "-------------------"
            tail -n 10 "$LOG_FILE" 2>/dev/null || echo "(Log file empty)"
        else
            echo "No log file found"
        fi

        echo ""
        echo "Commands:"
        echo "  subtitle-daemon stop        # Stop daemon"
        echo "  subtitle-daemon restart     # Restart daemon"
        echo "  tail -f $LOG_FILE           # View live logs"
        ;;

    "logs")
        if [ ! -f "$LOG_FILE" ]; then
            echo -e "${RED}Log file not found: $LOG_FILE${NC}"
            exit 1
        fi

        case "$2" in
            "tail"|"follow")
                echo -e "${CYAN}Following log file (Ctrl+C to stop)...${NC}"
                echo "==========================================="
                tail -f "$LOG_FILE"
                ;;
            "error"|"errors")
                echo -e "${CYAN}Showing errors from log...${NC}"
                grep -i "error\|fail\|exception\|warning" "$LOG_FILE" | tail -30
                ;;
            "clear")
                echo -e "${CYAN}Clearing log file...${NC}"
                > "$LOG_FILE"
                echo -e "${GREEN}✓ Log cleared${NC}"
                ;;
            "stats")
                echo -e "${CYAN}Subtitle statistics:${NC}"
                grep -i "download\|cycle\|complete" "$LOG_FILE" | tail -20
                ;;
            *)
                # Show last 50 lines by default
                echo -e "${CYAN}Last 50 lines of log:${NC}"
                echo "==========================================="
                tail -n 50 "$LOG_FILE"
                echo ""
                echo "Log options:"
                echo "  $0 logs tail    # Follow logs in real-time"
                echo "  $0 logs error   # Show only errors"
                echo "  $0 logs stats   # Show download statistics"
                echo "  $0 logs clear   # Clear log file"
                ;;
        esac
        ;;

    "run")
        # Run once manually (not as daemon)
        echo -e "${CYAN}Running manual subtitle download...${NC}"

        check_setup
        source venv/bin/activate

        python -c "
import asyncio
from src.subtitle_config import SubtitleConfig
from src.subtitle_downloader import SubtitleDownloader
from src.persistence import OrganizationDatabase
from src.log_config import get_logger

config = SubtitleConfig()
logger = get_logger(name='SubtitleManual')
database = OrganizationDatabase(config.database_path)
downloader = SubtitleDownloader(config, database, logger)

if not downloader.ensure_authenticated():
    print('Failed to authenticate')
    exit(1)

stats = downloader.process_all_media()
print('Statistics:', stats)
"
        ;;

    "test")
        echo -e "${CYAN}Testing Subtitle Downloader Configuration...${NC}"
        echo "=============================================="

        check_setup
        source venv/bin/activate

        echo ""
        echo "1. Testing Python environment..."
        python -c "
import sys
print(f'✓ Python {sys.version}')
try:
    import requests
    print('✓ Requests library installed')
except ImportError:
    print('✗ Requests library missing')
    print('  Run: pip install -r requirements.txt')
"

        echo ""
        echo "2. Testing configuration..."
        python -c "
from src.subtitle_config import SubtitleConfig
config = SubtitleConfig()

print(f'  API Key: {\"Set\" if config.api_key and config.api_key != \"your_api_key_here\" else \"Not set\"}')
print(f'  Username: {config.api_username or \"Not set\"}')
print(f'  Languages: {\", \".join(config.preferred_languages)}')
print(f'  Download limit: {config.download_limit}/day')
print(f'  Check interval: {config.check_interval // 3600}h')
print(f'  Daemon enabled: {config.daemon_enabled}')

if not config.is_valid:
    print('')
    print('Validation errors:')
    for error in config.validation_errors:
        print(f'  ✗ {error}')
else:
    print('')
    print('✓ Configuration valid')
"

        echo ""
        echo "3. Testing database..."
        if [ -f "data/organization.json" ]; then
            COUNT=$(grep -c '"file_hash"' data/organization.json 2>/dev/null || echo "0")
            echo "  ✓ Database exists: $COUNT items"
        else
            echo "  ⚠ No database found (normal on first run)"
        fi

        echo ""
        echo -e "${GREEN}✓ Configuration test complete${NC}"
        ;;

    *)
        echo "Subtitle Daemon Manager"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|logs|run|test}"
        echo ""
        echo "Commands:"
        echo "  start       - Start daemon in background"
        echo "  stop        - Stop daemon"
        echo "  restart     - Restart daemon"
        echo "  status      - Show daemon status and info"
        echo "  logs        - View logs (add: tail, error, stats, clear)"
        echo "  run         - Run manual download (one-time)"
        echo "  test        - Test system configuration"
        echo ""
        echo "Examples:"
        echo "  $0 start              # Start daemon"
        echo "  $0 status             # Check status"
        echo "  $0 logs tail          # Follow logs"
        echo "  $0 run                # Manual download"
        exit 1
        ;;
esac
