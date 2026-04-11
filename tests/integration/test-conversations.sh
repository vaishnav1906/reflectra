#!/bin/bash
# Test the conversations endpoint directly

# Get the first user from database to test with
echo "🧪 Testing Conversation Fetching"
echo "================================"
echo ""

# Check if backend is running
echo "1️⃣ Checking if backend is running..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is running"
else
    echo "❌ Backend is not running!"
    echo "   Start it with: cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    exit 1
fi

echo ""
echo "2️⃣ Running database check script..."
# Run the test script from the tests folder
python ../backend/test_conversations.py

echo ""
echo "3️⃣ Testing API endpoint directly..."
echo ""
echo "If you see users and conversations above, copy a user_id and test:"
echo ""
echo "Example:"
echo '  curl "http://localhost:8000/conversations?user_id=YOUR_USER_ID_HERE"'
echo ""
echo "Or test with reflection mode filter:"
echo '  curl "http://localhost:8000/conversations?user_id=YOUR_USER_ID_HERE&mode=reflection"'
echo ""
