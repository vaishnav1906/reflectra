#!/bin/bash
# Complete restart of both frontend and backend

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "Restarting Reflectra services..."
echo ""

echo "Stopping existing processes..."
pkill -f "uvicorn app.main" 2>/dev/null && echo "  Stopped backend" || echo "  No backend running"
pkill -f "vite.*8080" 2>/dev/null && echo "  Stopped frontend" || echo "  No frontend running"
sleep 2

echo ""
echo "Installing backend dependencies..."
source .venv/bin/activate || (python3 -m venv .venv && source .venv/bin/activate)
pip install -q -r backend/requirements.txt
echo "  Backend dependencies installed"

echo ""
echo "Starting backend..."
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app > ../backend.log 2>&1 &
BACKEND_PID=$!
echo "  Backend starting (PID: $BACKEND_PID)"
echo "  Logs: tail -f backend.log"

sleep 3

if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "  Backend is healthy"
    curl -s http://localhost:8000/ | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"  LLM: {data.get('llm_provider', 'Not configured')}\")"
else
    echo "  Backend failed to start - check backend.log"
    exit 1
fi

echo ""
echo "Starting frontend..."
cd "$REPO_ROOT/frontend"
npm run dev > "$REPO_ROOT/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "  Frontend starting (PID: $FRONTEND_PID)"
echo "  Logs: tail -f frontend.log"

sleep 3

echo ""
echo "All services started"
echo ""
echo "Access points:"
echo "  Frontend: http://localhost:8080"
echo "  Backend API: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "View logs:"
echo "  Backend:  tail -f backend.log"
echo "  Frontend: tail -f frontend.log"
