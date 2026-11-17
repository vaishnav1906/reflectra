import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BookOpen, Check, Loader2, MessageCircle, Pencil, Pin, PinOff, Plus, RotateCcw, Trash2 } from "lucide-react";
import { ErrorState, LoadingState, PageShell, Panel } from "@/components/portrait/PageShell";
import { LifeFact, LifeKind, formatDay, useLifeActions, useLifeMemory } from "@/hooks/useReflectra";
import { cn } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { learnNow } from "@/lib/learnNow";

/**
 * Your life: the lasting picture Reflectra keeps of you (what you do, what's going on,
 * what you're working toward), each fact in your own words. Edit, pin or remove any of it.
 */

const KIND_COLOR: Record<LifeKind, string> = {
  about: "hsl(var(--iris-violet))",
  situation: "hsl(var(--iris-peach))",
  goal: "hsl(var(--iris-cyan))",
  preference: "hsl(var(--trait-empathetic))",
  routine: "hsl(var(--trait-consistent))",
  place: "hsl(var(--muted-foreground))",
};

function FactRow({ fact, fresh = false }: { fact: LifeFact; fresh?: boolean }) {
  const navigate = useNavigate();
  const actions = useLifeActions();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(fact.text);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const active = fact.status === "active";

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save that.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className={cn("group flex gap-3 border-b border-white/5 py-4 first:pt-0 last:border-0 last:pb-0", !active && "opacity-60", fresh && "deal-in")}>
      <span className="mt-2 h-2 w-2 shrink-0 rounded-full" style={{ background: KIND_COLOR[fact.kind] }} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        {editing ? (
          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void run(async () => {
                await actions.edit(fact.id, { text });
                setEditing(false);
              });
            }}
          >
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={200}
              autoFocus
              className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-1.5 text-sm outline-none focus:border-iris-violet/60"
              aria-label="Edit this fact"
            />
            <button type="submit" className="trait-check-btn" disabled={busy || !text.trim()}>
              <Check className="h-3 w-3" /> Save
            </button>
          </form>
        ) : (
          <p className={cn("text-[15px] text-foreground/90", !active && "line-through decoration-white/30")}>
            {fact.pinned ? <Pin className="mr-1.5 inline h-3.5 w-3.5 -translate-y-px text-iris-cyan" aria-label="Pinned" /> : null}
            {fact.text}
          </p>
        )}
        {fact.quote ? <p className="mt-1 text-xs italic text-muted-foreground">“{fact.quote}”</p> : null}
        <p className="mt-1 flex flex-wrap items-center gap-x-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          {fact.source === "you" ? "you added" : `from your chats${fact.mention_count > 1 ? ` · ${fact.mention_count}×` : ""}`}
          {fact.last_seen ? <span>· last {formatDay(fact.last_seen)}</span> : null}
          {!active ? <span>· {fact.status === "resolved" ? "done" : "no longer true"}</span> : null}
          {fact.conversation_id ? (
            <button
              type="button"
              className="inline-flex items-center gap-1 normal-case tracking-normal text-primary hover:underline"
              onClick={() => navigate(`/app/chat?conversation_id=${fact.conversation_id}`)}
            >
              <MessageCircle className="h-3 w-3" /> open
            </button>
          ) : null}
        </p>
        {error ? <p className="mt-1 text-xs text-destructive">{error}</p> : null}
      </div>
      <div className="flex shrink-0 items-start gap-0.5 opacity-70 transition group-hover:opacity-100">
        {active ? (
          <>
            <button type="button" className="life-icon-btn" onClick={() => void run(() => actions.edit(fact.id, { pinned: !fact.pinned }))} disabled={busy}
              aria-label={fact.pinned ? "Unpin" : "Pin: always keep this in mind"} title={fact.pinned ? "Unpin" : "Pin: always keep this in mind"}>
              {fact.pinned ? <PinOff className="h-3.5 w-3.5" /> : <Pin className="h-3.5 w-3.5" />}
            </button>
            <button type="button" className="life-icon-btn" onClick={() => { setText(fact.text); setEditing((v) => !v); }} aria-label="Edit" title="Edit">
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button type="button" className="life-icon-btn" onClick={() => void run(() => actions.edit(fact.id, { status: fact.kind === "situation" || fact.kind === "goal" ? "resolved" : "outdated" }))}
              disabled={busy} aria-label="Not true any more" title={fact.kind === "situation" || fact.kind === "goal" ? "It's done / over" : "Not true any more"}>
              <Check className="h-3.5 w-3.5" />
            </button>
          </>
        ) : (
          <button type="button" className="life-icon-btn" onClick={() => void run(() => actions.edit(fact.id, { status: "active" }))} disabled={busy} aria-label="Still true" title="Still true">
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        )}
        <button type="button" className="life-icon-btn hover:!text-destructive" onClick={() => void run(() => actions.remove(fact.id))} disabled={busy} aria-label="Forget this" title="Forget this">
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </li>
  );
}

export function LifePage() {
  const { data, isLoading, error, refetch } = useLifeMemory();
  const actions = useLifeActions();
  const [kind, setKind] = useState<LifeKind>("about");
  const [text, setText] = useState("");
  const [adding, setAdding] = useState(false);
  const [showPast, setShowPast] = useState(false);
  const [readError, setReadError] = useState<string | null>(null);
  // Facts that were already here when you arrived; the rest are dealt in as they're found.
  const known = useRef<Set<string> | null>(null);
  if (known.current === null && data) known.current = new Set(data.facts.map((f) => f.id));
  const found = data && known.current ? data.facts.filter((f) => !known.current!.has(f.id) && f.source !== "you").length : 0;
  const reading = Boolean(data?.reading_history);
  const wasReading = useRef(false);
  const [finished, setFinished] = useState<string | null>(null);
  useEffect(() => {
    if (wasReading.current && !reading) {
      setFinished(found ? `Done. Found ${found} new ${found === 1 ? "thing" : "things"} in your past chats.` : "Done. Nothing new to add from your past chats.");
    }
    if (reading) setFinished(null);
    wasReading.current = reading;
  }, [reading, found]);
  // Reading past chats is a chain of background jobs: keep them moving while it's on.
  useEffect(() => {
    if (!reading) return;
    learnNow();
    const timer = window.setInterval(learnNow, 15000);
    return () => window.clearInterval(timer);
  }, [reading]);

  if (isLoading) return <LoadingState label="Remembering…" />;
  if (error || !data) return <ErrorState message={error instanceof Error ? error.message : "Couldn't load this."} onRetry={() => void refetch()} />;

  const active = data.facts.filter((f) => f.status === "active");
  const past = data.facts.filter((f) => f.status !== "active");

  return (
    <PageShell
      eyebrow="Your life"
      title="What Reflectra"
      accent="knows about you."
      subtitle="The lasting things you've told it: what you do, what's going on, what you're working toward. Each one in your own words. Fix anything that's off."
      actions={
        <button
          type="button"
          className="btn-ghost-glass !py-2.5"
          disabled={data.reading_history}
          onClick={async () => {
            setReadError(null);
            try {
              await actions.readHistory();
            } catch (err) {
              setReadError(err instanceof Error ? err.message : "Couldn't start that.");
            }
          }}
        >
          {data.reading_history ? <Loader2 className="h-4 w-4 animate-spin" /> : <BookOpen className="h-4 w-4" />}
          {data.reading_history ? "Reading your past chats…" : "Read my past chats"}
        </button>
      }
    >
      {readError ? <p className="text-sm text-destructive">{readError}</p> : null}

      {reading ? (
        <Panel className="iris-border">
          <div className="flex flex-col items-center gap-5 py-4 sm:flex-row sm:gap-8">
            {/* A beam of light passes over the outline of your old messages. */}
            <div className="history-scan" aria-hidden="true">
              {[72, 48, 86, 34, 64, 90, 40, 58].map((width, i) => (
                <span key={i} className={cn("history-scan-line", i % 2 && "is-you")} style={{ width: `${width}%` }} />
              ))}
              <span className="history-scan-beam" />
            </div>
            <div role="status" aria-live="polite">
              <p className="font-display text-2xl">Reading your past chats…</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {found ? (
                  <>
                    Found <span className="tabular-nums text-foreground">{found}</span> new {found === 1 ? "thing" : "things"} so far.
                  </>
                ) : (
                  "Looking for the lasting things: what you do, what's going on, what you're working toward."
                )}
              </p>
            </div>
          </div>
        </Panel>
      ) : finished ? (
        <p className="fade-in text-sm text-muted-foreground" role="status">{finished}</p>
      ) : null}

      <Panel title="What your replies see right now" hint="the few most relevant, pinned first" className="iris-border">
        {data.in_replies.length ? (
          <ul className="grid gap-2 sm:grid-cols-2">
            {data.in_replies.map((line) => (
              <li key={line} className="rounded-xl border border-white/8 bg-white/[0.02] px-3 py-2 text-sm text-foreground/85">
                {line}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            Nothing yet. It fills in as you chat, or tap “Read my past chats” to build it from what you&apos;ve already said.
          </p>
        )}
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        {data.kinds.map(({ kind: k, label }) => {
          const facts = active.filter((f) => f.kind === k);
          if (!facts.length) return null;
          return (
            <Panel key={k} title={label}>
              <ul>
                {facts.map((f) => (
                  <FactRow key={f.id} fact={f} fresh={Boolean(known.current && !known.current.has(f.id))} />
                ))}
              </ul>
            </Panel>
          );
        })}
      </div>

      <Panel title="Add something">
        <form
          className="flex flex-col gap-3 sm:flex-row"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!text.trim()) return;
            setAdding(true);
            try {
              await actions.add(kind, text.trim());
              setText("");
            } finally {
              setAdding(false);
            }
          }}
        >
          {/* The app's own menu: the browser's built-in one ignores the dark theme on Windows. */}
          <Select value={kind} onValueChange={(value) => setKind(value as LifeKind)}>
            <SelectTrigger className="h-auto rounded-xl border-white/10 bg-white/[0.03] px-3 py-2 text-sm sm:w-[190px]" aria-label="What kind of thing">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="border-white/10 bg-popover text-popover-foreground">
              {data.kinds.map(({ kind: k, label }) => (
                <SelectItem key={k} value={k} className="focus:bg-white/[0.08] focus:text-foreground">
                  <span className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: KIND_COLOR[k] }} aria-hidden="true" />
                    {label}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={200}
            placeholder="e.g. Final-year engineering student in Pune"
            className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm outline-none focus:border-iris-violet/60"
            aria-label="Something about your life"
          />
          <button type="submit" className="btn-mirror !py-2 disabled:opacity-40" disabled={adding || !text.trim()}>
            {adding ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Add
          </button>
        </form>
      </Panel>

      {past.length ? (
        <section>
          <button type="button" onClick={() => setShowPast((v) => !v)} aria-expanded={showPast} className="text-sm text-muted-foreground hover:text-foreground">
            {showPast ? "Hide" : "Show"} things that are over or no longer true ({past.length})
          </button>
          {showPast ? (
            <Panel className="mt-4">
              <ul>
                {past.map((f) => (
                  <FactRow key={f.id} fact={f} />
                ))}
              </ul>
            </Panel>
          ) : null}
        </section>
      ) : null}
    </PageShell>
  );
}
