# Deploying to Render (quick guide)

This repository can be deployed to Render with two services:

- Backend: a Docker web service built from `backend/Dockerfile` (recommended because `requirements.txt` includes large native deps like `torch`, `ffmpeg`).
- Frontend: a Static Site that runs `npm --prefix frontend run build` and publishes `frontend/dist`.

Files included

- `render.yaml` — template to create services automatically on Render (review and adjust fields before use).
- `backend/Dockerfile` — builds the backend container.

Quick steps (Render dashboard)

1. Backend (Docker service)
   - Create a new service -> Web Service.
   - Connect your GitHub repo and choose the `main` branch.
   - Environment: Docker.
   - Dockerfile path: `backend/Dockerfile` (context: repo root).
   - Set environment variables in the Render dashboard: `MISTRAL_API_KEY`, `DATABASE_URL`, etc.
   - Deploy.

2. Frontend (Static Site)
   - Create a new service -> Static Site.
   - Connect your GitHub repo and choose the `main` branch.
   - Build Command: `npm --prefix frontend run build`.
   - Publish Directory: `frontend/dist`.
   - Add any environment variables needed at build-time (e.g. `VITE_BACKEND_URL`).
   - Deploy.

Using `render.yaml`

- You can commit `render.yaml` (this file) and Render will detect it when you connect the repository, creating services automatically. Edit `render.yaml` to modify region, plan, or other settings before connecting.

Automatic redeploys via CI

To trigger Render automatic deploys after GitHub Actions finishes building/pushing images, create a Render "Deploy Hook" for your service and add the hook URL as the repository secret `RENDER_DEPLOY_HOOK`.

- In Render dashboard: Service -> Settings -> Deploy Hooks -> Create Deploy Hook. Copy the URL.
- In GitHub repo: Settings -> Secrets -> Actions -> New repository secret named `RENDER_DEPLOY_HOOK` with the hook URL.

The included CI workflow will call that hook after the frontend and backend build jobs complete, causing Render to start a new deploy.

Notes & troubleshooting

- The backend image is large due to native dependencies; using the Dockerfile is the recommended approach.
- For smaller deployments or when using managed LLM APIs, consider removing heavy packages from `requirements.txt` and using a lightweight Python web service instead.
- If you want automatic CI that builds and pushes an image to a registry, keep the existing GitHub Actions workflow and configure Render to pull from GHCR or to deploy directly from GitHub when builds finish.

Local test commands (same as other instructions):

```bash
# Build frontend locally
cd frontend
npm install
npm run build

# Build backend Docker image
cd ../backend
docker build -t reflectra-backend:local .
docker run --rm -e MISTRAL_API_KEY="$MISTRAL_API_KEY" -e DATABASE_URL="$DATABASE_URL" -p 8000:8000 reflectra-backend:local

# Check backend health
curl http://localhost:8000/
```
