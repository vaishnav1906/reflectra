import { beforeEach, describe, expect, it, vi } from "vitest";

const fetchMock = vi.fn();
vi.mock("@/lib/api", () => ({ apiFetch: (...args: unknown[]) => fetchMock(...args) }));

import { ChatError, sendChat } from "@/lib/chatStream";
import { readChatFromZip } from "@/lib/unzip";
// jsdom's Blob has no arrayBuffer()/stream(); browsers and Node do.
import { Blob as NodeBlob } from "node:buffer";

function sse(chunks: string[], status = 200) {
  const encoder = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { status, headers: { "Content-Type": "text/event-stream" } });
}

const event = (data: object) => `data: ${JSON.stringify(data)}\n\n`;

describe("sendChat", () => {
  beforeEach(() => fetchMock.mockReset());

  it("shows partial text, takes back a rejected draft, and returns the final reply", async () => {
    // Events split across network chunks at awkward places, as real streams are.
    const stream = event({ type: "partial", text: "yo" }) + event({ type: "reset" }) + event({ type: "partial", text: "hey there" }) +
      event({ type: "done", reply: "hey there", conversation_id: "c1", mode: "reflection" });
    fetchMock.mockResolvedValueOnce(sse([stream.slice(0, 17), stream.slice(17, 60), stream.slice(60)]));
    const seen: string[] = [];
    const result = await sendChat({ message: "hi" }, { onPartial: (t) => seen.push(t), onReset: () => seen.push("<reset>") });
    expect(seen).toEqual(["yo", "<reset>", "hey there"]);
    expect(result).toMatchObject({ reply: "hey there", conversation_id: "c1" });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/chat/stream");
  });

  it("turns a busy event into a 429 error", async () => {
    fetchMock.mockResolvedValueOnce(sse([event({ type: "error", status: 429, detail: "catching its breath" })]));
    const error = await sendChat({}, { onPartial: () => {}, onReset: () => {} }).catch((e) => e);
    expect(error).toBeInstanceOf(ChatError);
    expect(error.status).toBe(429);
    expect(error.message).toBe("catching its breath");
  });

  it("reports a stream that ends without a reply", async () => {
    fetchMock.mockResolvedValueOnce(sse([event({ type: "partial", text: "half" })]));
    await expect(sendChat({}, { onPartial: () => {}, onReset: () => {} })).rejects.toThrow(/cut off/);
  });

  it("falls back to plain /chat when streaming isn't available", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response("not found", { status: 404 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ reply: "plain" }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const result = await sendChat({ message: "hi" }, { onPartial: () => {}, onReset: () => {} });
    expect(result.reply).toBe("plain");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/chat");
  });

  it("passes on an error the server refused with before streaming", async () => {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Conversation not found" }), { status: 400 }));
    await expect(sendChat({}, { onPartial: () => {}, onReset: () => {} })).rejects.toThrow("Conversation not found");
  });
});

/** Build a small zip by hand: one entry per file, stored or deflated. */
async function makeZip(files: { name: string; text: string; deflate?: boolean }[]) {
  const encoder = new TextEncoder();
  const locals: Uint8Array[] = [];
  const centrals: Uint8Array[] = [];
  let offset = 0;
  for (const file of files) {
    const name = encoder.encode(file.name);
    const raw = encoder.encode(file.text);
    let data = raw;
    if (file.deflate) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const stream = (new NodeBlob([raw]).stream() as any).pipeThrough(new CompressionStream("deflate-raw"));
      data = new Uint8Array(await new Response(stream as ReadableStream).arrayBuffer());
    }
    const local = new Uint8Array(30 + name.length + data.length);
    const lv = new DataView(local.buffer);
    lv.setUint32(0, 0x04034b50, true);
    lv.setUint16(8, file.deflate ? 8 : 0, true);
    lv.setUint32(18, data.length, true);
    lv.setUint32(22, raw.length, true);
    lv.setUint16(26, name.length, true);
    local.set(name, 30);
    local.set(data, 30 + name.length);
    const central = new Uint8Array(46 + name.length);
    const cv = new DataView(central.buffer);
    cv.setUint32(0, 0x02014b50, true);
    cv.setUint16(10, file.deflate ? 8 : 0, true);
    cv.setUint32(20, data.length, true);
    cv.setUint32(24, raw.length, true);
    cv.setUint16(28, name.length, true);
    cv.setUint32(42, offset, true);
    central.set(name, 46);
    locals.push(local);
    centrals.push(central);
    offset += local.length;
  }
  const centralSize = centrals.reduce((n, c) => n + c.length, 0);
  const end = new Uint8Array(22);
  const ev = new DataView(end.buffer);
  ev.setUint32(0, 0x06054b50, true);
  ev.setUint16(8, files.length, true);
  ev.setUint16(10, files.length, true);
  ev.setUint32(12, centralSize, true);
  ev.setUint32(16, offset, true);
  return new NodeBlob([...locals, ...centrals, end]) as unknown as Blob;
}

describe("readChatFromZip", () => {
  it("finds the WhatsApp chat among photos, deflated", async () => {
    const zip = await makeZip([
      { name: "IMG-0001.jpg", text: "ÿØbinary" },
      { name: "_chat.txt", text: "[12/03/24, 10:15:32 PM] Vaish: yo whats up", deflate: true },
    ]);
    expect(await readChatFromZip(zip)).toEqual({ name: "_chat.txt", text: "[12/03/24, 10:15:32 PM] Vaish: yo whats up" });
  });

  it("finds ChatGPT's conversations.json inside a folder, stored", async () => {
    const zip = await makeZip([
      { name: "__MACOSX/._conversations.json", text: "junk" },
      { name: "export/conversations.json", text: "[]" },
      { name: "export/chat.html", text: "<html>" },
    ]);
    expect(await readChatFromZip(zip)).toEqual({ name: "conversations.json", text: "[]" });
  });

  it("explains what's wrong with a zip that has no chat in it", async () => {
    await expect(readChatFromZip(await makeZip([{ name: "photo.jpg", text: "x" }]))).rejects.toThrow(/No chat text/);
    await expect(readChatFromZip(new NodeBlob(["definitely not a zip"]) as unknown as Blob)).rejects.toThrow(/doesn't look like a zip/);
  });
});
