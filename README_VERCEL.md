# Deploying to Vercel (quick guide)

This repository is prepared for a two-service Vercel deployment:

- **frontend**: Vite React app in `frontend/` (build -> `frontend/dist`)
- **backend**: Containerized FastAPI service from `backend/Dockerfile`

Files added to help Vercel:

- `vercel.json` — maps the two services (`frontend` and `backend`).
- `backend/Dockerfile` — builds a container image for the backend (recommended because `requirements.txt` contains native deps like `torch`, `ffmpeg`).
- `.vercelignore` — reduces upload size and excludes secrets.

Steps (Vercel UI):

1. Import the repository into Vercel (GitHub import).
2. During setup, Vercel should detect `vercel.json` and create two services:
   - `frontend` (framework: `vite`) with build command `npm --prefix frontend run build` and output `frontend/dist` mapped to `/`.
   - `backend` (framework: `docker`) using `backend/Dockerfile` and routePrefix `/api`.
3. In the Vercel project settings, add required Environment Variables (set under Production and Preview):
   - `MISTRAL_API_KEY` (or your LLM provider key)
   - `DATABASE_URL` (Postgres connection URL)
   - Any other secrets used by your `.env` files (DON'T commit `.env` to the repo).
4. Deploy. Vercel will run the frontend build and build the backend Docker image.

Notes & troubleshooting
- If Vercel build of the backend fails due to missing system libs required by `weasyprint`/`torch`, consider using a different base image in `backend/Dockerfile` (e.g., `python:3.11-bullseye`) or building the backend in a separate cloud service (Cloud Run, ECS) and pointing the frontend to that URL.
- For local testing, build the frontend and backend container locally (see `backend/README.md`).

Quick local commands

```bash
# Build frontend
cd frontend
npm install
npm run build

# Build backend container (requires Docker)
cd ../backend
docker build -t reflectra-backend:local .
docker run --rm -e MISTRAL_API_KEY="$MISTRAL_API_KEY" -e DATABASE_URL="$DATABASE_URL" -p 8000:8000 reflectra-backend:local

# Check backend health
curl http://localhost:8000/
```

If you prefer I can also add a short GitHub Actions workflow to automatically run `npm ci` + `npm run build` for the frontend and push backend images to a registry — tell me if you'd like that.

CI / GitHub Actions

This repo contains a GitHub Actions workflow at `.github/workflows/ci.yml` that:

- Builds the frontend (`npm ci` + `npm run build`) on pushes to `main` and uploads `frontend/dist` as an artifact.
- Optionally builds and pushes the backend Docker image to GitHub Container Registry (GHCR) if you set the secret `GHCR_TOKEN` in the repository settings.

To enable backend image publishing:

1. Create a Personal Access Token with `write:packages` and `read:packages` (or use a fine-grained token for packages) and save it as repo secret `GHCR_TOKEN`.
2. On push, Actions will build `backend/Dockerfile` and push `ghcr.io/<org-or-user>/reflectra-backend:sha` and `:latest`.

You can then point Vercel's backend service to pull that image from GHCR (or use Vercel's Docker build directly). If you want, I can add a short workflow step to also notify Vercel via the Vercel API to trigger a redeploy after the image is pushed.
