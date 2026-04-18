#!/bin/bash
# Debug script to test backend startup

set -e

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

# Check ffmpeg binary (required by Whisper/ffmpeg-python)
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ ffmpeg binary not found on system PATH"
    echo "   Install it first: sudo apt-get update && sudo apt-get install -y ffmpeg"
    exit 1
fi
echo "✅ ffmpeg: $(ffmpeg -version | head -n 1)"

# Install dependencies
echo "📦 Installing dependencies..."
python3 -m pip install --quiet -r requirements.txt

echo ""
echo "🚀 Starting backend..."
echo "   Access at: http://localhost:8000"
echo "   Docs at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start server with better error output
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
