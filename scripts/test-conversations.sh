#!/bin/bash
# Test the conversations endpoint directly

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Testing Conversation Fetching"
echo "============================"
echo ""

echo "1) Checking if backend is running..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "Backend is running"
else
    echo "Backend is not running"
    echo "Start it with: cd $REPO_ROOT/backend && source $REPO_ROOT/.venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    exit 1
fi

echo ""
echo "2) Running database check script..."
cd "$REPO_ROOT"
python tests/backend/test_conversations.py

echo ""
echo "3) Testing API endpoint directly..."
echo ""
echo "If you see users and conversations above, copy a user_id and test:"
echo ""
echo '  curl "http://localhost:8000/conversations?user_id=YOUR_USER_ID_HERE"'
echo ""
echo "Or test with reflection mode filter:"
echo '  curl "http://localhost:8000/conversations?user_id=YOUR_USER_ID_HERE&mode=reflection"'
echo ""
