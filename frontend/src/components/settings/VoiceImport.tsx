import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, FileUp, Loader2, MessageCircle, ShieldCheck, Trash2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch } from "@/lib/api";
import { isZip, readChatFromZip } from "@/lib/unzip";
import { formatDay } from "@/hooks/useReflectra";
import { cn } from "@/lib/utils";

/**
 * "Teach Mirror how you text": import a chat export so Mirror sounds like you from
 * day one. The server keeps only the chosen person's messages (with links, e-mails
 * and phone numbers stripped); everyone else's are read to find message boundaries
 * and thrown away. Zip exports are opened here, so photos and voice notes never
 * leave the device.
 */

const MAX_CHARS = 3_000_000;
const FORMAT_LABEL: Record<string, string> = {
  whatsapp: "a WhatsApp chat",
  telegram: "a Telegram chat",
  chatgpt: "your ChatGPT history",
  lines: "pasted messages",
};

type Preview = {
  format: string;
  senders: { name: string; messages: number }[];
  sender: string | null;
  needs_sender: boolean;
  samples?: number;
  description?: string;
  avg_words?: number;
  lowercase_share?: number;
  emoji_share?: number;
  examples?: string[];
  saved: boolean;
};

type Current = { samples: number; format: string | null; description: string | null; imported_at: string | null } | null;

async function detail(res: Response, fallback: string) {
  const body = await res.json().catch(() => ({}));
  return typeof body?.detail === "string" ? body.detail : fallback;
}

/**
 * Keep uploads small. JSON exports are cut down to just the user's own messages in
 * the browser (they can be tens of megabytes); text is trimmed to its most recent part.
 */
function shrink(text: string): string {
  if (text.length <= MAX_CHARS) return text;
  const trimmed = text.trimStart();
  if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
    try {
      const data = JSON.parse(trimmed);
      if (Array.isArray(data)) {
        const mine: { message: { author: { role: string }; create_time: number; content: { parts: string[] } } }[] = [];
        for (const conversation of data) {
          for (const node of Object.values(conversation?.mapping ?? {}) as { message?: { author?: { role?: string }; create_time?: number; content?: { parts?: unknown[] } } }[]) {
            const message = node?.message;
            if (message?.author?.role !== "user") continue;
            const parts = (message.content?.parts ?? []).filter((p): p is string => typeof p === "string");
            if (parts.length) mine.push({ message: { author: { role: "user" }, create_time: message.create_time ?? 0, content: { parts } } });
          }
        }
        mine.sort((a, b) => a.message.create_time - b.message.create_time);
        const kept = Object.fromEntries(mine.slice(-4000).map((node, i) => [String(i), node]));
        return JSON.stringify([{ mapping: kept }]);
      }
      if (Array.isArray(data?.messages)) {
        const messages = data.messages
          .filter((m: { type?: string; from?: string }) => (m.type ?? "message") === "message" && m.from)
          .slice(-8000)
          .map((m: { from: string; text: unknown }) => ({ type: "message", from: m.from, text: m.text }));
        return JSON.stringify({ messages });
      }
    } catch {
      /* fall through to trimming */
    }
  }
  const tail = text.slice(-MAX_CHARS);
  return tail.slice(tail.indexOf("\n") + 1);
}

export function VoiceImportRow({ Row }: { Row: (props: { title: string; body: string; control: React.ReactNode }) => JSX.Element }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const current = useQuery({
    queryKey: ["voice-import"],
    queryFn: async () => {
      const res = await apiFetch("/api/persona/voice-import");
      if (!res.ok) throw new Error(await detail(res, "Couldn't check your import."));
      return ((await res.json()) as { imported: Current }).imported;
    },
  });
  const remove = useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/api/persona/voice-import", { method: "DELETE" });
      if (!res.ok) throw new Error(await detail(res, "Couldn't remove it."));
    },
    onSuccess: () => {
      queryClient.setQueryData(["voice-import"], null);
      void queryClient.invalidateQueries({ queryKey: ["system"] });
      toast.success("Imported texts removed. Mirror now learns only from your chats here.");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Couldn't remove it."),
  });

  const imported = current.data;
  return (
    <>
      <Row
        title="Teach Mirror how you text"
        body={
          imported
            ? `Mirror is also copying ${imported.samples} of your own messages from ${FORMAT_LABEL[imported.format ?? ""] ?? "an import"}${
                imported.imported_at ? `, added ${formatDay(imported.imported_at)}` : ""
              }. ${imported.description ?? ""}`
            : "Import a WhatsApp, Telegram or ChatGPT export and Mirror sounds like you from day one. Only your own messages are kept."
        }
        control={
          <div className="flex items-center gap-2">
            <button type="button" className="btn-ghost-glass !px-4 !py-2" onClick={() => setOpen(true)} aria-label={imported ? "Replace your imported chat" : "Import your own chats"}>
              <MessageCircle className="h-4 w-4" /> {imported ? "Replace" : "Import"}
            </button>
            {imported ? (
              <button
                type="button"
                className="rounded-full p-2 text-muted-foreground transition-colors hover:bg-white/5 hover:text-destructive"
                onClick={() => remove.mutate()}
                disabled={remove.isPending}
                aria-label="Remove imported texts"
                title="Remove imported texts"
              >
                {remove.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              </button>
            ) : null}
          </div>
        }
      />
      {open ? <VoiceImportDialog onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function VoiceImportDialog({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [pasting, setPasting] = useState(false);
  const [reading, setReading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [sender, setSender] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const send = async (body: { text: string; sender: string | null; dry_run: boolean }) => {
    const res = await apiFetch("/api/persona/voice-import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await detail(res, "Couldn't read that."));
    return (await res.json()) as Preview;
  };

  const read = async (content: string, chosen: string | null = null) => {
    setError(null);
    setReading(true);
    try {
      const result = await send({ text: content, sender: chosen, dry_run: true });
      setPreview(result);
      setSender(result.sender);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't read that.");
    } finally {
      setReading(false);
    }
  };

  const pickFile = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    setPreview(null);
    try {
      const { name, text: content } = isZip(file) ? await readChatFromZip(file) : { name: file.name, text: await file.text() };
      const small = shrink(content);
      setFileName(name);
      setText(small);
      await read(small);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't open that file.");
    }
  };

  const save = async () => {
    if (!sender) return;
    setSaving(true);
    setError(null);
    try {
      const result = await send({ text, sender, dry_run: false });
      queryClient.setQueryData(["voice-import"], {
        samples: result.samples ?? 0,
        format: result.format,
        description: result.description ?? null,
        imported_at: new Date().toISOString(),
      });
      void queryClient.invalidateQueries({ queryKey: ["system"] });
      toast.success(`Mirror now has ${result.samples} of your messages to learn your voice from.`);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save that.");
    } finally {
      setSaving(false);
    }
  };

  const others = preview ? preview.senders.filter((s) => s.name !== sender) : [];
  const ready = preview && !preview.needs_sender && preview.samples;

  return (
    <Dialog open onOpenChange={(next) => (!next && !saving ? onClose() : undefined)}>
      <DialogContent className="max-h-[90vh] overflow-y-auto border-white/10 bg-popover sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-display text-3xl font-normal">
            {ready ? "Here's how you text" : preview?.needs_sender ? "Which one is you?" : "Teach Mirror how you text"}
          </DialogTitle>
          <DialogDescription>
            {ready
              ? "Nothing is saved yet. This is what Mirror will learn from."
              : preview?.needs_sender
                ? "Pick your name. Only that person's messages are kept."
                : "A chat you've had with a friend shows your real voice better than anything you could describe."}
          </DialogDescription>
        </DialogHeader>

        {!preview ? (
          <div className="space-y-4">
            {!pasting ? (
              <>
                <button
                  type="button"
                  onClick={() => fileRef.current?.click()}
                  onDragOver={(event) => {
                    event.preventDefault();
                    setDragging(true);
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(event) => {
                    event.preventDefault();
                    setDragging(false);
                    void pickFile(event.dataTransfer.files?.[0]);
                  }}
                  disabled={reading}
                  className={cn(
                    "flex w-full flex-col items-center gap-3 rounded-3xl border border-dashed px-6 py-10 text-center transition-colors",
                    dragging ? "border-iris-cyan bg-white/[0.06]" : "border-white/15 bg-white/[0.02] hover:bg-white/[0.05]",
                  )}
                >
                  {reading ? <Loader2 className="h-7 w-7 animate-spin text-iris-violet" /> : <FileUp className="h-7 w-7 text-iris-violet" />}
                  <span className="font-medium text-foreground">{reading ? `Reading ${fileName ?? "it"}…` : "Drop a chat export here, or click to choose"}</span>
                  <span className="text-xs text-muted-foreground">WhatsApp .txt or .zip · Telegram result.json · ChatGPT conversations.json or .zip</span>
                </button>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".txt,.json,.zip,text/plain,application/json,application/zip"
                  className="hidden"
                  onChange={(event) => void pickFile(event.target.files?.[0])}
                />
                <div className="grid gap-3 text-xs leading-relaxed text-muted-foreground sm:grid-cols-3">
                  <p>
                    <span className="text-foreground">WhatsApp:</span> open a chat · ⋮ or the name · Export chat · Without media
                  </p>
                  <p>
                    <span className="text-foreground">ChatGPT:</span> Settings · Data controls · Export data, then upload the zip it emails you
                  </p>
                  <p>
                    <span className="text-foreground">Telegram:</span> Desktop app · Settings · Advanced · Export Telegram data · JSON
                  </p>
                </div>
                <button type="button" className="text-sm text-primary hover:underline" onClick={() => setPasting(true)}>
                  Or paste some of your own messages instead
                </button>
              </>
            ) : (
              <>
                <Textarea
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder={"One message per line, written by you:\nbro i overslept again\nngl that was kinda fire\n…"}
                  className="min-h-[220px] border-white/10 bg-white/[0.03]"
                  aria-label="Your messages"
                  disabled={reading}
                />
                <div className="flex items-center justify-between gap-3">
                  <button type="button" className="text-sm text-muted-foreground hover:text-foreground" onClick={() => setPasting(false)}>
                    Upload a file instead
                  </button>
                  <button type="button" className="btn-mirror disabled:opacity-50" disabled={!text.trim() || reading} onClick={() => void read(shrink(text))}>
                    {reading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    {reading ? "Reading…" : "Read it"}
                  </button>
                </div>
              </>
            )}
          </div>
        ) : preview.needs_sender ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Which sender is you">
              {preview.senders.map((s) => (
                <button
                  key={s.name}
                  type="button"
                  role="radio"
                  aria-checked={sender === s.name}
                  onClick={() => void read(text, s.name)}
                  disabled={reading}
                  className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm transition-colors hover:border-white/25 hover:bg-white/[0.07]"
                >
                  {s.name} <span className="font-mono text-xs text-muted-foreground">{s.messages}</span>
                </button>
              ))}
            </div>
            {reading ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Reading their messages…
              </p>
            ) : null}
          </div>
        ) : (
          <div className="space-y-5">
            <div className="grid grid-cols-3 gap-3">
              {[
                { value: preview.samples ?? 0, label: "of your messages" },
                { value: preview.avg_words ?? "–", label: "words in a typical one" },
                { value: `${Math.round((preview.lowercase_share ?? 0) * 100)}%`, label: "all lowercase" },
              ].map((stat) => (
                <div key={stat.label} className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                  <p className="font-display text-3xl text-foreground">{stat.value}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{stat.label}</p>
                </div>
              ))}
            </div>
            {preview.description ? (
              <p className="text-sm text-foreground/85">{preview.description.charAt(0).toUpperCase() + preview.description.slice(1)}</p>
            ) : null}
            {preview.examples?.length ? (
              <div className="space-y-2">
                <p className="eyebrow !text-[0.62rem]">Lines Mirror will copy the feel of</p>
                {preview.examples.map((example) => (
                  <p key={example} className="border-l border-iris-peach/60 pl-3 text-sm italic text-muted-foreground">
                    “{example}”
                  </p>
                ))}
              </div>
            ) : null}
            <div className="flex gap-3 rounded-2xl border border-white/10 bg-white/[0.02] p-4">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-iris-cyan" />
              <p className="text-xs leading-relaxed text-muted-foreground">
                Only {sender === "You" ? "your" : `${sender}'s`} messages are kept.
                {others.length
                  ? ` ${others.length === 1 ? `${others[0].name}'s ${others[0].messages}` : `The other ${others.length} people's`} messages were only read to tell the messages apart and are thrown away.`
                  : ""}{" "}
                Links, e-mail addresses and phone numbers are removed. Erase in Settings deletes these too.
              </p>
            </div>
            <div className="flex items-center justify-between gap-3">
              <button
                type="button"
                className="btn-ghost-glass"
                onClick={() => {
                  setPreview(null);
                  setSender(null);
                }}
                disabled={saving}
              >
                Back
              </button>
              <button type="button" className="btn-mirror disabled:opacity-50" onClick={() => void save()} disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                {saving ? "Saving…" : `Use these ${preview.samples}`}
              </button>
            </div>
          </div>
        )}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </DialogContent>
    </Dialog>
  );
}
