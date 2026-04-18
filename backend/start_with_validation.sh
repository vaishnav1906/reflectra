#!/bin/bash
# Quick validation and server startup script

set -e  # Exit on error

echo "======================================================================"
echo "🔍 REFLECTRA BACKEND - PRE-FLIGHT CHECKS"
echo "======================================================================"

cd /workspaces/reflectra/backend

# Check Python
echo ""
echo "1️⃣ Checking Python..."
python3 --version

# Check virtual environment
echo ""
echo "2️⃣ Checking virtual environment..."
if [ -d "/workspaces/reflectra/.venv" ]; then
    echo "✅ Virtual environment found at /workspaces/reflectra/.venv"
    source /workspaces/reflectra/.venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found"
    exit 1
fi

# Check .env file
echo ""
echo "3️⃣ Checking environment file..."
if [ -f ".env" ]; then
    echo "✅ .env file exists"
    # Show DATABASE_URL (partial)
    if grep -q "DATABASE_URL=" .env; then
        echo "✅ DATABASE_URL is set"
    else
        echo "❌ DATABASE_URL not found in .env"
        exit 1
    fi
    # Check MISTRAL_API_KEY
    if grep -q "MISTRAL_API_KEY=" .env; then
        echo "✅ MISTRAL_API_KEY is set"
    else
        echo "⚠️  MISTRAL_API_KEY not set (will use templates)"
    fi
else
    echo "❌ .env file not found"
    exit 1
fi

# Check dependencies
echo ""
echo "4️⃣ Checking Python packages..."
pip list | grep -E "(fastapi|uvicorn|sqlalchemy|mistralai)" || echo "⚠️  Some packages may be missing"

# Check ffmpeg binary
echo ""
echo "5️⃣ Checking ffmpeg binary..."
if command -v ffmpeg >/dev/null 2>&1; then
    echo "✅ ffmpeg: $(ffmpeg -version | head -n 1)"
else
    echo "❌ ffmpeg binary not found"
    echo "   Install it first: sudo apt-get update && sudo apt-get install -y ffmpeg"
    exit 1
fi

# Run validation script
echo ""
echo "6️⃣ Running comprehensive validation..."
echo "======================================================================"
python validate_startup.py
validation_result=$?

if [ $validation_result -ne 0 ]; then
    echo ""
    echo "❌ Validation failed. Please fix the issues above."
    exit 1
fi

# Start server
echo ""
echo "======================================================================"
echo "🚀 ALL CHECKS PASSED - STARTING SERVER"
echo "======================================================================"
echo ""
echo "Server will start at: http://localhost:8000"
echo "API docs will be at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
