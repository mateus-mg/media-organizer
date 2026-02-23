#!/bin/bash
# Media Organizer Daemon Manager (single script)
# Compatível com seu wrapper media-organizer

set -e

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configurações
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
PID_FILE=".daemon.pid"
LOG_FILE="logs/daemon.log"

# Verificar se daemon está rodando
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Verificar dependências
check_setup() {
    if [ ! -d "venv" ]; then
        echo -e "${RED}Error: Virtual environment not found. Run ./run.sh first.${NC}"
        exit 1
    fi
    
    if [ ! -f ".env" ]; then
        echo -e "${RED}Error: .env file not found${NC}"
        exit 1
    fi
    
    mkdir -p logs
    mkdir -p data/backups
}

# ============================================
# SUBCOMANDOS PRINCIPAIS
# ============================================

case "$1" in
    "start")
        echo -e "${CYAN}Starting Media Organizer Daemon...${NC}"
        
        if is_running; then
            PID=$(cat "$PID_FILE")
            echo -e "${RED}Error: Daemon already running (PID: $PID)${NC}"
            exit 1
        fi
        
        check_setup
        
        # Ativar venv
        source venv/bin/activate
        
        # Executar em background
        nohup python -m src.main daemon >> "$LOG_FILE" 2>&1 &
        
        # Salvar PID
        DAEMON_PID=$!
        echo "$DAEMON_PID" > "$PID_FILE"
        
        sleep 2
        
        if is_running; then
            echo -e "${GREEN}✓ Daemon started successfully!${NC}"
            echo ""
            echo "  PID:      $DAEMON_PID"
            echo "  Log:      $LOG_FILE"
            echo "  Config:   $SCRIPT_DIR/.env"
            echo ""
            echo "Commands:"
            echo "  media-organizer status  # Check status"
            echo "  media-organizer stop    # Stop daemon"
            echo "  tail -f $LOG_FILE      # View logs"
        else
            echo -e "${RED}✗ Failed to start daemon${NC}"
            echo "Check logs: $LOG_FILE"
            rm -f "$PID_FILE"
            exit 1
        fi
        ;;
        
    "stop")
        echo -e "${CYAN}Stopping Media Organizer Daemon...${NC}"
        
        if ! is_running; then
            echo -e "${YELLOW}Daemon is not running${NC}"
            exit 0
        fi
        
        PID=$(cat "$PID_FILE")
        
        # Tentar parada graciosa
        kill "$PID"
        
        # Esperar até 10 segundos
        for i in {1..10}; do
            if ! is_running; then
                echo -e "${GREEN}✓ Daemon stopped gracefully${NC}"
                rm -f "$PID_FILE"
                exit 0
            fi
            sleep 1
        done
        
        # Forçar parada
        echo -e "${YELLOW}Warning: Forcing stop...${NC}"
        kill -9 "$PID" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo -e "${GREEN}✓ Daemon force-stopped${NC}"
        ;;
        
    "status")
        echo -e "${CYAN}Media Organizer Daemon Status${NC}"
        echo "================================"
        
        if ! is_running; then
            echo -e "${RED}Status: NOT RUNNING${NC}"
            
            # Verificar se há PID file obsoleto
            if [ -f "$PID_FILE" ]; then
                OLD_PID=$(cat "$PID_FILE")
                echo -e "${YELLOW}Stale PID file found: $OLD_PID (cleaning up)${NC}"
                rm -f "$PID_FILE"
            fi
            
            echo ""
            echo "To start: media-organizer start"
            exit 0
        fi
        
        PID=$(cat "$PID_FILE")
        
        # Obter informações do processo
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
        
        # Mostrar últimas entradas do log
        if [ -f "$LOG_FILE" ]; then
            echo "Recent log entries:"
            echo "-------------------"
            tail -n 8 "$LOG_FILE" 2>/dev/null || echo "(Log file empty)"
        else
            echo "No log file found"
        fi
        
        echo ""
        echo "Commands:"
        echo "  media-organizer stop        # Stop daemon"
        echo "  tail -f $LOG_FILE          # View live logs"
        echo "  media-organizer stats       # Show statistics"
        ;;
        
    "restart")
        echo -e "${CYAN}Restarting Media Organizer Daemon...${NC}"
        
        # Parar se estiver rodando
        if is_running; then
            "$0" stop > /dev/null 2>&1
            sleep 2
        fi
        
        # Iniciar
        "$0" start
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
            *)
                # Mostrar últimas 50 linhas por padrão
                echo -e "${CYAN}Last 50 lines of log:${NC}"
                echo "==========================================="
                tail -n 50 "$LOG_FILE"
                echo ""
                echo "Log options:"
                echo "  $0 logs tail    # Follow logs in real-time"
                echo "  $0 logs error   # Show only errors"
                echo "  $0 logs clear   # Clear log file"
                ;;
        esac
        ;;
        
    "test")
        echo -e "${CYAN}Testing Media Organizer Configuration...${NC}"
        echo "=============================================="
        
        check_setup
        source venv/bin/activate
        
        echo ""
        echo "1. Testing Python environment..."
        python -c "
import sys
print(f'✓ Python {sys.version}')
try:
    import rich
    print('✓ Rich library installed')
except ImportError:
    print('✗ Rich library missing')
        "
        
        echo ""
        echo "2. Testing paths from .env..."
        
        # Carregar .env temporariamente
        while IFS='=' read -r key value; do
            if [[ $key == LIBRARY_PATH_* ]] || [[ $key == DOWNLOAD_PATH_* ]]; then
                if [[ -n $value ]]; then
                    if [ -d "$value" ]; then
                        count=$(find "$value" -type f 2>/dev/null | wc -l)
                        echo "  ✓ $key: $count files"
                    else
                        echo "  ✗ $key: $value (not found)"
                    fi
                fi
            fi
        done < .env
        
        echo ""
        echo "3. Testing database..."
        if [ -f "data/organization.json" ]; then
            count=$(grep -c '"media_type"' data/organization.json 2>/dev/null || echo "0")
            echo "  ✓ Database exists: $count items"
        else
            echo "  ⚠ No database found (normal on first run)"
        fi
        
        echo ""
        echo -e "${GREEN}✓ Configuration test complete${NC}"
        ;;
        
    *)
        echo "Media Organizer Daemon Manager"
        echo "Usage: $0 {start|stop|restart|status|logs|test}"
        echo ""
        echo "Commands:"
        echo "  start     - Start daemon in background"
        echo "  stop      - Stop daemon"
        echo "  restart   - Restart daemon"
        echo "  status    - Show daemon status and info"
        echo "  logs      - View logs (add: tail, error, clear)"
        echo "  test      - Test system configuration"
        exit 1
        ;;
esac