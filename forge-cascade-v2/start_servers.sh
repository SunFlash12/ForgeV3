#!/bin/bash
# Forge V3 - Start All Servers (Unix/Linux/Mac)
#
# Starts all three API servers:
# - Cascade API (port 8001)
# - Compliance API (port 8002)
# - Virtuals API (port 8003)
#
# Usage:
#   ./start_servers.sh          # Start all servers
#   ./start_servers.sh stop     # Stop all servers

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PID_DIR="$SCRIPT_DIR/.pids"
mkdir -p "$PID_DIR"

start_servers() {
    echo "============================================================"
    echo "FORGE V3 - Starting API Servers"
    echo "============================================================"

    # Start Cascade API
    echo "Starting Cascade API on port 8001..."
    python -m uvicorn forge.api.app:app --host 0.0.0.0 --port 8001 &
    echo $! > "$PID_DIR/cascade.pid"

    # Start Compliance API
    echo "Starting Compliance API on port 8002..."
    python run_compliance.py &
    echo $! > "$PID_DIR/compliance.pid"

    # Start Virtuals API
    echo "Starting Virtuals API on port 8003..."
    python run_virtuals.py &
    echo $! > "$PID_DIR/virtuals.pid"

    sleep 3

    echo ""
    echo "============================================================"
    echo "All servers started:"
    echo "  - Cascade API:    http://localhost:8001 (PID: $(cat $PID_DIR/cascade.pid 2>/dev/null))"
    echo "  - Compliance API: http://localhost:8002 (PID: $(cat $PID_DIR/compliance.pid 2>/dev/null))"
    echo "  - Virtuals API:   http://localhost:8003 (PID: $(cat $PID_DIR/virtuals.pid 2>/dev/null))"
    echo "============================================================"
    echo ""
    echo "Run './start_servers.sh stop' to stop all servers"
}

stop_servers() {
    echo "Stopping all servers..."

    for pid_file in "$PID_DIR"/*.pid; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                echo "  Stopping PID $pid..."
                kill "$pid" 2>/dev/null
            fi
            rm -f "$pid_file"
        fi
    done

    echo "All servers stopped."
}

case "${1:-start}" in
    start)
        start_servers
        ;;
    stop)
        stop_servers
        ;;
    restart)
        stop_servers
        sleep 2
        start_servers
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
        ;;
esac
