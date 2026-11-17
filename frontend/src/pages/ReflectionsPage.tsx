import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { ErrorState, LoadingState, PageShell, Panel } from "@/components/portrait/PageShell";
import { LooseEnds } from "@/components/portrait/LooseEnds";
import { Reflection, formatDay, useGenerateReflections, useReflections } from "@/hooks/useReflectra";
import { cn } from "@/lib/utils";

/**
 * Reflections: patterns across your conversations, each one backed by things you
 * actually said on at least two separate occasions. Quotes link to their conversation.
 */

const THEME_COLOR: Record<string, string> = {
  work: "hsl(var(--iris-cyan))",
  habits: "hsl(var(--iris-violet))",
  relationships: "hsl(var(--trait-empathetic))",
  "self-image": "hsl(var(--iris-peach))",
  emotions: "hsl(var(--trait-empathetic))",
  health: "hsl(var(--trait-consistent))",
  decisions: "hsl(var(--iris-violet))",
  growth: "hsl(var(--trait-consistent))",
  other: "hsl(var(--muted-foreground))",
};

function ReflectionCard({ reflection, index, muted = false }: { reflection: Reflection; index: number; muted?: boolean }) {
  const navigate = useNavigate();
  const color = THEME_COLOR[reflection.theme] || THEME_COLOR.other;
  const days = new Set(reflection.evidence.map((e) => e.date).filter(Boolean)).size;

  return (
    <article className={cn("glass-panel fade-in rounded-3xl p-6 md:p-8", !muted && "iris-border", muted && "opacity-75")} style={{ animationDelay: `${index * 90}ms` }}>
      <div className="flex flex-wrap items-center gap-3">
        <span className="rounded-full px-3 py-1 font-mono text-[10px] uppercase tracking-widest" style={{ color, background: `color-mix(in srgb, ${color} 12%, transparent)` }}>
          {reflection.theme}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          said on {days || 1} {days === 1 ? "day" : "different days"}
          {reflection.confidence ? ` · ${Math.round(reflection.confidence * 100)}% sure` : ""}
        </span>
      </div>

      <h2 className="mt-4 font-display text-[clamp(1.6rem,3vw,2.2rem)] leading-[1.1] text-balance">{reflection.title}</h2>
      <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-foreground/80">{reflection.insight}</p>

      <div className="mt-6 space-y-3">
        <p className="eyebrow !text-[0.62rem]">In your words</p>
        {reflection.evidence.map((evidence, i) => {
          const body = (
            <>
              <span className="block text-[15px] italic leading-relaxed text-foreground/85">“{evidence.quote}”</span>
              <span className="mt-1 block font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                {formatDay(evidence.date)}
                {evidence.conversation_id ? " · open conversation" : ""}
              </span>
            </>
          );
          return evidence.conversation_id ? (
            <button
              key={i}
              type="button"
              onClick={() => navigate(`/app/chat?conversation_id=${evidence.conversation_id}`)}
              className="block w-full border-l border-iris-peach/60 pl-4 text-left transition-colors hover:border-iris-peach"
            >
              {body}
            </button>
          ) : (
            <div key={i} className="border-l border-iris-peach/60 pl-4">
              {body}
            </div>
          );
        })}
      </div>
    </article>
  );
}

export function ReflectionsPage() {
  const { data, isLoading, error, refetch } = useReflections();
  const generate = useGenerateReflections();
  const [showEarlier, setShowEarlier] = useState(false);
  const autoStarted = useRef(false);

  // First visit with enough conversation and nothing written yet: write them once.
  const status = data?.status;
  useEffect(() => {
    if (!status || autoStarted.current) return;
    if (!status.generated_at && status.can_generate) {
      autoStarted.current = true;
      generate.mutate(false);
    }
  }, [status, generate]);

  if (isLoading) return <LoadingState label="Opening your reflections…" />;
  if (error || !data || !status) return <ErrorState message={error instanceof Error ? error.message : "Couldn't load your reflections."} onRetry={() => void refetch()} />;

  const working = generate.isPending;
  const hasAny = data.reflections.length > 0;
  const canRefresh = status.can_generate && status.new_messages_since > 0;
  // "Read again" re-reads the same messages; allowed whenever reflecting is possible at all.
  const canRetry = hasAny && status.pattern_tracking && !working;

  return (
    <PageShell
      eyebrow="Reflections"
      title="What keeps"
      accent="coming up."
      subtitle="Patterns Reflectra has noticed across your conversations. Each one has to show up at least twice, in your own words, or it doesn't make the page."
      actions={
        hasAny ? (
          <button
            type="button"
            className={cn(canRefresh ? "btn-mirror" : "btn-ghost-glass", "!py-2.5 disabled:cursor-not-allowed disabled:opacity-50")}
            disabled={working || !(canRefresh || canRetry)}
            onClick={() => generate.mutate(!canRefresh)}
          >
            {working ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {working ? "Reading…" : canRefresh ? `Reflect on ${status.new_messages_since} new` : "Read again"}
          </button>
        ) : null
      }
    >
      <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
        {status.generated_at
          ? `Written ${formatDay(status.generated_at)} from your last ${status.messages_read} messages · ${status.new_messages_since} new since`
          : `${status.messages_available} messages available to read`}
      </p>

      {generate.isError ? (
        <Panel className="border-destructive/30">
          <p className="text-sm text-destructive">{generate.error instanceof Error ? generate.error.message : "Couldn't write reflections right now."}</p>
        </Panel>
      ) : null}

      {working && !hasAny ? (
        <Panel className="iris-border">
          <div className="flex flex-col items-center gap-4 py-14 text-center">
            <Sparkles className="h-6 w-6 animate-pulse text-iris-violet" />
            <p className="font-display text-2xl">Reading back through what you&apos;ve said…</p>
            <p className="max-w-sm text-sm text-muted-foreground">This takes around ten seconds. It only keeps patterns it can back with your own quotes.</p>
          </div>
        </Panel>
      ) : null}

      {!working && !hasAny ? (
        <Panel className="iris-border">
          <div className="flex flex-col items-center gap-4 py-14 text-center">
            <p className="font-display text-3xl">Nothing here yet.</p>
            <p className="max-w-md text-sm leading-relaxed text-muted-foreground">
              {status.reason || "Reflectra can read your recent conversations and write down what it notices."}
            </p>
            {status.can_generate ? (
              <button type="button" className="btn-mirror" onClick={() => generate.mutate(false)}>
                <Sparkles className="h-4 w-4" /> Write my reflections
              </button>
            ) : null}
          </div>
        </Panel>
      ) : null}

      {data.reflections.map((reflection, index) => (
        <ReflectionCard key={reflection.id} reflection={reflection} index={index} />
      ))}

      <LooseEnds />

      {data.earlier.length ? (
        <section>
          <button
            type="button"
            onClick={() => setShowEarlier((open) => !open)}
            aria-expanded={showEarlier}
            className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ChevronDown className={cn("h-4 w-4 transition-transform", showEarlier && "rotate-180")} />
            Earlier reflections ({data.earlier.length})
          </button>
          {showEarlier ? (
            <div className="mt-6 space-y-6">
              {data.earlier.map((reflection, index) => (
                <ReflectionCard key={reflection.id} reflection={reflection} index={index} muted />
              ))}
            </div>
          ) : null}
        </section>
      ) : null}
    </PageShell>
  );
}
