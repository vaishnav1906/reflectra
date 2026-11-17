/**
 * Just enough of ZIP to pull one text file out of a chat export, in the browser.
 *
 * WhatsApp on iPhone exports "_chat.txt" inside a .zip, ChatGPT exports
 * "conversations.json" inside a .zip and Telegram writes "result.json". Reading it
 * here means the archive (photos, voice notes) never leaves the device: only the
 * chat text is sent on.
 */

const EOCD = 0x06054b50;
const CENTRAL = 0x02014b50;
const LOCAL = 0x04034b50;

const PREFERRED = [/(^|\/)_chat\.txt$/i, /(^|\/)conversations\.json$/i, /(^|\/)result\.json$/i, /\.txt$/i, /\.json$/i];

type Entry = { name: string; method: number; compressedSize: number; localOffset: number };

function entries(view: DataView, bytes: Uint8Array): Entry[] {
  let eocd = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 65557); i--) {
    if (view.getUint32(i, true) === EOCD) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error("That doesn't look like a zip file.");
  const count = view.getUint16(eocd + 10, true);
  let offset = view.getUint32(eocd + 16, true);
  const decoder = new TextDecoder();
  const found: Entry[] = [];
  for (let i = 0; i < count && view.getUint32(offset, true) === CENTRAL; i++) {
    const method = view.getUint16(offset + 10, true);
    const compressedSize = view.getUint32(offset + 20, true);
    const nameLength = view.getUint16(offset + 28, true);
    const extraLength = view.getUint16(offset + 30, true);
    const commentLength = view.getUint16(offset + 32, true);
    const localOffset = view.getUint32(offset + 42, true);
    const name = decoder.decode(bytes.subarray(offset + 46, offset + 46 + nameLength));
    found.push({ name, method, compressedSize, localOffset });
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return found;
}

async function inflate(data: Uint8Array): Promise<Uint8Array> {
  if (typeof DecompressionStream === "undefined") {
    throw new Error("This browser can't open zip files. Unzip it first and upload the .txt or .json inside.");
  }
  const source = new ReadableStream<BufferSource>({
    start(controller) {
      controller.enqueue(data.slice());  // a copy, so its buffer is a plain ArrayBuffer
      controller.close();
    },
  });
  const stream = source.pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/** The chat text inside a zip export, and the name of the file it came from. */
export async function readChatFromZip(file: Blob): Promise<{ name: string; text: string }> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const all = entries(view, bytes).filter((e) => !e.name.endsWith("/") && !/(^|\/)__MACOSX\//.test(e.name));
  const pick = PREFERRED.map((pattern) => all.find((e) => pattern.test(e.name))).find(Boolean);
  if (!pick) throw new Error("No chat text in that zip. Look for a _chat.txt or conversations.json inside it.");

  const local = pick.localOffset;
  if (view.getUint32(local, true) !== LOCAL) throw new Error("That zip file seems damaged.");
  const start = local + 30 + view.getUint16(local + 26, true) + view.getUint16(local + 28, true);
  const raw = bytes.subarray(start, start + pick.compressedSize);
  const content = pick.method === 0 ? raw : pick.method === 8 ? await inflate(raw) : null;
  if (!content) throw new Error("That zip uses a compression this page can't read. Unzip it first.");
  return { name: pick.name.split("/").pop() || pick.name, text: new TextDecoder().decode(content) };
}

export function isZip(file: File) {
  return /\.zip$/i.test(file.name) || file.type === "application/zip" || file.type === "application/x-zip-compressed";
}
