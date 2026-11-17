// A tiny Chrome DevTools Protocol driver for Microsoft Edge / Chrome, using only
// Node's built-in WebSocket and fetch (Node 22+). Enough to script the app for
// screenshots and the demo video without installing Playwright.

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const BROWSERS = [
  process.env.BROWSER_PATH,
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].filter(Boolean);

export async function launch({ width = 1440, height = 900, scale = 1, port = 9333, headless = true } = {}) {
  const exe = BROWSERS.find((p) => existsSync(p));
  if (!exe) throw new Error("No Edge or Chrome found. Set BROWSER_PATH.");
  const profile = mkdtempSync(join(tmpdir(), "reflectra-media-"));
  const proc = spawn(
    exe,
    [
      headless ? "--headless=new" : "",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      `--window-size=${width},${height}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--hide-scrollbars",
      "--mute-audio",
      "--disable-extensions",
      "--force-color-profile=srgb",
      "about:blank",
    ].filter(Boolean),
    { stdio: "ignore" },
  );

  let info;
  for (let i = 0; i < 60 && !info; i++) {
    await sleep(250);
    info = await fetch(`http://127.0.0.1:${port}/json/version`).then((r) => r.json()).catch(() => null);
  }
  if (!info) throw new Error("The browser didn't start.");

  const browser = new Connection(info.webSocketDebuggerUrl);
  await browser.ready;
  const { targetId } = await browser.send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await browser.send("Target.attachToTarget", { targetId, flatten: true });
  const page = new Page(browser, sessionId, { width, height, scale });
  await page.init();
  page.close = async () => {
    await browser.send("Browser.close").catch(() => undefined);
    proc.kill();
    await sleep(500);
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch {
      /* Windows may still hold a lock; it's in the temp folder anyway */
    }
  };
  return page;
}

class Connection {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.id = 0;
    this.pending = new Map();
    this.listeners = [];
    this.ready = new Promise((resolve, reject) => {
      this.ws.onopen = resolve;
      this.ws.onerror = reject;
    });
    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? reject(new Error(`${msg.error.message} ${msg.error.data ?? ""}`)) : resolve(msg.result);
      } else if (msg.method) {
        for (const listener of this.listeners) listener(msg);
      }
    };
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
  on(listener) {
    this.listeners.push(listener);
  }
}

class Page {
  constructor(connection, sessionId, viewport) {
    this.c = connection;
    this.sessionId = sessionId;
    this.viewport = viewport;
    this.mouse = { x: viewport.width / 2, y: viewport.height / 2 };
    this.handlers = new Map();
    connection.on((msg) => {
      if (msg.sessionId !== sessionId) return;
      for (const handler of this.handlers.get(msg.method) ?? []) handler(msg.params);
    });
  }
  send(method, params) {
    return this.c.send(method, params, this.sessionId);
  }
  on(method, handler) {
    this.handlers.set(method, [...(this.handlers.get(method) ?? []), handler]);
  }
  off(method) {
    this.handlers.delete(method);
  }

  async init() {
    await this.send("Page.enable");
    await this.send("Runtime.enable");
    await this.send("Emulation.setDeviceMetricsOverride", {
      width: this.viewport.width,
      height: this.viewport.height,
      deviceScaleFactor: this.viewport.scale,
      mobile: false,
    });
  }

  /** Answer matching requests from `respond(url, method, postData)` instead of the network. */
  async intercept(patterns, respond) {
    await this.send("Fetch.enable", { patterns: patterns.map((urlPattern) => ({ urlPattern, requestStage: "Request" })) });
    this.on("Fetch.requestPaused", async ({ requestId, request }) => {
      try {
        const res = respond(request.url, request.method, request.postData ?? "");
        if (res.delayMs) await sleep(res.delayMs);
        await this.send("Fetch.fulfillRequest", {
          requestId,
          responseCode: res.status,
          responseHeaders: [
            { name: "Content-Type", value: res.contentType },
            { name: "Access-Control-Allow-Origin", value: "*" },
            { name: "Access-Control-Allow-Headers", value: "*" },
          ],
          body: Buffer.from(res.body).toString("base64"),
        });
      } catch (err) {
        console.error("intercept failed for", request.url, err.message);
        await this.send("Fetch.continueRequest", { requestId }).catch(() => undefined);
      }
    });
  }

  /** Runs in every page before its own scripts. */
  addInitScript(source) {
    return this.send("Page.addScriptToEvaluateOnNewDocument", { source });
  }

  async goto(url, settleMs = 1200) {
    const loaded = new Promise((resolve) => {
      const done = () => {
        this.off("Page.loadEventFired");
        resolve();
      };
      this.on("Page.loadEventFired", done);
    });
    await this.send("Page.navigate", { url });
    await Promise.race([loaded, sleep(15000)]);
    await sleep(settleMs);
  }

  async eval(expression) {
    const { result, exceptionDetails } = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (exceptionDetails) throw new Error(exceptionDetails.exception?.description ?? exceptionDetails.text);
    return result.value;
  }

  async waitFor(expression, timeout = 10000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      if (await this.eval(`Boolean(${expression})`).catch(() => false)) return true;
      await sleep(100);
    }
    throw new Error(`Timed out waiting for ${expression}`);
  }

  /** Centre of the first element matching a CSS selector, optionally containing some text. */
  async box(selector, text) {
    const pos = await this.eval(`(() => {
      const els = [...document.querySelectorAll(${JSON.stringify(selector)})];
      const el = els.find((e) => ${text ? `e.textContent.includes(${JSON.stringify(text)})` : "true"});
      if (!el) return null;
      el.scrollIntoView({ block: "nearest", inline: "nearest" });
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    })()`);
    if (!pos) throw new Error(`No element for ${selector} ${text ?? ""}`);
    return pos;
  }

  /** Glide the mouse to (x, y) over `ms`, easing in and out, so the cursor moves visibly. */
  async moveTo(x, y, ms = 650) {
    const from = { ...this.mouse };
    const steps = Math.max(1, Math.round(ms / 16));
    for (let i = 1; i <= steps; i++) {
      const t = i / steps;
      const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      this.mouse = { x: from.x + (x - from.x) * e, y: from.y + (y - from.y) * e };
      await this.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: this.mouse.x, y: this.mouse.y });
      await sleep(16);
    }
  }

  async click(selector, text, { move = 650, pause = 180 } = {}) {
    const { x, y } = await this.box(selector, text);
    await this.moveTo(x, y, move);
    await sleep(pause);
    await this.send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
    await sleep(70);
    await this.send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
  }

  async drag(from, to, ms = 900) {
    await this.moveTo(from.x, from.y, 500);
    await this.send("Input.dispatchMouseEvent", { type: "mousePressed", x: from.x, y: from.y, button: "left", clickCount: 1 });
    const steps = Math.round(ms / 16);
    for (let i = 1; i <= steps; i++) {
      const t = i / steps;
      this.mouse = { x: from.x + (to.x - from.x) * t, y: from.y + (to.y - from.y) * t };
      await this.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: this.mouse.x, y: this.mouse.y, button: "left", buttons: 1 });
      await sleep(16);
    }
    await this.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: to.x, y: to.y, button: "left", clickCount: 1 });
  }

  async type(text, perChar = 45) {
    for (const ch of text) {
      await this.send("Input.insertText", { text: ch });
      await sleep(perChar + Math.random() * perChar * 0.6);
    }
  }

  async key(key, code = key, keyCode = 0) {
    await this.send("Input.dispatchKeyEvent", { type: "keyDown", key, code, windowsVirtualKeyCode: keyCode });
    await this.send("Input.dispatchKeyEvent", { type: "keyUp", key, code, windowsVirtualKeyCode: keyCode });
  }

  async wheel(deltaY, x = this.mouse.x, y = this.mouse.y) {
    await this.send("Input.dispatchMouseEvent", { type: "mouseWheel", x, y, deltaX: 0, deltaY });
  }

  /** Scroll smoothly by `distance` pixels over `ms`. */
  async scroll(distance, ms = 1200) {
    const steps = Math.max(1, Math.round(ms / 33));
    for (let i = 0; i < steps; i++) {
      await this.wheel(distance / steps);
      await sleep(33);
    }
  }

  async screenshot(format = "png") {
    const { data } = await this.send("Page.captureScreenshot", { format, captureBeyondViewport: false });
    return Buffer.from(data, "base64");
  }

  /** Start capturing frames; returns a stop() that resolves to [{data, t}] (t in seconds). */
  async record({ quality = 88, maxWidth = 1920, maxHeight = 1200 } = {}) {
    const frames = [];
    this.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
      frames.push({ data: Buffer.from(data, "base64"), t: metadata.timestamp });
      this.send("Page.screencastFrameAck", { sessionId }).catch(() => undefined);
    });
    await this.send("Page.startScreencast", { format: "jpeg", quality, maxWidth, maxHeight, everyNthFrame: 1 });
    return async () => {
      await this.send("Page.stopScreencast");
      this.off("Page.screencastFrame");
      return frames;
    };
  }
}

export { sleep };
