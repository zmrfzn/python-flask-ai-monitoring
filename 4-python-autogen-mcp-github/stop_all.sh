#!/bin/bash
# Stop all running services

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Stopping all services..."

# Kill processes by port (more reliable than PID files)
echo "Checking for processes on ports 8080, 8090, 8501..."

# Port 8090 - Tools server
TOOLS_PIDS=$(lsof -ti :8090 2>/dev/null)
if [ ! -z "$TOOLS_PIDS" ]; then
    echo "Stopping tools server on port 8090 (PIDs: $TOOLS_PIDS)..."
    kill $TOOLS_PIDS 2>/dev/null
    sleep 1
    # Force kill if still running
    if lsof -ti :8090 >/dev/null 2>&1; then
        echo "Force killing tools server..."
        kill -9 $TOOLS_PIDS 2>/dev/null
    fi
fi

# Port 8080 - Agent server
AGENT_PIDS=$(lsof -ti :8080 2>/dev/null)
if [ ! -z "$AGENT_PIDS" ]; then
    echo "Stopping agent server on port 8080 (PIDs: $AGENT_PIDS)..."
    kill $AGENT_PIDS 2>/dev/null
    sleep 1
    # Force kill if still running
    if lsof -ti :8080 >/dev/null 2>&1; then
        echo "Force killing agent server..."
        kill -9 $AGENT_PIDS 2>/dev/null
    fi
fi

# Port 8501 - Streamlit client
CLIENT_PIDS=$(lsof -ti :8501 2>/dev/null)
if [ ! -z "$CLIENT_PIDS" ]; then
    echo "Stopping client on port 8501 (PIDs: $CLIENT_PIDS)..."
    kill $CLIENT_PIDS 2>/dev/null
    sleep 1
    # Force kill if still running
    if lsof -ti :8501 >/dev/null 2>&1; then
        echo "Force killing client..."
        kill -9 $CLIENT_PIDS 2>/dev/null
    fi
fi

# Clean up PID files
rm -f logs/tools.pid logs/agent.pid logs/client.pid

echo "All services stopped."
