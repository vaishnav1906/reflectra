// Copies Reflectra's settings into your Vercel project (and the two GitHub secrets the
// background tick needs), straight from your local .env files. Values are piped to the
// official CLIs and never printed.
//
//   vercel login && vercel link          (once, in the repo root)
//   node scripts/deploy/setup-env.mjs --app-url https://your-app.vercel.app
//
// Anything it can't find locally (e.g. GEMINI_API_KEY) it asks you to paste.

import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { createInterface } from "node:readline/promises";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const args = process.argv.slice(2);
const appUrl = (args[args.indexOf("--app-url") + 1] || "").replace(/\/$/, "");
const ENVIRONMENTS = ["production"];
const shell = process.platform === "win32";

function readEnv(file) {
  const out = {};
  if (!existsSync(file)) return out;
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
    if (m) out[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
  return out;
}

const backend = readEnv(join(ROOT, "backend", ".env"));
const frontend = readEnv(join(ROOT, "frontend", ".env"));
const vapidFile = join(ROOT, "backend", ".vapid.json");
const vapid = existsSync(vapidFile) ? JSON.parse(readFileSync(vapidFile, "utf8")) : {};

// name -> where it comes from, and whether the app needs it
const VARS = [
  ["DATABASE_URL", backend.DATABASE_URL, true],
  ["SUPABASE_URL", backend.SUPABASE_URL, true],
  ["SUPABASE_JWT_SECRET", backend.SUPABASE_JWT_SECRET, true],
  ["SUPABASE_SERVICE_ROLE_KEY", backend.SUPABASE_SERVICE_ROLE_KEY, true],
  ["AUTH_REQUIRE_VERIFIED_EMAIL", backend.AUTH_REQUIRE_VERIFIED_EMAIL, false],
  ["GEMINI_API_KEY", backend.GEMINI_API_KEY || process.env.GEMINI_API_KEY, true],
  ["MISTRAL_API_KEY", backend.MISTRAL_API_KEY, false],
  ["VAPID_PUBLIC_KEY", backend.VAPID_PUBLIC_KEY || vapid.public, true],
  ["VAPID_PRIVATE_KEY", backend.VAPID_PRIVATE_KEY || vapid.private, true],
  ["CRON_SECRET", backend.CRON_SECRET || randomBytes(32).toString("base64url"), true],
  ["ALLOWED_ORIGINS", appUrl || backend.ALLOWED_ORIGINS, false],
  // Read by the frontend build
  ["VITE_SUPABASE_URL", frontend.VITE_SUPABASE_URL, true],
  ["VITE_SUPABASE_ANON_KEY", frontend.VITE_SUPABASE_ANON_KEY, true],
];

function run(cmd, cmdArgs, input) {
  return spawnSync(cmd, cmdArgs, { cwd: ROOT, input, encoding: "utf8", shell, stdio: [input === undefined ? "inherit" : "pipe", "pipe", "pipe"] });
}

if (!existsSync(join(ROOT, ".vercel", "project.json"))) {
  console.error("This folder isn't linked to a Vercel project yet. Run `vercel login` and `vercel link` here first.");
  process.exit(1);
}

const ask = createInterface({ input: process.stdin, output: process.stdout });
const missing = [];
for (const entry of VARS) {
  if (!entry[1] && entry[2]) {
    const value = (await ask.question(`${entry[0]} isn't in your local .env files. Paste it (or press Enter to skip): `)).trim();
    entry[1] = value;
    if (!value) missing.push(entry[0]);
  }
}
ask.close();

for (const [name, value] of VARS) {
  if (!value) continue;
  for (const environment of ENVIRONMENTS) {
    run("vercel", ["env", "rm", name, environment, "--yes"], "");
    const res = run("vercel", ["env", "add", name, environment], `${value}\n`);
    console.log(res.status === 0 ? `set ${name} (${environment})` : `could not set ${name}: ${(res.stderr || "").trim().split("\n").pop()}`);
  }
}

// GitHub secrets for the scheduled background tick.
const cron = VARS.find(([name]) => name === "CRON_SECRET")[1];
if (appUrl && run("gh", ["--version"], "").status === 0) {
  for (const [name, value] of [["APP_URL", appUrl], ["CRON_SECRET", cron]]) {
    const res = run("gh", ["secret", "set", name, "--body", "-"], value);
    console.log(res.status === 0 ? `set GitHub secret ${name}` : `could not set GitHub secret ${name}: ${(res.stderr || "").trim()}`);
  }
} else {
  console.log("Skipped GitHub secrets: pass --app-url and have the GitHub CLI (gh) signed in, or add APP_URL and CRON_SECRET by hand.");
}

if (missing.length) console.log(`\nStill needed before the app fully works: ${missing.join(", ")}`);
console.log("\nDone. Redeploy (push to main, or `vercel --prod`) so the new settings are used.");
