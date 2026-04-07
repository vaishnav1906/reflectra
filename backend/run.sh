#!/bin/bash
# Start the FastAPI backend server

set -e

cd "$(dirname "$0")"

# Check if venv exists, if not create it
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Check ffmpeg binary (required by Whisper/ffmpeg-python)
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ ffmpeg binary not found on system PATH"
    echo "   Install it first: sudo apt-get update && sudo apt-get install -y ffmpeg"
    exit 1
fi

echo "📦 Installing/updating dependencies..."
python3 -m pip install -r requirements.txt

# Run the server
echo "🚀 Starting Reflectra backend on http://localhost:8000"
echo "📝 API docs available at http://localhost:8000/docs"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
