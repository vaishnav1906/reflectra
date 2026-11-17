// Screenshots for the README, taken from the real app running against demo data.
//   1. cd frontend && npm run dev        (the app on http://localhost:8080)
//   2. node scripts/media/screenshots.mjs
// Output: docs/media/screenshots/*.png

import { spawnSync } from "node:child_process";
import { mkdirSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { sleep } from "./cdp.mjs";
import { BASE, openStage } from "./stage.mjs";
import { DEMO_MESSAGE } from "./demo-data.mjs";

const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "media", "screenshots");
mkdirSync(OUT, { recursive: true });

const scrollTo = (page, expression) =>
  page.eval(`(() => {
    const scroller = document.querySelector("main .overflow-y-auto") || document.scrollingElement;
    const target = ${expression};
    if (target) scroller.scrollTo({ top: target.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 24 });
  })()`);

/** Saved as WebP (about a tenth of the PNG size, still crisp). Needs ffmpeg on PATH. */
async function shoot(page, name) {
  await page.eval("document.activeElement && document.activeElement.blur && document.activeElement.blur()").catch(() => undefined);
  const png = join(OUT, `${name}.png`);
  writeFileSync(png, await page.screenshot());
  const res = spawnSync("ffmpeg", ["-y", "-loglevel", "error", "-i", png, "-c:v", "libwebp", "-quality", "88", "-compression_level", "6", join(OUT, `${name}.webp`)]);
  if (res.status === 0) unlinkSync(png);
  console.log("saved", name);
}

const page = await openStage({ width: 1440, height: 900, scale: 1.5 });
try {
  // Home
  await page.goto(`${BASE}/`, 4000);
  await shoot(page, "01-home");

  // Chat: a message, the reply streaming in, then what it knew and remembered
  await page.goto(`${BASE}/app/chat?mode=reflection`, 2500);
  await page.click("textarea", undefined, { move: 0 });
  await page.type(DEMO_MESSAGE, 4);
  await page.key("Enter", "Enter", 13);
  await page.waitFor("document.querySelector('.memory-chip')", 20000);
  await sleep(2200);
  const reply = await page.box(".chat-ai-row .chat-bubble-ai");
  await page.moveTo(reply.x, reply.y, 0);
  await sleep(400);
  await shoot(page, "02-chat");

  // Mirror mode
  await page.goto(`${BASE}/app/chat?mode=mirror`, 2500);
  await shoot(page, "03-mirror");

  // Persona: the shape, then correcting a trait with the live preview
  await page.goto(`${BASE}/app/personality`, 3500);
  await shoot(page, "04-persona");
  await scrollTo(page, `[...document.querySelectorAll("section")].find((s) => s.textContent.includes("Is this you?"))`);
  await sleep(400);
  await page.click("button", "Not quite", { move: 0 });
  await sleep(300);
  await page.eval(`(() => {
    const input = document.querySelector('input[type=range]');
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    set.call(input, '72');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
  })()`);
  await sleep(1200);
  await scrollTo(page, `document.querySelector("input[type=range]").closest("section")`);
  await sleep(500);
  await shoot(page, "05-persona-correct");

  // People
  await page.goto(`${BASE}/app/people?person=30000000-0000-4000-8000-000000000001`, 3500);
  await shoot(page, "06-people");

  // Your life
  await page.goto(`${BASE}/app/life`, 2500);
  await shoot(page, "07-life");

  // Reflections (after they've assembled)
  await page.goto(`${BASE}/app/reflections`, 4500);
  await shoot(page, "08-reflections");

  // Timeline, scrolled so the light is running down the days
  await page.goto(`${BASE}/app/memory`, 3500);
  await scrollTo(page, `document.querySelector(".thread-list")`);
  await page.scroll(-160, 300);
  await sleep(1200);
  await shoot(page, "09-timeline");

  // Your week, and its reel
  await page.goto(`${BASE}/app/week`, 3000);
  await shoot(page, "10-week");
  await page.click("button", "Play your week", { move: 0 });
  await sleep(600);
  await page.key("ArrowRight", "ArrowRight", 39);
  await sleep(2200);
  await shoot(page, "11-week-reel");
  await page.key("Escape", "Escape", 27);

  // Settings: your colour
  await page.goto(`${BASE}/app/settings`, 3000);
  await scrollTo(page, `[...document.querySelectorAll("section")].find((s) => s.querySelector("h2")?.textContent.includes("Your colour"))`);
  await sleep(600);
  await shoot(page, "12-colour");

  // How it works
  await page.goto(`${BASE}/app/architecture`, 3000);
  await scrollTo(page, `document.querySelector("[data-step='3']")`);
  await sleep(1500);
  await shoot(page, "13-how-it-works");
} finally {
  await page.close();
}

// Phone size
const phone = await openStage({ width: 390, height: 844, scale: 2.5 });
try {
  await phone.goto(`${BASE}/app/people?person=30000000-0000-4000-8000-000000000001`, 3500);
  await shoot(phone, "14-phone-people");
  await phone.goto(`${BASE}/app/personality`, 3500);
  await shoot(phone, "15-phone-persona");
} finally {
  await phone.close();
}
