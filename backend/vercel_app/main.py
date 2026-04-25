from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx

app = FastAPI(title="Reflectra Vercel Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health():
    return {"status": "ok", "service": "reflectra-vercel-backend"}


@app.post("/mistral")
async def call_mistral(request: Request):
    """
    Thin proxy to Mistral (or another managed LLM). Expects JSON body which will be
    forwarded to the external API configured by `MISTRAL_API_URL` and `MISTRAL_API_KEY`.
    This keeps heavy model work off Vercel and uses managed inference endpoints.
    """
    mistral_url = os.getenv("MISTRAL_API_URL")
    mistral_key = os.getenv("MISTRAL_API_KEY")
    if not mistral_url or not mistral_key:
        return {"error": "MISTRAL_API_URL or MISTRAL_API_KEY not configured"}

    body = await request.json()
    headers = {"Authorization": f"Bearer {mistral_key}",
               "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(mistral_url, json=body, headers=headers)
            return resp.json()
        except httpx.HTTPError as e:
            return {"error": "upstream request failed", "detail": str(e)}


@app.post("/auth/login")
async def auth_login(payload: dict):
    """
    Minimal login stub for Vercel deployment.
    Accepts JSON payload (e.g. {"email":"...","display_name":"..."})
    and returns a simple token and user object. Replace with real auth logic.
    """
    email = payload.get("email") if isinstance(payload, dict) else None
    display_name = payload.get("display_name") if isinstance(
        payload, dict) else None
    if not email:
        return {"error": "email required"}

    # In a real app: validate credentials, create session, issue JWT, etc.
    fake_token = "dev-token-12345"
    user = {"email": email,
            "display_name": display_name or email.split("@")[0]}
    return {"token": fake_token, "user": user}
