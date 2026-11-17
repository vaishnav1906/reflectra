# Deploying Reflectra for free (Vercel + Supabase + Gemini)

Everything runs on free tiers, with no payment method anywhere. People install the app
from their browser (Android: Chrome; iPhone/iPad: Safari), so there are no app-store fees.

| Piece | Where | Free-tier notes |
|---|---|---|
| App + API | **Vercel** Hobby, one project with two [Services](https://vercel.com/docs/services) (in beta): the Vite frontend and the FastAPI backend | Your address is `https://<name>.vercel.app` (a custom domain costs money). |
| Database + sign-in | **Supabase** Free | A project pauses after about a week with no database activity; the background tick below keeps it active. Keep your own backups. |
| AI | **Gemini** with an AI Studio key | Low rate limits. On the free tier Google may use prompts and replies to improve its products, so tell your users. |
| Background work | **GitHub Actions**, every 10 minutes | Free for public repositories. |
| Notifications | Web Push (VAPID) | Android: works in Chrome. iPhone/iPad: iOS 16.4+, only after *Add to Home Screen*, opened from the icon. |

## How it runs on Vercel

```text
https://<name>.vercel.app/api/*  ->  backend service (backend/, FastAPI, /api stripped)
https://<name>.vercel.app/*      ->  frontend service (frontend/, static Vite build)
```

Serverless functions can't keep a worker running between requests, so the learning that
normally happens in the background runs two ways instead:

- **Right after each reply** the app calls `POST /api/jobs/run-mine`, which runs that
  person's queued jobs (traits, memory, People, life facts) within seconds.
- **Every 10 minutes** `.github/workflows/tick.yml` calls `POST /api/internal/tick` with a
  secret. It runs everyone's leftover jobs, sends reminders and cleans up.

Voice typing (`/transcribe`, Whisper) is left out because it is several GB. On Vercel it
answers "not available" and everything else works. To keep it, run the backend from
`backend/Dockerfile` on a container host instead.

## Steps

### 1. Merge to `main`

Vercel deploys production from your default branch, and GitHub only runs scheduled
workflows from the default branch. Merge `feat/immersive-ui` into `main` first.

### 2. Create the Vercel project

1. Update the CLI: `npm i -g vercel@latest`, then `vercel login`.
2. On [vercel.com/new](https://vercel.com/new), import the `reflectra` GitHub repository.
   Keep the **root directory** as the repository root. If Vercel asks for a framework,
   choose **Services**: it reads both services from `vercel.json`.
3. In this folder, run `vercel link` and pick that project.

The first deploy may fail because the settings below aren't there yet. That's expected.

### 3. Copy your settings to Vercel and GitHub

```bash
node scripts/deploy/setup-env.mjs --app-url https://<name>.vercel.app
```

This reads `backend/.env`, `frontend/.env` and `backend/.vapid.json`, asks for anything
missing (for example `GEMINI_API_KEY`), and sets them on Vercel for Production. It also
creates `CRON_SECRET` and saves it, with `APP_URL`, as GitHub secrets (using the `gh` CLI).
No value is ever printed. If you'd rather click, set the same names by hand:

| Name | Value |
|---|---|
| `DATABASE_URL` | Supabase connection string (Session pooler) |
| `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `SUPABASE_SERVICE_ROLE_KEY` | from Supabase → Project settings → API |
| `GEMINI_API_KEY` | from [Google AI Studio](https://aistudio.google.com/apikey) |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` | from `backend/.vapid.json` (keep them; new keys break existing subscriptions) |
| `CRON_SECRET` | any long random string, the same as the GitHub secret |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | from `frontend/.env` |

GitHub (repository → Settings → Secrets and variables → Actions): `APP_URL` and `CRON_SECRET`.

### 4. Point Supabase sign-in at the new address

Supabase → Authentication → URL Configuration:

- **Site URL**: `https://<name>.vercel.app`
- **Redirect URLs**: add `https://<name>.vercel.app/**`

Without this, confirmation and password-reset emails link back to localhost.

### 5. Deploy

Push to `main` (or run `vercel --prod`). Then check:

- `https://<name>.vercel.app/api/health` returns `{"status": ...}`
- Signing in works, and a chat reply streams in
- GitHub → Actions → **Background tick** → *Run workflow*: it should finish green

### 6. Install it on your phone

- **Android:** open the site in Chrome. Use **Install** in Settings → *Get the app*, or the menu → *Install app*.
- **iPhone/iPad:** open it in **Safari** → Share → **Add to Home Screen**, then open it from the icon. Turn on
  notifications from Settings → *About you* (iOS only allows that inside the installed app).

## Keeping it free and healthy

- The 10-minute tick keeps Supabase from pausing. If the repository has no commits for
  60 days, GitHub pauses scheduled workflows: re-enable it from the Actions tab.
- Gemini free-tier limits are low. When they're hit, Reflectra says it's catching its
  breath and you can resend, and background jobs retry by themselves.
- Database migrations aren't run on deploy. After pulling new ones, run
  `cd backend && alembic upgrade head` once from your computer (same `DATABASE_URL`).
