#!/bin/bash
# Quick restart script for backend with conversation history updates

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT/backend"

echo "Restarting Reflectra Backend..."
echo ""

echo "Stopping existing backend processes..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1

if [ ! -d "$REPO_ROOT/.venv" ]; then
    echo "Virtual environment not found. Run: python3 -m venv .venv"
    exit 1
fi

source "$REPO_ROOT/.venv/bin/activate"

echo ""
echo "Starting backend with conversation history system..."
echo "  AI-generated conversation titles enabled"
echo "  Message persistence enabled"
echo "  Conversation history API ready"
echo ""
echo "  Access at: http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
