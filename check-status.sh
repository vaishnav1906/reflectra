#!/bin/bash
# Check current status of Reflectra services

echo "🔍 Reflectra Status Check"
echo "========================="
echo ""

# Check backend process
echo "1️⃣ Backend Process:"
if pgrep -f "uvicorn app.main" > /dev/null; then
    PID=$(pgrep -f "uvicorn app.main")
    echo "  ✅ Running (PID: $PID)"
    
    # Check if responding
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "  ✅ Responding on port 8000"
        
        # Check API config
        API_INFO=$(curl -s http://localhost:8000/)
        LLM_PROVIDER=$(echo "$API_INFO" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('llm_provider', 'None'))" 2>/dev/null)
        LLM_AVAILABLE=$(echo "$API_INFO" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('llm_available', False))" 2>/dev/null)
        
        if [ "$LLM_AVAILABLE" = "True" ]; then
            echo "  ✅ LLM configured: $LLM_PROVIDER"
        else
            echo "  ⚠️  No LLM configured (using templates)"
        fi
    else
        echo "  ❌ Not responding on port 8000"
    fi
else
    echo "  ❌ Not running"
fi

echo ""

# Check frontend process
echo "2️⃣ Frontend Process:"
if pgrep -f "vite.*8080" > /dev/null; then
    PID=$(pgrep -f "vite.*8080" | head -1)
    echo "  ✅ Running (PID: $PID)"
    echo "  🌐 Available at: http://localhost:8080"
else
    echo "  ❌ Not running"
fi

echo ""

# Check API key
echo "3️⃣ API Configuration:"
if [ -f "backend/.env" ]; then
    if grep -q "MISTRAL_API_KEY=" backend/.env; then
        KEY_SET=$(grep "MISTRAL_API_KEY=" backend/.env | cut -d'=' -f2)
        if [ -n "$KEY_SET" ] && [ "$KEY_SET" != "your_mistral_api_key_here" ]; then
            echo "  ✅ Mistral API key configured"
        else
            echo "  ⚠️  Mistral API key not set"
        fi
    else
        echo "  ⚠️  No Mistral API key in .env"
    fi
else
    echo "  ❌ No .env file found"
fi

echo ""

# Check dependencies
echo "4️⃣ Dependencies:"
if [ -d "backend/venv" ]; then
    echo "  ✅ Backend venv exists"
    
    # Check if mistralai is installed
    source backend/venv/bin/activate 2>/dev/null
    if python3 -c "import mistralai" 2>/dev/null; then
        echo "  ✅ mistralai package installed"
    else
        echo "  ⚠️  mistralai package NOT installed"
        echo "     Run: cd backend && source venv/bin/activate && pip install -r requirements.txt"
    fi
    deactivate 2>/dev/null
else
    echo "  ⚠️  Backend venv not found"
fi

if [ -d "frontend/node_modules" ]; then
    echo "  ✅ Frontend node_modules exists"
else
    echo "  ⚠️  Frontend node_modules not found"
    echo "     Run: cd frontend && npm install"
fi

echo ""
echo "========================="

# Provide recommendations
echo ""
echo "📋 Recommendations:"
NEEDS_ACTION=false

if ! pgrep -f "uvicorn app.main" > /dev/null; then
    echo "  • Start backend: cd backend && ./run.sh"
    NEEDS_ACTION=true
fi

if ! pgrep -f "vite.*8080" > /dev/null; then
    echo "  • Start frontend: cd frontend && npm run dev"
    NEEDS_ACTION=true
fi

if ! python3 -c "import sys; sys.path.insert(0, 'backend/venv/lib/python3.12/site-packages'); import mistralai" 2>/dev/null; then
    echo "  • Install dependencies: cd backend && source venv/bin/activate && pip install -r requirements.txt"
    NEEDS_ACTION=true
fi

if [ "$NEEDS_ACTION" = false ]; then
    echo "  ✅ Everything looks good!"
    echo ""
    echo "🧪 Test it: ./test-mistral.sh"
    echo "🌐 Open: http://localhost:8080"
fi
