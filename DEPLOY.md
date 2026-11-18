# Deploying Reflectra for free (Vercel + Supabase + Gemini)

Everything runs on free tiers, with no payment method anywhere. People install the app
from their browser (Android: Chrome; iPhone/iPad: Safari), so there are no app-store fees.

| Piece | Where | Free-tier notes |
|---|---|---|
| App + API | **Vercel** Hobby, one project with two [Services](https://vercel.com/docs/services) (in beta): the Vite frontend and the FastAPI backend | Your address is `https://<name>.vercel.app` (a custom domain costs money). |
| Database + sign-in | **Supabase** Free | A project pauses after about a week with no database activity; the background tick below keeps it active. Keep your own backups. |
| AI | **Gemini** with an AI Studio key | Low rate limits. On the free tier Google may use prompts and replies to improve its products, so tell your users. |
| Background work | **Vercel Cron**, once a day (plus an optional faster scheduler) | Hobby allows daily jobs, run some time within the chosen hour. |
| Notifications | Web Push (VAPID) | Android: works in Chrome. iPhone/iPad: iOS 16.4+, only after *Add to Home Screen*, opened from the icon. |

## How it runs on Vercel

```text
https://<name>.vercel.app/api/*  ->  backend service (backend/, FastAPI, /api stripped)
https://<name>.vercel.app/*      ->  frontend service (frontend/, static Vite build)
```

The backend runs in Vercel's Singapore region (`"regions": ["sin1"]` in `vercel.json`), next to
the Supabase database (ap-southeast-1). Every database query is a round trip, so keep these two in the
same part of the world; if your database lives elsewhere, change the region to match.

Serverless functions can't keep a worker running between requests, so the learning that
normally happens in the background runs two ways instead:

- **Right after each reply** the app calls `POST /api/jobs/run-mine`, which runs that
  person's queued jobs (traits, memory, People, life facts) within seconds.
- **Once a day** Vercel's cron (`crons` in `vercel.json`, 13:00 UTC, which is about 7 pm in
  India) calls `/api/internal/tick`, sending `CRON_SECRET` itself. It runs everyone's leftover
  jobs, sends reminders and cleans up, and keeps Supabase from pausing.
- **Optionally, more often:** `.github/workflows/tick.yml` (every 10 minutes, free for public
  repositories) or any free scheduler such as [cron-job.org](https://cron-job.org) can POST to
  the same endpoint with `Authorization: Bearer <CRON_SECRET>`. That makes a daily check-in at
  a time you pick work; with only the daily cron, reminders arrive around the cron's hour.

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
| `DATABASE_URL` | Supabase connection string (the Session pooler one is fine: on Vercel the backend switches it to the Transaction pooler, port 6543, by itself, because session mode allows only 15 connections and serverless instances would run out) |
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

#### Optional: Continue with Google

The sign-in box always shows a **Continue with Google** button. It works once Google is switched on, which is free and needs no billing:

1. Google Cloud Console → APIs & Services → Credentials → create an **OAuth client ID** of type *Web application*. Under *Authorized redirect URIs* add the callback URL that Supabase shows you.
2. Supabase → Authentication → Providers → **Google**: paste the client ID and secret, and enable it.
3. Make sure `https://<name>.vercel.app/**` is in the Supabase redirect URLs (above).

Until Google is enabled, the button shows Supabase's "provider is not enabled" message. Email and password keep working either way.

### 5. Deploy

Push to `main` (or run `vercel --prod`). Then check:

- `https://<name>.vercel.app/api/health` returns `{"status": ...}`
- Signing in works, and a chat reply streams in
- Vercel → your project → Settings → **Cron Jobs** lists `/api/internal/tick`

### 6. Install it on your phone

- **Android:** open the site in Chrome. Use **Install** in Settings → *Get the app*, or the menu → *Install app*.
- **iPhone/iPad:** open it in **Safari** → Share → **Add to Home Screen**, then open it from the icon. Turn on
  notifications from Settings → *About you* (iOS only allows that inside the installed app).

## Keeping it free and healthy

- The daily cron keeps Supabase from pausing. If you also use the GitHub workflow: GitHub
  pauses scheduled workflows after 60 days without commits, and doesn't run any while an
  account has a billing lock.
- Gemini free-tier limits are low. When they're hit, Reflectra says it's catching its
  breath and you can resend, and background jobs retry by themselves.
- Database migrations aren't run on deploy. After pulling new ones, run
  `cd backend && alembic upgrade head` once from your computer (same `DATABASE_URL`).
