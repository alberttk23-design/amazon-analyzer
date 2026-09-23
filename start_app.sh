#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "================================="
echo " Starting Amazon Analyzer v1.0"
echo "================================="

cd "$PROJECT_DIR"

# Clean up any lingering processes on ports 8001 and 5174
lsof -ti :8001 | xargs kill -9 2>/dev/null || true
lsof -ti :5174 | xargs kill -9 2>/dev/null || true

# Check Ollama service (Optional)
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "✓ Ollama is active"
else
    echo "Notice: Ollama not detected on localhost:11434, starting ollama serve in background..."
    ollama serve > /dev/null 2>&1 &
    sleep 2
fi

echo "Starting Backend (FastAPI + SQLite WAL on port 8001)..."
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Warning: .venv not found, using system python3"
fi
uvicorn backend.api:app --host 127.0.0.1 --port 8001 --reload > backend.log 2>&1 &
BACKEND_PID=$!

sleep 2

echo "Starting Frontend (React + Vite on port 5174)..."
cd frontend
npm run dev -- --port 5174 > frontend.log 2>&1 &
FRONTEND_PID=$!

sleep 3

echo ""
echo "================================="
echo " AMAZON ANALYZER IS RUNNING"
echo " Backend API: http://127.0.0.1:8001"
echo " Frontend UI: http://localhost:5174"
echo " Backend PID:  $BACKEND_PID"
echo " Frontend PID: $FRONTEND_PID"
echo " Press CTRL+C to stop all servers"
echo "================================="

# Trap exit signals to kill children cleanly
cleanup() {
    echo ""
    echo "Shutting down servers..."
    kill "$BACKEND_PID" 2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Open browser
open http://localhost:5174 2>/dev/null || true

wait
