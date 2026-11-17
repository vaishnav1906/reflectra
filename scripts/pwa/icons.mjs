// PNG app icons from frontend/public/icon.svg (iPhones ignore SVG icons, and Android
// wants a "maskable" version it can crop into its own shape).
//   node scripts/pwa/icons.mjs
// Output: frontend/public/icons/*.png

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { launch } from "../media/cdp.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PUBLIC = join(ROOT, "frontend", "public");
const OUT = join(PUBLIC, "icons");
mkdirSync(OUT, { recursive: true });

const svg = readFileSync(join(PUBLIC, "icon.svg"), "utf8");
// The same mirror without its rounded tile, for icons the platform shapes itself.
const bare = svg.replace(/<rect[^>]*\/>/, "");
const BG = "#0b0a12";

const ICONS = [
  // name, size, what goes in the square
  { name: "icon-192.png", size: 192, html: (s) => tile(svg, s, 1) },
  { name: "icon-512.png", size: 512, html: (s) => tile(svg, s, 1) },
  // Maskable: full-bleed background, the mirror inside the 80% safe zone.
  { name: "maskable-512.png", size: 512, html: (s) => fill(bare, s, 0.78) },
  // iOS rounds the corners itself and shows transparency as black.
  { name: "apple-touch-icon.png", size: 180, html: (s) => fill(bare, s, 0.92) },
  { name: "badge-96.png", size: 96, html: (s) => tile(svg, s, 1) },
];

function tile(source, size, scale) {
  return `<div style="width:${size}px;height:${size}px;display:grid;place-items:center">${sized(source, size * scale)}</div>`;
}
function fill(source, size, scale) {
  return `<div style="width:${size}px;height:${size}px;background:${BG};display:grid;place-items:center">${sized(source, size * scale)}</div>`;
}
function sized(source, px) {
  return source.replace("<svg ", `<svg width="${px}" height="${px}" `);
}

const page = await launch({ width: 512, height: 512, scale: 1, port: 9334 });
try {
  await page.send("Emulation.setDefaultBackgroundColorOverride", { color: { r: 0, g: 0, b: 0, a: 0 } });
  for (const icon of ICONS) {
    await page.send("Emulation.setDeviceMetricsOverride", { width: icon.size, height: icon.size, deviceScaleFactor: 1, mobile: false });
    const html = `<!doctype html><html><body style="margin:0;background:transparent">${icon.html(icon.size)}</body></html>`;
    await page.goto(`data:text/html;base64,${Buffer.from(html).toString("base64")}`, 300);
    writeFileSync(join(OUT, icon.name), await page.screenshot());
    console.log("saved", icon.name);
  }
} finally {
  await page.close();
}
