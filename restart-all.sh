#!/bin/bash
# Complete restart of both frontend and backend

echo "🔄 Restarting Reflectra services..."
echo ""

# Kill existing processes
echo "🛑 Stopping existing processes..."
pkill -f "uvicorn app.main" 2>/dev/null && echo "  ✓ Stopped backend" || echo "  - No backend running"
pkill -f "vite.*8080" 2>/dev/null && echo "  ✓ Stopped frontend" || echo "  - No frontend running"
sleep 2

echo ""
echo "📦 Installing backend dependencies..."
cd backend
source venv/bin/activate || (python3 -m venv venv && source venv/bin/activate)
pip install -q -r requirements.txt
echo "  ✓ Backend dependencies installed"

echo ""
echo "🚀 Starting backend..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > ../backend.log 2>&1 &
BACKEND_PID=$!
echo "  ✓ Backend starting (PID: $BACKEND_PID)"
echo "  📋 Logs: tail -f backend.log"

sleep 3

# Verify backend is running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "  ✅ Backend is healthy!"
    curl -s http://localhost:8000/ | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"  🤖 LLM: {data.get('llm_provider', 'Not configured')}\")"
else
    echo "  ❌ Backend failed to start - check backend.log"
    exit 1
fi

echo ""
echo "🎨 Starting frontend..."
cd ../frontend
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  ✓ Frontend starting (PID: $FRONTEND_PID)"
echo "  📋 Logs: tail -f frontend.log"

sleep 3

echo ""
echo "✅ All services started!"
echo ""
echo "📍 Access points:"
echo "   Frontend: http://localhost:8080"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "📋 View logs:"
echo "   Backend:  tail -f backend.log"
echo "   Frontend: tail -f frontend.log"
echo ""
echo "💡 To test: open http://localhost:8080 and send a message"
