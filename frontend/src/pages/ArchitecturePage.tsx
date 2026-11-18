import { ReactNode, useMemo, useRef, useState } from "react";
import { useScrollLight } from "@/hooks/useScrollLight";
import { ErrorState, LoadingState, PageShell, Panel, Stat } from "@/components/portrait/PageShell";
import { SystemFacts, TRAIT_COLOR, TRAIT_LABEL, useSystemFacts } from "@/hooks/useReflectra";
import { cn } from "@/lib/utils";

/**
 * How it works: the path one message takes through Reflectra.
 * The rules shown are read from the backend's own constants, and the "you" figures
 * are this account's live numbers, so nothing on this page is a marketing claim.
 */

const SOURCE_LABEL: Record<string, string> = {
  traits: "How settled your traits are",
  conversations: "How much you've said, over how many days",
  voice: "How much of your writing it has",
  reflections: "Patterns backed by your own quotes",
};

const TIER_LABEL: Record<string, string> = {
  very_low: "Barely knows you",
  partial: "Getting there",
  moderate: "Knows you",
  high: "Knows you well",
};

function Station({ step, title, children, aside }: { step: string; title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="relative pl-10 md:pl-14" data-thread-stop data-step={step}>
      <span className="station-badge absolute left-0 top-1 flex h-7 w-7 items-center justify-center rounded-full border border-white/15 bg-background font-mono text-[10px] text-iris-cyan md:h-9 md:w-9 md:text-xs">
        {step}
      </span>
      <div className={cn("grid gap-6", aside ? "lg:grid-cols-[1.05fr_0.95fr]" : "")}>
        <div>
          <h2 className="font-display text-[clamp(1.7rem,3vw,2.3rem)] leading-tight">{title}</h2>
          <div className="mt-3 space-y-3 text-[15px] leading-relaxed text-foreground/75">{children}</div>
        </div>
        {aside}
      </div>
    </section>
  );
}

function Fact({ value, label }: { value: ReactNode; label: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-white/5 py-2.5 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="shrink-0 font-mono text-sm text-foreground">{value}</span>
    </div>
  );
}

/** Runs the real update rule in the browser so the "it learns slowly" claim can be tried. */
function LearningSimulator({ rules }: { rules: SystemFacts["rules"]["traits"] }) {
  const [signal, setSignal] = useState(85);
  const [strength, setStrength] = useState(15);
  const [count, setCount] = useState(30);

  const path = useMemo(() => {
    let score = 0.5;
    let confidence = 0.1;
    const points = [{ score, confidence }];
    const s = signal / 100;
    const k = Math.min(strength / 100, rules.max_step_per_message);
    for (let i = 0; i < count; i++) {
      const distance = Math.abs(s - score);
      const alpha = k * (1 - rules.inertia * confidence);
      score = Math.max(0, Math.min(1, score + alpha * (s - score)));
      if (distance <= rules.agree_within) confidence += rules.confidence_gain * k * (1 - confidence);
      else if (distance >= rules.conflict_beyond) confidence -= rules.confidence_loss * k * confidence;
      confidence = Math.max(rules.confidence_floor, Math.min(rules.confidence_ceiling, confidence));
      points.push({ score, confidence });
    }
    return points;
  }, [signal, strength, count, rules]);

  const width = 520;
  const height = 150;
  const line = (key: "score" | "confidence") =>
    path.map((p, i) => `${i ? "L" : "M"} ${((i / Math.max(path.length - 1, 1)) * width).toFixed(1)} ${(height - p[key] * height).toFixed(1)}`).join(" ");
  const last = path[path.length - 1];
  const first = path[1] ?? last;

  return (
    <Panel title="Try it" hint="this runs the same rule the server uses">
      <div className="space-y-4">
        {[
          { label: "What your messages show", value: signal, set: setSignal, min: 0, max: 100, suffix: "/100" },
          { label: "How clear each message is", value: strength, set: setStrength, min: 2, max: Math.round(rules.max_step_per_message * 100), suffix: "%" },
          { label: "Messages sent", value: count, set: setCount, min: 1, max: 80, suffix: "" },
        ].map((control) => (
          <label key={control.label} className="block">
            <span className="flex justify-between text-xs text-muted-foreground">
              {control.label}
              <span className="font-mono text-foreground">
                {control.value}
                {control.suffix}
              </span>
            </span>
            <input
              type="range"
              min={control.min}
              max={control.max}
              value={control.value}
              onChange={(event) => control.set(Number(event.target.value))}
              className="mt-2 w-full accent-[hsl(var(--iris-violet))]"
            />
          </label>
        ))}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="mt-5 w-full" role="img" aria-label={`After ${count} messages the score is ${Math.round(last.score * 100)} and confidence is ${Math.round(last.confidence * 100)} percent`}>
        <line x1="0" x2={width} y1={height / 2} y2={height / 2} stroke="hsl(0 0% 100% / 0.08)" strokeDasharray="3 5" />
        <path d={line("confidence")} fill="none" stroke="hsl(var(--iris-peach))" strokeWidth="2" strokeDasharray="4 4" />
        <path d={line("score")} fill="none" stroke="hsl(var(--iris-violet))" strokeWidth="2.5" />
      </svg>
      <div className="mt-4 grid grid-cols-3 gap-4">
        <Stat value={Math.round(first.score * 100)} label="score after 1 message (starts at 50)" />
        <Stat value={Math.round(last.score * 100)} label={`score after ${count}`} />
        <Stat value={`${Math.round(last.confidence * 100)}%`} label="how sure it is by then" />
      </div>
    </Panel>
  );
}

/** "7 of 9 (78%)" from your own ratings, or a note that there are none yet. */
function rated(yes = 0, no = 0) {
  const total = yes + no;
  return total ? `${yes} of ${total} (${Math.round((yes / total) * 100)}%)` : "not rated yet";
}

export function ArchitecturePage() {
  const { data, isLoading, error, refetch } = useSystemFacts();
  // A dot of light travels down the steps as you scroll, filling each step's ring.
  const steps = useRef<HTMLDivElement>(null);
  useScrollLight(steps, [Boolean(data)], { fill: ".station-badge" });

  if (isLoading) return <LoadingState label="Opening the hood…" />;
  if (error || !data) return <ErrorState message={error instanceof Error ? error.message : "Couldn't load this page."} onRetry={() => void refetch()} />;

  const { rules, you } = data;
  const confidence = you.confidence;
  const tierIndex = rules.confidence.tiers.findIndex((t) => t.tier === confidence.tier);
  const step = Math.round(rules.traits.max_step_per_message * 100);

  return (
    <PageShell
      eyebrow="How it works"
      title="What happens when"
      accent="you hit send."
      subtitle="The real path one message takes. The rules below are read from the code that runs them, and the numbers marked “you” are your account right now."
    >
      <div ref={steps} className="steps-thread relative space-y-16 before:absolute before:bottom-4 before:left-[13px] before:top-3 before:w-px before:bg-gradient-to-b before:from-iris-violet/70 before:via-iris-cyan/30 before:to-transparent md:before:left-[17px]">
        <Station
          step="1"
          title="You say something."
          aside={
            <Panel title="You">
              <div className="grid grid-cols-2 gap-4">
                <Stat value={you.messages.toLocaleString()} label="messages you've sent" />
                <Stat value={you.conversations} label="conversations" />
              </div>
            </Panel>
          }
        >
          <p>Your message is saved to your account so Reflectra can remember it later.</p>
          <p>
            With <span className="text-foreground">Incognito</span> on, nothing is saved at all: not the message, not the reply, and nothing is learned from it.
          </p>
        </Station>

        <Station
          step="2"
          title="It remembers."
          aside={
            <Panel title="The rule">
              <Fact label="Earlier messages it searches" value={`last ${rules.memory.messages_searched}`} />
              <Fact label="Related past exchanges it recalls" value={`up to ${rules.memory.related_recalled}`} />
              <Fact label="Most recent things you said, always included" value={rules.memory.recent_recalled} />
              <Fact label="Turns of this chat it keeps in view" value={rules.memory.turns_in_context} />
              {rules.memory.by_meaning && you.memory ? (
                <Fact
                  label="Your messages it can find by meaning (you)"
                  value={`${you.memory.by_meaning.toLocaleString()} of ${you.memory.recallable.toLocaleString()}`}
                />
              ) : null}
            </Panel>
          }
        >
          <p>
            Before replying it looks back through your earlier conversations for moments that share what you&apos;re talking about now, and favours rare, specific
            words over common ones.
          </p>
          {rules.memory.by_meaning ? (
            <p>
              It also searches by meaning, so “finals are killing me” finds the time you said “the last days of the semester kill me”. A match has to be close
              (similarity over {rules.memory.meaning_min_similarity}) and stand out from how alike all your messages are
              ({rules.memory.meaning_min_standout} deviations above your average), so it doesn&apos;t drag up random old chats.
            </p>
          ) : null}
          <p>That is how it can say “isn&apos;t this the phone thing from April?” instead of treating every chat as the first.</p>
        </Station>

        <Station
          step="3"
          title="It answers."
          aside={
            <Panel title="You" hint={you.mirror.replies_measured ? `measured over ${you.mirror.replies_measured} Mirror replies` : undefined}>
              <Fact label="Model writing your replies" value={rules.ai.reply_model ?? "none configured"} />
              {rules.ai.fast_model ? <Fact label={`Backup if that takes over ${rules.ai.hedge_seconds}s`} value={rules.ai.fast_model} /> : null}
              <Fact label="Samples of your writing Mirror can copy" value={`${Math.min(you.voice_samples_available, rules.mirror.voice_samples)} per reply, from ${you.voice_samples_available}`} />
              <Fact label="Average Mirror reply time" value={you.mirror.avg_seconds != null ? `${you.mirror.avg_seconds}s` : "not measured yet"} />
              <Fact label="Mirror replies that needed the simpler fallback" value={you.mirror.fallback_rate != null ? `${Math.round(you.mirror.fallback_rate * 100)}%` : "–"} />
              <Fact label="Reflection replies you rated good" value={rated(you.feedback?.replies.reflection?.up, you.feedback?.replies.reflection?.down)} />
              <Fact label="Mirror replies you said sound like you" value={rated(you.feedback?.replies.mirror?.up, you.feedback?.replies.mirror?.down)} />
            </Panel>
          }
        >
          <p>
            <span className="text-foreground">Reflection</span> replies like a friend who notices things: it matches your length, picks up specifics, and is not allowed to
            invent history you never told it.
          </p>
          <p>
            <span className="text-foreground">Mirror</span> replies as you. It is shown real messages you wrote and copies their casing, punctuation and rhythm. A draft that
            sounds like a chatbot is thrown away and rewritten once.
          </p>
        </Station>

        <Station step="4" title="It learns, slowly." aside={<LearningSimulator rules={rules.traits} />}>
          <p>
            Each message is read for four traits. One message can move a trait at most <span className="text-foreground">{step}%</span> of the way toward what it shows,
            and less once Reflectra is confident, so a single bad day can&apos;t rewrite you.
          </p>
          <p>Confidence rises when new messages agree with what it already believes and falls when they contradict it.</p>
          {rules.bootstrap.counts_as_messages ? (
            <p>
              A description you import in Settings is hearsay, so it is capped: even its strongest claim counts like{" "}
              <span className="text-foreground">{rules.bootstrap.counts_as_messages.strong} of your own messages</span>. It decides things on day one and
              barely moves them after a hundred.
            </p>
          ) : null}
          <div className="!mt-5 rounded-2xl border border-white/8 bg-white/[0.02] p-4">
            {you.traits.length ? (
              you.traits.map((trait) => (
                <div key={trait.key} className="flex items-center gap-3 py-1.5 text-sm">
                  <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: TRAIT_COLOR[trait.key] }} />
                  <span className="flex-1 text-foreground/85">{TRAIT_LABEL[trait.key]?.name ?? trait.key}</span>
                  <span className="font-mono text-foreground">{Math.round(trait.score * 100)}</span>
                  <span className="w-20 text-right font-mono text-xs text-muted-foreground">{Math.round(trait.confidence * 100)}% sure</span>
                  <span className="hidden w-24 text-right font-mono text-xs text-muted-foreground sm:block">{trait.evidence_count} signals</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No traits yet. They appear after your first few messages.</p>
            )}
            <p className="mt-3 border-t border-white/5 pt-3 text-xs text-muted-foreground">
              Readings you agreed with: <span className="font-mono text-foreground">{rated(you.feedback?.traits.agree, you.feedback?.traits.disagree)}</span>.
              Say yes or correct one on your Persona page; a correction counts like 15 of your messages.
            </p>
          </div>
        </Station>

        <Station
          step="5"
          title="It knows how sure it is."
          aside={
            <Panel title="You" hint={`overall ${Math.round(confidence.center * 100)}, likely between ${Math.round(confidence.interval.lower * 100)} and ${Math.round(confidence.interval.upper * 100)}`}>
              <div className="space-y-3">
                {Object.entries(rules.confidence.source_weights).map(([source, weight]) => {
                  const score = confidence.source_scores[source] ?? 0;
                  return (
                    <div key={source}>
                      <div className="flex justify-between text-xs">
                        <span className="text-foreground/80">{SOURCE_LABEL[source] ?? source}</span>
                        <span className="font-mono text-muted-foreground">
                          {score ? Math.round(score * 100) : "none yet"} · counts {Math.round(weight * 100)}%
                        </span>
                      </div>
                      <div className="mt-1.5 h-1 rounded-full bg-white/[0.06]">
                        <div className="h-full rounded-full bg-gradient-to-r from-iris-violet to-iris-cyan" style={{ width: `${Math.round(score * 100)}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
              <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
                The range is wide when there is little to go on or when these four disagree, and narrows as you talk. A source with nothing in it is left out
                rather than counted as zero. Going quiet for more than a month slowly lowers it.
              </p>
            </Panel>
          }
        >
          <p>
            Reflectra combines four kinds of evidence into one confidence range, then acts on the <span className="text-foreground">cautious end</span> of it. That places you in
            one of four levels, which decide how boldly Mirror imitates you.
          </p>
          <div className="!mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {rules.confidence.tiers.map((tier, i) => (
              <div
                key={tier.tier}
                className={cn("rounded-2xl border p-3", i === tierIndex ? "iris-border border-transparent bg-white/[0.05]" : "border-white/8 bg-white/[0.02] opacity-70")}
              >
                <p className="text-sm font-medium text-foreground">{TIER_LABEL[tier.tier] ?? tier.tier}</p>
                <p className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">up to {tier.up_to}</p>
                <p className="mt-2 text-xs leading-snug text-muted-foreground">Copies your style at {Math.round(tier.style_enforcement_intensity * 100)}% strength</p>
                {i === tierIndex ? <p className="mt-2 font-mono text-[10px] uppercase tracking-widest text-iris-cyan">you are here</p> : null}
              </div>
            ))}
          </div>
        </Station>

        <Station
          step="6"
          title="It reflects."
          aside={
            <Panel title="The rule">
              <Fact label="Messages it reads each time" value={`your last ${rules.reflections.messages_read}`} />
              <Fact label="Messages needed before it will try" value={rules.reflections.min_messages} />
              <Fact label="Separate quotes each pattern must have" value={`at least ${rules.reflections.min_quotes}`} />
              <Fact label="Reflections on your page now" value={you.reflections} />
              <Fact label="Reflections you said were spot on" value={rated(you.feedback?.reflections.agree, you.feedback?.reflections.disagree)} />
            </Panel>
          }
        >
          <p>
            On the Reflections page it reads back through what you&apos;ve said and writes down patterns. Every quote it cites is checked against your actual messages, word
            for word.
          </p>
          <p>A pattern with a quote you never said, or one that only happened once, is thrown out before you see it.</p>
        </Station>

        <Station step="7" title="It stays yours.">
          <p>Every request carries your login, and the server works out who you are from that, never from an id the browser sends.</p>
          <p>The database itself refuses to hand your rows to anyone else, including through Supabase&apos;s public API.</p>
          <p>Clearing your data or deleting your account erases your conversations, traits and reflections with it.</p>
        </Station>
        <span className="steps-track" aria-hidden="true">
          <span className="steps-light" />
          <span className="steps-head" />
        </span>
      </div>
    </PageShell>
  );
}
