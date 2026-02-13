# Reflectra - AI-Powered Self-Reflection Platform

A full-stack application with React frontend and FastAPI backend, powered by Mistral AI.

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- Mistral API key ([Get one here](https://console.mistral.ai/api-keys/))

### Setup & Run

**1. Backend Setup:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Add your Mistral API key and database URL
cat <<'EOF' > .env
MISTRAL_API_KEY=your_key_here
DATABASE_URL=postgresql+asyncpg://postgres.rnddxkfgddwcwuedwaog:your_db_password@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
EOF
```

**2. Frontend Setup:**
```bash
cd frontend
npm install
```

**3. Start Services:**

Terminal 1 - Backend:
```bash
cd backend
source venv/bin/activate
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

**4. Access:**
- Frontend: http://localhost:8080
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 📁 Project Structure

```
reflectra-frontend/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── main.py      # FastAPI app entry
│   │   └── api/
│   │       └── chat.py  # Chat endpoints with Mistral AI
│   ├── .env             # API keys (gitignored)
│   └── requirements.txt # Python dependencies
├── frontend/            # React + TypeScript frontend
│   ├── src/
│   │   ├── pages/      # Page components
│   │   ├── components/ # UI components
│   │   └── lib/        # Utils
│   └── package.json    # Node dependencies
└── README.md
```

## 🤖 Features

- **Reflection Mode**: Asks thought-provoking questions
- **Mirror Mode**: Provides empathetic validation
- **AI-Powered**: Uses Mistral AI for responses
- **Modern UI**: shadcn/ui + Tailwind CSS

## 🔧 Backend (.env)

```env
MISTRAL_API_KEY=your_key_here
DATABASE_URL=postgresql+asyncpg://postgres.rnddxkfgddwcwuedwaog:your_db_password@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
```

## 🐛 Troubleshooting

**401 Unauthorized?**
- Check API key at https://console.mistral.ai/
- Ensure no spaces in `.env` file
- Restart backend after changing `.env`

**Backend not starting?**
- Activate venv: `source backend/venv/bin/activate`
- Install deps: `pip install -r requirements.txt`

**Frontend can't connect?**
- Ensure backend is running on port 8000
- Check browser console for errors

## 📚 Tech Stack

**Backend:** FastAPI, Mistral AI, Uvicorn, Pydantic  
**Frontend:** React, TypeScript, Vite, shadcn/ui, Tailwind CSS

## 📄 License

MIT
4. **Hot reload** enabled for both frontend and backend

## 🐛 Troubleshooting

**CORS errors?**
- Make sure backend is running on port 8000
- Check `backend/app/main.py` CORS configuration
- Verify `frontend/.env.local` has correct URL

**Proxy not working?**
- Restart frontend dev server after backend starts
- Check console logs for proxy messages
- Verify `frontend/vite.config.ts` proxy configuration

**Backend not starting?**
- Activate virtual environment: `source backend/venv/bin/activate`
- Install dependencies: `pip install -r backend/requirements.txt`
- Check if port 8000 is already in use
