import { apiFetch } from "@/lib/api";

/**
 * POST /chat/stream and read its server-sent events.
 *
 *   partial  the reply so far (replaces what is shown)
 *   reset    that draft was rejected; show "typing" again
 *   done     the final reply and everything /chat returns
 *   error    { status, detail }
 *
 * If the stream endpoint can't be used at all (an older backend, a proxy that
 * buffers), it falls back to plain POST /chat so sending always works.
 */

export interface ChatResult {
  reply: string;
  conversation_id?: string;
  title?: string;
  mode?: string;
  mirror_active?: boolean;
  assistant_task_type?: string | null;
  active_mirror_style?: string | null;
  detected_emotion?: string | null;
  message_id?: string | null;
  people_used?: { id: string; name: string }[];
  remembered?: { said: string; when: string; conversation_id: string }[];
  [key: string]: unknown;
}

export class ChatError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

interface Handlers {
  onPartial: (text: string) => void;
  onReset: () => void;
}

async function plainChat(payload: object): Promise<ChatResult> {
  const res = await apiFetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ChatError(res.status, typeof body?.detail === "string" ? body.detail : `HTTP ${res.status}`);
  if (typeof body?.reply !== "string") throw new ChatError(500, "Invalid chat response payload");
  return body as ChatResult;
}

export async function sendChat(payload: object, handlers: Handlers): Promise<ChatResult> {
  let res: Response;
  try {
    res = await apiFetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(payload),
    });
  } catch {
    return plainChat(payload);
  }

  const isStream = (res.headers.get("content-type") || "").includes("text/event-stream");
  if (res.status === 404 || res.status === 405 || (res.ok && !isStream) || !res.body) {
    return plainChat(payload);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ChatError(res.status, typeof body?.detail === "string" ? body.detail : `HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: ChatResult | null = null;

  const handle = (raw: string) => {
    const data = raw
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!data) return;
    let event: Record<string, unknown>;
    try {
      event = JSON.parse(data);
    } catch {
      return;
    }
    if (event.type === "partial" && typeof event.text === "string") handlers.onPartial(event.text);
    else if (event.type === "reset") handlers.onReset();
    else if (event.type === "done") {
      const { type: _type, ...rest } = event;
      result = rest as ChatResult;
    } else if (event.type === "error") {
      throw new ChatError(Number(event.status) || 500, String(event.detail || "Something went wrong."));
    }
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (value) buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      handle(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
    if (done) break;
  }
  if (buffer.trim()) handle(buffer);

  if (!result || typeof (result as ChatResult).reply !== "string") {
    throw new ChatError(500, "The reply was cut off. Send it again.");
  }
  return result;
}
