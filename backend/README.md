# Backend: Docker & local run notes

Quick notes to run the backend locally or build a container for deployment.

Local (venv recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Build and run Docker (recommended if native deps like `torch` are required):

```bash
docker build -t reflectra-backend:latest .
docker run -e MISTRAL_API_KEY="$MISTRAL_API_KEY" -e DATABASE_URL="$DATABASE_URL" -p 8000:8000 reflectra-backend:latest
```

Notes:

- The `requirements.txt` contains heavy native deps (`torch`, `ffmpeg`, `weasyprint`). The slim Python image may require additional system packages depending on platform and wheel availability. If builds fail, prefer a more complete base image (e.g. `python:3.11-bullseye`) or use a prebuilt image that includes `libglib2.0` and other libs required by `weasyprint`/`weasyprint` dependencies.
- For Vercel multi-service deployment, you can deploy the backend as a Docker container using Vercel's container support or deploy it separately (e.g., on a small VM or cloud run) and point your frontend to that URL.
