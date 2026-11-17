// Opens the app (the Vite dev server) in a scripted browser, signed in as the demo
// person, with every API call answered by demo-data.mjs. Nothing reaches the backend.

import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { launch } from "./cdp.mjs";
import { USER, respond } from "./demo-data.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
export const BASE = process.env.APP_URL || "http://localhost:8080";

/** The Supabase project URL from frontend/.env (only its host is used, for the session key). */
function supabaseUrl() {
  const envFile = join(ROOT, "frontend", ".env");
  const text = existsSync(envFile) ? readFileSync(envFile, "utf8") : "";
  const match = text.match(/^VITE_SUPABASE_URL\s*=\s*["']?([^"'\r\n]+)/m);
  return match ? match[1].trim() : "http://localhost:54321";
}

function fakeJwt() {
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
  const exp = Math.floor(Date.now() / 1000) + 86_400;
  return `${b64({ alg: "HS256", typ: "JWT" })}.${b64({ sub: USER.id, email: USER.email, role: "authenticated", aud: "authenticated", exp })}.demo-signature`;
}

// A pointer drawn in the page, so the video shows where the "user" clicks.
const CURSOR = `
(() => {
  const install = () => {
    if (document.getElementById("demo-cursor")) return;
    const style = document.createElement("style");
    style.textContent = \`
      #demo-cursor { position: fixed; left: 0; top: 0; z-index: 2147483647; pointer-events: none; width: 22px; height: 22px;
        transform: translate(-100px, -100px); transition: opacity .2s; filter: drop-shadow(0 2px 6px rgba(0,0,0,.6)); }
      #demo-cursor svg { width: 22px; height: 22px; }
      .demo-click { position: fixed; z-index: 2147483646; pointer-events: none; width: 36px; height: 36px; margin: -18px 0 0 -18px;
        border-radius: 50%; border: 2px solid rgba(255,255,255,.85); animation: demo-click .55s ease-out forwards; }
      @keyframes demo-click { from { transform: scale(.3); opacity: 1; } to { transform: scale(1.4); opacity: 0; } }\`;
    document.head.appendChild(style);
    const cursor = document.createElement("div");
    cursor.id = "demo-cursor";
    cursor.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 2l15 10.5-6.6 1.3L16 21l-3 1.4-3.6-7.2L4 19.5z" fill="white" stroke="black" stroke-width="1.2" stroke-linejoin="round"/></svg>';
    document.body.appendChild(cursor);
    addEventListener("mousemove", (e) => (cursor.style.transform = \`translate(\${e.clientX - 3}px, \${e.clientY - 2}px)\`), true);
    addEventListener("mousedown", (e) => {
      const ring = document.createElement("span");
      ring.className = "demo-click";
      ring.style.left = e.clientX + "px";
      ring.style.top = e.clientY + "px";
      document.body.appendChild(ring);
      setTimeout(() => ring.remove(), 600);
    }, true);
  };
  if (document.body) install();
  else addEventListener("DOMContentLoaded", install);
})();`;

export async function openStage({ cursor = false, ...viewport } = {}) {
  const page = await launch(viewport);
  const supabase = new URL(supabaseUrl());
  const storageKey = `sb-${supabase.hostname.split(".")[0]}-auth-token`;
  const session = {
    access_token: fakeJwt(),
    token_type: "bearer",
    expires_in: 86_400,
    expires_at: Math.floor(Date.now() / 1000) + 86_400,
    refresh_token: "demo-refresh",
    user: { id: USER.id, email: USER.email, aud: "authenticated", role: "authenticated", user_metadata: { display_name: USER.display_name } },
  };

  await page.intercept(["*/api/*", `*${supabase.hostname}*`], respond);
  await page.addInitScript(`
    try {
      if (location.origin === ${JSON.stringify(new URL(BASE).origin)}) {
        localStorage.setItem(${JSON.stringify(storageKey)}, ${JSON.stringify(JSON.stringify(session))});
        localStorage.setItem("user_id", ${JSON.stringify(USER.id)});
        localStorage.setItem("display_name", ${JSON.stringify(USER.display_name)});
        localStorage.setItem("email", ${JSON.stringify(USER.email)});
      }
    } catch (e) {}
    ${cursor ? CURSOR : ""}
  `);
  return page;
}
