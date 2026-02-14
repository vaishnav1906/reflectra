from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat import router as chat_router
from app.api.dbms import router as db_router
from app.api.auth import router as auth_router
from dotenv import load_dotenv
from pathlib import Path
import os

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="Reflectra Backend", version="1.0.0")

# Enable CORS (required for frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:5173",
        "https://potential-space-parakeet-pjgqvwgxvvqg296q-8080.app.github.dev",
        "*",  # fallback for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(chat_router)
app.include_router(db_router)
app.include_router(auth_router)

@app.get("/")
def health():
    """Root endpoint with API information"""
    mistral_configured = bool(os.getenv("MISTRAL_API_KEY"))
    
    return {
        "status": "✅ Reflectra backend running",
        "version": "1.0.0",
        "llm_available": mistral_configured,
        "llm_provider": "Mistral AI" if mistral_configured else None,
        "endpoints": {
            "health": "/",
            "health_check": "/health",
            "docs": "/docs",
            "chat": "/chat"
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "reflectra-backend",
        "llm_configured": bool(os.getenv("MISTRAL_API_KEY"))
    }
