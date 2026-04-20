# Reflectra

AI-powered self-reflection platform with a FastAPI backend and React frontend.

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+

### Setup

1) Python environment (single shared env at repo root)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

2) Frontend dependencies

```bash
cd frontend
npm install
cd ..
```

3) Backend environment file

Create `backend/.env` with required values:

```env
MISTRAL_API_KEY=your_key_here
DATABASE_URL=your_database_url_here
```

### Run

Use utility scripts:

```bash
./scripts/restart-all.sh
./scripts/check-status.sh
```

Or manually:

```bash
source .venv/bin/activate
cd backend
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In another terminal:

```bash
cd frontend
npm run dev
```

## Repository Layout

```text
.
├── backend/
├── frontend/
├── scripts/
├── tests/
├── docs/
├── data/
├── README.md
└── .gitignore
```

## Key Scripts

- `scripts/restart-all.sh` - restart backend and frontend
- `scripts/restart-backend-with-conversations.sh` - restart backend only
- `scripts/check-status.sh` - health and dependency checks
- `scripts/test-conversations.sh` - conversation endpoint checks

## Tests

Backend and integration-style tests are centralized under `tests/backend`.

Examples:

```bash
python tests/backend/test_conversations.py
python tests/backend/test_past_conversations.py
python tests/backend/test_mirror_confidence_updates.py
```

## Documentation

Canonical docs are in `docs/`.

- architecture-fix.md
- conversation-history.md
- past-conversations.md
- persona-quickstart.md
- persona-system.md
- error-handling-improvements.md
- backend-cors-fix.md

## License

MIT
