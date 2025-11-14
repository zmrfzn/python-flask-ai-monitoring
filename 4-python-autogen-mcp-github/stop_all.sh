#!/bin/bash
# Stop all running services

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Stopping all services..."

# Stop services by PID files
if [ -f logs/tools.pid ]; then
    TOOLS_PID=$(cat logs/tools.pid)
    if kill -0 "$TOOLS_PID" 2>/dev/null; then
        echo "Stopping tools server (PID: $TOOLS_PID)..."
        kill "$TOOLS_PID"
    fi
    rm logs/tools.pid
fi

if [ -f logs/agent.pid ]; then
    AGENT_PID=$(cat logs/agent.pid)
    if kill -0 "$AGENT_PID" 2>/dev/null; then
        echo "Stopping agent server (PID: $AGENT_PID)..."
        kill "$AGENT_PID"
    fi
    rm logs/agent.pid
fi

if [ -f logs/client.pid ]; then
    CLIENT_PID=$(cat logs/client.pid)
    if kill -0 "$CLIENT_PID" 2>/dev/null; then
        echo "Stopping client (PID: $CLIENT_PID)..."
        kill "$CLIENT_PID"
    fi
    rm logs/client.pid
fi

# Also kill any stray processes that might be using the ports
echo "Checking for stray processes on ports 8080, 8090, 8501..."
STRAY_PIDS=$(lsof -ti :8080,:8090,:8501 2>/dev/null)
if [ ! -z "$STRAY_PIDS" ]; then
    echo "Found stray processes: $STRAY_PIDS"
    echo "Killing stray processes..."
    kill $STRAY_PIDS 2>/dev/null
    sleep 1
    # Force kill if still running
    kill -9 $STRAY_PIDS 2>/dev/null
fi

echo "All services stopped."
