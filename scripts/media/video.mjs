// The demo video: scenes recorded from the real app (running against demo data),
// then cut together with ffmpeg: title card, captions, crossfades, outro, and a GIF preview.
//   1. cd frontend && npm run dev
//   2. node scripts/media/video.mjs
// Needs ffmpeg on PATH. Output: docs/media/reflectra-demo.mp4 and docs/media/reflectra-demo.gif

import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { sleep } from "./cdp.mjs";
import { BASE, openStage } from "./stage.mjs";
import { DEMO_MESSAGE } from "./demo-data.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const MEDIA = join(ROOT, "docs", "media");
const WORK = mkdtempSync(join(tmpdir(), "reflectra-video-"));
const W = 1920;
const H = 1080;
const FPS = 30;
const FADE = 0.6;
let GIF_FROM = 4.6;
let GIF_TO = 34;

const SCENES = [
  { key: "home", label: "Reflectra", caption: "A mirror for your mind. It listens, notices, and learns who you are." },
  { key: "chat", label: "Conversation", caption: "Talk like you'd text a friend. Replies remember your life and the people in it." },
  { key: "mirror", label: "Mirror mode", caption: "Switch to Mirror, and it talks back as you, in your own voice." },
  { key: "persona", label: "Persona", caption: "It reads how you think from how you write. Disagree? Drag it and watch your shape change." },
  { key: "people", label: "People", caption: "Your people, in orbit. The closer they are, the more recently they came up." },
  { key: "reflections", label: "Reflections", caption: "Patterns it noticed, each one backed by your own words." },
  { key: "timeline", label: "Timeline", caption: "Your story, day by day, with how you changed along the way." },
  { key: "week", label: "Your week", caption: "Every Sunday, your week comes back to you as a short story." },
  { key: "colour", label: "Your colour", caption: "Make it yours. Pick a colour and the whole app follows." },
  { key: "how", label: "How it works", caption: "Nothing hidden. Every rule and every number is on show." },
];

// ------------------------------------------------------------------ recording
const scrollTo = (page, expression) =>
  page.eval(`(() => {
    const scroller = document.querySelector("main .overflow-y-auto") || document.scrollingElement;
    const target = ${expression};
    if (target) scroller.scrollTo({ top: target.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 24, behavior: "smooth" });
  })()`);

const rect = (page, expression) =>
  page.eval(`(() => { const r = (${expression}).getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; })()`);

const ACTIONS = {
  async home(page) {
    await page.goto(`${BASE}/`, 300);
    await sleep(2600);
    await page.moveTo(1180, 380, 1400);
    await sleep(1600);
  },
  async chat(page) {
    await page.goto(`${BASE}/app/chat?mode=reflection`, 900);
    await page.click("textarea", undefined, { move: 900 });
    await sleep(300);
    await page.type(DEMO_MESSAGE, 38);
    await sleep(400);
    await page.key("Enter", "Enter", 13);
    await page.waitFor("document.querySelector('.memory-chip')", 20000);
    await sleep(1600);
    const chip = await page.box(".memory-chip");
    await page.moveTo(chip.x, chip.y, 800);
    await sleep(900);
    await page.click('button[aria-label="Good reply"]', undefined, { move: 600 });
    await sleep(1800);
  },
  async mirror(page) {
    await page.goto(`${BASE}/app/chat?mode=reflection`, 1200);
    await page.click('button[data-mode="mirror"]', undefined, { move: 900 });
    await sleep(2600);
  },
  async persona(page) {
    await page.goto(`${BASE}/app/personality`, 300);
    await sleep(3200);
    await scrollTo(page, `[...document.querySelectorAll("section")].find((s) => s.textContent.includes("Is this you?"))`);
    await sleep(1200);
    await page.click("button", "Not quite", { move: 800 });
    await sleep(700);
    const track = await rect(page, `document.querySelector("input[type=range]")`);
    const y = track.y + track.h / 2;
    await page.drag({ x: track.x + track.w * 0.34, y }, { x: track.x + track.w * 0.8, y }, 1500);
    await sleep(500);
    await page.drag({ x: track.x + track.w * 0.8, y }, { x: track.x + track.w * 0.6, y }, 900);
    await sleep(1600);
  },
  async people(page) {
    await page.goto(`${BASE}/app/people`, 300);
    await sleep(3000);
    await page.click('[role="button"][aria-label^="Kabir"]', undefined, { move: 900 });
    await sleep(1500);
    await page.click('[role="button"][aria-label^="Ananya"]', undefined, { move: 700 });
    await sleep(2200);
  },
  async reflections(page) {
    await page.goto(`${BASE}/app/reflections`, 300);
    await sleep(4200);
    await page.scroll(520, 1800);
    await sleep(1400);
  },
  async timeline(page) {
    await page.goto(`${BASE}/app/memory`, 300);
    await sleep(2200);
    await page.moveTo(900, 500, 300);
    await page.scroll(1500, 4200);
    await sleep(900);
  },
  async week(page) {
    await page.goto(`${BASE}/app/week`, 300);
    await sleep(1800);
    await page.click("button", "Play your week", { move: 900 });
    await sleep(2600);
    await page.key("ArrowRight", "ArrowRight", 39);
    await sleep(2900);
    await page.key("ArrowRight", "ArrowRight", 39);
    await sleep(2300);
    await page.key("ArrowRight", "ArrowRight", 39);
    await sleep(2300);
  },
  async colour(page) {
    await page.goto(`${BASE}/app/settings`, 1200);
    await scrollTo(page, `[...document.querySelectorAll("section")].find((s) => s.querySelector("h2")?.textContent.includes("Your colour"))`);
    await sleep(1300);
    await page.click('[aria-label="Ready-made colours"] button', "Forest", { move: 900 });
    await sleep(1800);
    await page.click('[aria-label="Ready-made colours"] button', "Sunset", { move: 700 });
    await sleep(1800);
    await page.click('[aria-label="Ready-made colours"] button', "Moonlit", { move: 700 });
    await sleep(1700);
  },
  async how(page) {
    await page.goto(`${BASE}/app/architecture`, 300);
    await sleep(1600);
    await page.moveTo(1000, 520, 300);
    await page.scroll(2600, 5600);
    await sleep(900);
  },
};

function run(cmd, args, cwd = WORK) {
  const res = spawnSync(cmd, args, { cwd, stdio: ["ignore", "ignore", "pipe"], maxBuffer: 1 << 26 });
  if (res.status !== 0) throw new Error(`${cmd} failed:\n${res.stderr?.toString().slice(-3000)}`);
}

function probeDuration(file) {
  const res = spawnSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file], { cwd: WORK });
  return parseFloat(res.stdout.toString());
}

/** Frames with timestamps -> a constant-frame-rate clip. */
function framesToClip(frames, name) {
  const dir = join(WORK, name);
  mkdirSync(dir, { recursive: true });
  const lines = [];
  frames.forEach((frame, i) => {
    const file = `f${String(i).padStart(5, "0")}.jpg`;
    writeFileSync(join(dir, file), frame.data);
    const next = frames[i + 1]?.t ?? frame.t + 0.5;
    lines.push(`file '${file}'`, `duration ${Math.max(0.001, next - frame.t).toFixed(4)}`);
  });
  lines.push(`file 'f${String(frames.length - 1).padStart(5, "0")}.jpg'`);
  writeFileSync(join(dir, "list.txt"), lines.join("\n"));
  run(
    "ffmpeg",
    ["-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-vf", `scale=${W}:${H}:flags=lanczos,fps=${FPS},format=yuv420p`, "-c:v", "libx264", "-preset", "fast", "-crf", "16", `../${name}.mp4`],
    dir,
  );
  return join(WORK, `${name}.mp4`);
}

async function record() {
  const page = await openStage({ width: 1600, height: 900, scale: W / 1600, cursor: true });
  const clips = [];
  try {
    for (const scene of SCENES) {
      process.stdout.write(`recording ${scene.key}… `);
      await page.goto("about:blank", 100);
      const stop = await page.record({ quality: 90, maxWidth: W, maxHeight: H });
      await ACTIONS[scene.key](page);
      const frames = await stop();
      // Drop the blank frames from before the page started drawing.
      const firstReal = Math.max(0, frames.findIndex((f) => f.data.length > 30_000));
      clips.push({ ...scene, file: framesToClip(frames.slice(firstReal), scene.key) });
      console.log(`${frames.length} frames`);
    }
  } finally {
    await page.close();
  }
  return clips;
}

// ------------------------------------------------------------------ editing
const FONT = { serif: "C:/Windows/Fonts/georgia.ttf", serifItalic: "C:/Windows/Fonts/georgiai.ttf", sans: "C:/Windows/Fonts/segoeui.ttf", sansBold: "C:/Windows/Fonts/segoeuib.ttf", mono: "C:/Windows/Fonts/consola.ttf" };

function prepareFonts() {
  for (const [name, path] of Object.entries(FONT)) {
    if (!existsSync(path)) throw new Error(`Font missing: ${path} (set FONT paths in video.mjs for your system)`);
    copyFileSync(path, join(WORK, `${name}.ttf`));
  }
}

const fade = (start, end, inFor = 0.45, outFor = 0.45) =>
  `alpha='if(lt(t,${start}),0,if(lt(t,${start + inFor}),(t-${start})/${inFor},if(lt(t,${end - outFor}),1,if(lt(t,${end}),(${end}-t)/${outFor},0))))'`;

function text(file, content) {
  writeFileSync(join(WORK, file), content);
  return file;
}

// The app floats as a window over a blurred copy of itself; the caption gets its own band below.
const APP_W = 1536;
const APP_H = 864;
const APP_X = (W - APP_W) / 2;
const APP_Y = 34;

/** A scene: framed app window, step label and caption. */
function captionClip(clip, index) {
  const duration = probeDuration(clip.file);
  const label = text(`label-${clip.key}.txt`, `${String(index + 1).padStart(2, "0")}  /  ${clip.label.toUpperCase()}`);
  const caption = text(`caption-${clip.key}.txt`, clip.caption);
  const out = `cap-${clip.key}.mp4`;
  const end = duration - 0.2;
  const graph = [
    // three chains: blurred backdrop, the app scaled into a window, then window + captions on top
    "[0:v]split[a][b]",
    `[a]scale=${W / 4}:${H / 4},boxblur=12:2,scale=${W}:${H},eq=brightness=-0.28:saturation=1.35,` +
      `drawbox=x=${APP_X - 18}:y=${APP_Y - 10}:w=${APP_W + 36}:h=${APP_H + 36}:color=black@0.35:t=fill[bg]`,
    `[b]scale=${APP_W}:${APP_H}:flags=lanczos[app]`,
    `[bg][app]overlay=${APP_X}:${APP_Y},` +
      `drawbox=x=${APP_X - 1}:y=${APP_Y - 1}:w=${APP_W + 2}:h=${APP_H + 2}:color=white@0.16:t=1,` +
      `drawtext=fontfile=mono.ttf:textfile=${label}:fontsize=21:fontcolor=0xC4BAFF:x=(w-text_w)/2:y=${APP_Y + APP_H + 40}:${fade(0.3, end)},` +
      `drawtext=fontfile=sansBold.ttf:textfile=${caption}:fontsize=38:fontcolor=white:x=(w-text_w)/2:y=${APP_Y + APP_H + 82}:${fade(0.45, end)},` +
      "format=yuv420p[v]",
  ].join(";");
  run("ffmpeg", ["-y", "-i", clip.file, "-filter_complex", graph, "-map", "[v]", "-c:v", "libx264", "-preset", "fast", "-crf", "16", out]);
  return { file: join(WORK, out), duration };
}

/** A title or end card over a blurred, darkened screenshot of the app. */
function card(name, background, lines, duration) {
  const draws = lines.map((line, i) => {
    const file = text(`${name}-${i}.txt`, line.text);
    return `drawtext=fontfile=${line.font}.ttf:textfile=${file}:fontsize=${line.size}:fontcolor=${line.color}:x=(w-text_w)/2:y=${line.y}:${fade(line.at, duration - 0.15, 0.7, 0.5)}`;
  });
  const vf = [
    `scale=${W}:${H}:force_original_aspect_ratio=increase`,
    `crop=${W}:${H}`,
    "gblur=sigma=28",
    "eq=brightness=-0.22:saturation=1.25",
    ...draws,
    `fade=t=in:st=0:d=0.6`,
    "format=yuv420p",
  ].join(",");
  run("ffmpeg", ["-y", "-loop", "1", "-t", String(duration), "-i", background, "-vf", vf, "-r", String(FPS), "-c:v", "libx264", "-preset", "fast", "-crf", "16", `${name}.mp4`]);
  return { file: join(WORK, `${name}.mp4`), duration };
}

function stitch(parts, out) {
  const inputs = parts.flatMap((p) => ["-i", p.file]);
  const filters = [];
  let previous = "[0:v]";
  let offset = parts[0].duration - FADE;
  const transitions = ["fade", "smoothleft", "fade", "smoothup", "fade", "circleopen", "fade", "smoothleft", "fade", "smoothup", "fade", "fadeblack"];
  for (let i = 1; i < parts.length; i++) {
    const label = i === parts.length - 1 ? "[v]" : `[x${i}]`;
    filters.push(`${previous}[${i}:v]xfade=transition=${transitions[(i - 1) % transitions.length]}:duration=${FADE}:offset=${offset.toFixed(3)}${label}`);
    previous = label;
    offset += parts[i].duration - FADE;
  }
  run("ffmpeg", ["-y", ...inputs, "-filter_complex", filters.join(";"), "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]);
}

function gif(source, out) {
  // The heart of it: chat, persona and people, at a size that loads quickly in a README.
  const palette = join(WORK, "palette.png");
  const pick = `select='between(t,${GIF_FROM},${GIF_TO})',setpts=N/FRAME_RATE/TB`;
  run("ffmpeg", ["-y", "-i", source, "-vf", `${pick},fps=11,scale=880:-2:flags=lanczos,palettegen=max_colors=160:stats_mode=diff`, palette]);
  run("ffmpeg", ["-y", "-i", source, "-i", palette, "-lavfi", `${pick},fps=11,scale=880:-2:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle`, out]);
}

// ------------------------------------------------------------------ go
try {
  mkdirSync(MEDIA, { recursive: true });
  const clips = await record();
  prepareFonts();
  const shots = join(MEDIA, "screenshots");
  const home = ["01-home.webp", "01-home.png"].map((f) => join(shots, f)).find(existsSync);
  const background = home ?? join(shots, readdirSync(shots)[0]);
  run("ffmpeg", ["-y", "-i", background, "bg.png"]);

  const intro = card(
    "intro",
    "bg.png",
    [
      { text: "Reflectra", font: "serif", size: 150, color: "white", y: "h/2-150", at: 0.3 },
      { text: "a mirror for your mind", font: "serifItalic", size: 56, color: "0xC4BAFF", y: "h/2+20", at: 0.9 },
      { text: "A QUICK TOUR", font: "mono", size: 24, color: "0x9A97AE", y: "h/2+130", at: 1.5 },
    ],
    3.8,
  );
  const outro = card(
    "outro",
    "bg.png",
    [
      { text: "Every thought leaves a trace.", font: "serifItalic", size: 76, color: "white", y: "h/2-110", at: 0.3 },
      { text: "FastAPI  ·  React  ·  PostgreSQL  ·  Gemini", font: "mono", size: 30, color: "0xC4BAFF", y: "h/2+10", at: 0.8 },
      { text: "github.com/vaishnav1906/reflectra", font: "mono", size: 26, color: "0x9A97AE", y: "h/2+70", at: 1.2 },
    ],
    4.2,
  );
  const scenes = clips.map((clip, i) => captionClip(clip, i));
  // The GIF covers the chat, Mirror and Persona scenes.
  const starts = [intro, ...scenes].reduce((acc, part) => [...acc, acc.at(-1) + part.duration - FADE], [0]);
  GIF_FROM = starts[2] + 0.3;
  GIF_TO = Math.min(starts[5] - 0.2, GIF_FROM + 34);
  const final = join(MEDIA, "reflectra-demo.mp4");
  stitch([intro, ...scenes, outro], final);
  gif(final, join(MEDIA, "reflectra-demo.gif"));
  console.log("done:", final, `${Math.round(probeDuration(final))}s`);
} finally {
  rmSync(WORK, { recursive: true, force: true });
}
