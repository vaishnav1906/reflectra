#!/bin/bash
# Debug script to test backend startup

cd "$(dirname "$0")"

echo "🔍 Checking backend setup..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found"
    exit 1
fi
echo "✅ Python3: $(python3 --version)"

# Check if in backend directory
if [ ! -f "app/main.py" ]; then
    echo "❌ Not in backend directory or app/main.py not found"
    exit 1
fi
echo "✅ Found app/main.py"

# Check/create venv
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate
echo "✅ Virtual environment activated"

# Install dependencies
echo "📦 Installing dependencies..."
pip install --quiet fastapi uvicorn pydantic

echo ""
echo "🚀 Starting backend..."
echo "   Access at: http://localhost:8000"
echo "   Docs at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start server with better error output
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
