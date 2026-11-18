// Screens for the in-app tutorial: the real app with demo data, on PC and on a phone,
// plus where each slide's button is (so the animated pointer lands exactly on it).
//   1. cd frontend && npm run dev
//   2. node scripts/media/tutorial-shots.mjs
// Output: frontend/public/tutorial/{desktop,mobile}/*.webp
//         frontend/src/components/tutorial/targets.json

import { spawnSync } from "node:child_process";
import { mkdirSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { sleep } from "./cdp.mjs";
import { BASE, openStage } from "./stage.mjs";
import { DEMO_MESSAGE } from "./demo-data.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PUBLIC = join(ROOT, "frontend", "public", "tutorial");
const MANIFEST = join(ROOT, "frontend", "src", "components", "tutorial", "targets.json");

const DEVICES = {
  desktop: { width: 1280, height: 800, scale: 1.25 },
  mobile: { width: 390, height: 844, scale: 1.5 },
};

const scroll = (page, expression) =>
  page.eval(`(() => {
    const target = ${expression};
    if (target) target.scrollIntoView({ block: "center" });
  })()`);

/** The element a slide points at, found by CSS selector and (optionally) its text. */
const find = (selector, text) =>
  `[...document.querySelectorAll(${JSON.stringify(selector)})].find((e) => ${text ? `e.textContent.includes(${JSON.stringify(text)})` : "true"} && e.getBoundingClientRect().width > 0)`;

/** A page panel, found by its title. */
const panel = (title) => `[...document.querySelectorAll("section")].find((s) => s.querySelector("h2")?.textContent.includes(${JSON.stringify(title)}))`;

// Each slide: page, how to get it into the right state, and what to point at. A slide
// with `callouts` points at several things in turn; each gets its own position.
const SLIDES = [
  {
    key: "navigate",
    url: "/app/chat?mode=reflection",
    target: { desktop: find("nav[aria-label='App']"), mobile: find("button[aria-label='Open menu']") },
  },
  {
    key: "message",
    url: "/app/chat?mode=reflection",
    async prepare(page) {
      await page.click("textarea", undefined, { move: 0 });
      await page.type(DEMO_MESSAGE, 0);
    },
    target: find("button:has(.sr-only)", "Send"),
  },
  {
    key: "remembered",
    url: "/app/chat?mode=reflection",
    async prepare(page) {
      await page.click("textarea", undefined, { move: 0 });
      await page.type(DEMO_MESSAGE, 0);
      await page.key("Enter", "Enter", 13);
      await page.waitFor("document.querySelector('.memory-chip')", 20000);
      await sleep(2200);
    },
    target: find(".memory-chip"),
    hover: ".chat-ai-row .chat-bubble-ai",
  },
  {
    key: "rate",
    reuse: "remembered",
    target: find("button[aria-label='Good reply']"),
  },
  {
    key: "mirror",
    url: "/app/chat?mode=reflection",
    target: find("button[data-mode='mirror']"),
  },
  {
    key: "persona",
    url: "/app/personality",
    wait: 3500,
    target: find(".trait-shape"),
  },
  {
    key: "moved",
    url: "/app/personality",
    wait: 4000,
    scrollTo: panel("How you've moved"),
    callouts: {
      lines: `${panel("How you've moved")}?.querySelector("svg")`,
      legend: `${panel("How you've moved")}?.querySelector("svg")?.nextElementSibling`,
    },
  },
  {
    key: "rhythm",
    url: "/app/personality",
    wait: 4000,
    scrollTo: panel("When you talk"),
    callouts: {
      clock: `${panel("When you talk")}?.querySelector("svg[role='img']")`,
      bars: `${panel("When you talk")}?.querySelector("div[role='img']")`,
    },
  },
  {
    key: "correct",
    url: "/app/personality",
    wait: 3000,
    target: find("button", "Not quite"),
  },
  {
    key: "orbit",
    url: "/app/people",
    wait: 3500,
    scrollTo: `document.querySelector(".people-orbit")`,
    callouts: {
      you: `document.querySelector(".people-you")`,
      inner: `document.querySelector("[role='button'][aria-label^='Ananya']")`,
      outer: `document.querySelector("[role='button'][aria-label^='Meera']")`,
      legend: `document.querySelector(".people-orbit")?.nextElementSibling`,
      open: `document.querySelector("[role='button'][aria-label^='Kabir']")`,
    },
  },
  {
    key: "people",
    url: "/app/people",
    target: find("button", "Add someone"),
  },
  {
    key: "life",
    url: "/app/life",
    target: find("button", "Read my past chats"),
  },
  {
    key: "reflections",
    url: "/app/reflections",
    wait: 4000,
    target: find("button", "Spot on"),
  },
  {
    key: "week",
    url: "/app/week",
    target: find("button", "Play your week"),
  },
  {
    key: "colour",
    url: "/app/settings",
    target: find(".colour-wheel"),
  },
  {
    key: "export",
    url: "/app/personality",
    wait: 3000,
    target: find("button", "Export PDF"),
  },
];

const manifest = {};

for (const [device, viewport] of Object.entries(DEVICES)) {
  const out = join(PUBLIC, device);
  mkdirSync(out, { recursive: true });
  manifest[device] = {};
  const page = await openStage(viewport);
  // The install suggestion card would only distract inside the tutorial's screens.
  await page.addInitScript(`try { localStorage.setItem("reflectra:install-nudge-dismissed", "1"); } catch (e) {}`);
  try {
    let lastUrl = null;
    for (const slide of SLIDES) {
      if (!slide.reuse) {
        await page.goto(`${BASE}${slide.url}`, slide.wait ?? 2500);
        if (slide.prepare) await slide.prepare(page);
        lastUrl = slide.url;
      }
      const target = slide.callouts ? slide.scrollTo : typeof slide.target === "string" ? slide.target : slide.target[device];
      await scroll(page, target);
      await sleep(slide.callouts ? 1500 : 500); // let charts finish drawing
      if (slide.hover && device === "desktop") {
        const { x, y } = await page.box(slide.hover);
        await page.moveTo(x, y, 0);
        await sleep(300);
      }
      await page.eval("document.activeElement?.blur?.()").catch(() => undefined);
      const measure = (expression) =>
        page.eval(`(() => {
          const el = ${expression};
          if (!el) return null;
          const r = el.getBoundingClientRect();
          return { x: r.left / innerWidth, y: r.top / innerHeight, w: r.width / innerWidth, h: r.height / innerHeight };
        })()`);
      const round = (v) => Math.round(v * 10000) / 100; // percent, 2 decimals
      const asPercent = (r) => ({ x: round(r.x), y: round(r.y), w: round(r.w), h: round(r.h) });
      if (slide.callouts) {
        manifest[device][slide.key] = {};
        for (const [id, expression] of Object.entries(slide.callouts)) {
          const rect = await measure(expression);
          if (!rect) throw new Error(`${device}/${slide.key}/${id}: not found on ${lastUrl}`);
          if (rect.y < 0 || rect.y + rect.h > 1.01) throw new Error(`${device}/${slide.key}/${id}: off screen ${JSON.stringify(rect)}`);
          manifest[device][slide.key][id] = asPercent(rect);
        }
      } else {
        const rect = await measure(target);
        if (!rect) throw new Error(`${device}/${slide.key}: target not found on ${lastUrl}`);
        manifest[device][slide.key] = asPercent(rect);
      }

      const png = join(out, `${slide.key}.png`);
      writeFileSync(png, await page.screenshot());
      const webp = join(out, `${slide.key}.webp`);
      const res = spawnSync("ffmpeg", ["-y", "-loglevel", "error", "-i", png, "-c:v", "libwebp", "-quality", "80", "-compression_level", "6", webp]);
      if (res.status !== 0) throw new Error(`ffmpeg failed for ${webp}`);
      unlinkSync(png);
      console.log(`${device}/${slide.key}`, manifest[device][slide.key]);
    }
  } finally {
    await page.close();
  }
}

mkdirSync(dirname(MANIFEST), { recursive: true });
writeFileSync(MANIFEST, `${JSON.stringify(manifest, null, 2)}\n`);
console.log("saved", MANIFEST);
