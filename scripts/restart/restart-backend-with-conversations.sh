#!/bin/bash

# Quick restart script for backend with conversation history updates

echo "🔄 Restarting Reflectra Backend..."
echo ""

cd "$(dirname "$0")/backend"

# Kill any existing backend processes
echo "🛑 Stopping existing backend processes..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run backend/run.sh first."
    exit 1
fi

source venv/bin/activate

# Start backend with auto-reload
echo ""
echo "🚀 Starting backend with conversation history system..."
echo "   📝 AI-generated conversation titles enabled"
echo "   💾 Message persistence enabled"
echo "   📋 Conversation history API ready"
echo ""
echo "   Access at: http://localhost:8000"
echo "   API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
