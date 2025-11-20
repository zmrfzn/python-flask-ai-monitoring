#!/bin/bash
# Start all three services: tools server, agent server, and client

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Clear existing logs
echo "Clearing previous logs..."
rm -f logs/tools.log logs/agent.log logs/client.log logs/newrelic.log

echo "Starting all services..."
echo "========================"

# Start tools server in background
echo "Starting tools server on port 8090..."
uv run python tools/tools_server.py > logs/tools.log 2>&1 &
TOOLS_PID=$!
echo "Tools server PID: $TOOLS_PID"

# Wait longer for tools server to fully initialize (New Relic + MCP setup)
echo "Waiting for tools server to initialize..."
sleep 3

# Start agent server in background
echo "Starting agent server on port 8080..."
uv run python server/agent.py --port 8080 > logs/agent.log 2>&1 &
AGENT_PID=$!
echo "Agent server PID: $AGENT_PID"

# Wait a moment for agent server to start
sleep 2

# Start Streamlit client in background
echo "Starting Streamlit client on port 8501..."
uv run streamlit run client/client.py > logs/client.log 2>&1 &
CLIENT_PID=$!
echo "Client PID: $CLIENT_PID"

echo ""
echo "========================"
echo "All services started!"
echo "========================"
echo "Tools Server:  http://localhost:8090"
echo "Agent Server:  http://localhost:8080"
echo "Client UI:     http://localhost:8501"
echo ""
echo "Process IDs:"
echo "  Tools:  $TOOLS_PID"
echo "  Agent:  $AGENT_PID"
echo "  Client: $CLIENT_PID"
echo ""
echo "To stop all services, run: ./stop_all.sh"
echo "Or manually: kill $TOOLS_PID $AGENT_PID $CLIENT_PID"
echo ""
echo "Logs are in the logs/ directory:"
echo "  tools.log, agent.log, client.log"

# Save PIDs to file for stop script
echo "$TOOLS_PID" > logs/tools.pid
echo "$AGENT_PID" > logs/agent.pid
echo "$CLIENT_PID" > logs/client.pid
