# Reflectra

> **Intelligent Self-Reflection Through AI-Powered Conversation**

Reflectra is an advanced self-reflection platform that combines dynamic personality modeling with AI-driven mirroring to help you understand yourself better. Through continuous conversation analysis, it learns your behavioral patterns, traits, and communication style—then reflects them back to you in meaningful, personalized interactions.

[![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=flat-square&logo=python)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-339933?style=flat-square&logo=node.js)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-009485?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-Latest-61dafb?style=flat-square&logo=react)](https://react.dev/)
[![MIT License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

## ✨ Key Features

- **Dynamic Persona System** — Learns and adapts to your unique behavioral patterns with weighted confidence tracking
- **AI Mirror Mode** — Reflective responses that authentically mirror your communication style and personality traits
- **Conversation Intelligence** — Deep analysis of past conversations to extract behavioral insights and patterns
- **Confidence-Based Learning** — Continuously refines understanding through statistically-sound trait modeling
- **Memory & Context** — Maintains rich conversation history with contextual awareness for meaningful follow-ups
- **User-Controlled Privacy** — Full control over your data with granular settings and digital twin controls

## 🏗️ Architecture

```
Reflectra
├── Backend (FastAPI)
│   ├── Persona Engine      - Trait extraction, snapshots, mirroring
│   ├── Conversation Store  - Rich history with context preservation  
│   ├── Analytics Service   - Behavioral insights and pattern detection
│   └── Database (SQLAlchemy) - Persistent persona & conversation storage
│
├── Frontend (React + TypeScript)
│   ├── Chat Interface      - Intuitive conversation UI
│   ├── Analytics Dashboard - Visualization of behavioral insights
│   └── Settings Panel      - Control over persona learning & privacy
│
└── AI Integration
    └── Mistral AI API      - Advanced language understanding & generation
```

## 🚀 Getting Started

### Prerequisites

- **Python** 3.12 or higher
- **Node.js** 18 or higher
- **Git** for version control

### Installation

#### 1. Clone the repository

```bash
git clone https://github.com/vaishnav1906/reflectra.git
cd reflectra
```

#### 2. Set up Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

#### 3. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

#### 4. Configure environment variables

Create `backend/.env` with your configuration:

```env
# AI Provider
MISTRAL_API_KEY=your_mistral_api_key_here

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/reflectra

# (Optional) Other configurations
DEBUG=false
```

### Running the Application

#### Quick Start (All-in-one)

```bash
./scripts/restart-all.sh
./scripts/check-status.sh
```

#### Manual Start

```bash
# Terminal 1: Backend
source .venv/bin/activate
cd backend
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

Visit `http://localhost:5173` to access the application.

## 📚 Documentation

Comprehensive documentation is available in the `/docs` directory:

- [**Persona System**](docs/persona-system.md) — Deep dive into dynamic personality modeling
- [**Mirror Mode**](docs/persona-quickstart.md) — How the AI learns and reflects your style
- [**Architecture**](docs/architecture-fix.md) — System design and component interactions
- [**API Reference**](docs/README.md) — Complete API documentation

## 🧪 Testing

Run the test suite to ensure everything is working correctly:

```bash
# Backend tests
pytest tests/backend/

# Frontend tests
cd frontend && npm run test
```

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## 💬 Questions & Support

Have questions or need help? Feel free to:
- Open an [issue](https://github.com/vaishnav1906/reflectra/issues)
- Check existing [documentation](docs/README.md)
- Review [past discussions](docs/past-conversations.md)

---

**Built with ❤️ for better self-understanding through AI**
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
