import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Flag, Sparkles, TrendingUp, Upload, Zap } from "lucide-react";
import { ErrorState, LoadingState, PageShell, Panel, Stat } from "@/components/portrait/PageShell";
import { TraitRiver } from "@/components/portrait/Charts";
import { Milestone, TimelineDay, formatDay, useTimeline } from "@/hooks/useReflectra";
import { cn } from "@/lib/utils";

/**
 * Timeline: what you actually talked about, day by day.
 * Every figure is counted from stored conversations; nothing is estimated except
 * mood, which is a simple count of positive vs negative feeling-words that day.
 */

const RANGES = [
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
  { value: "1y", label: "1 year" },
  { value: "all", label: "All time" },
];

const MILESTONE_ICON: Record<string, typeof Flag> = {
  start: Flag,
  activity: Zap,
  trait: TrendingUp,
  import: Upload,
  reflection: Sparkles,
};

function moodLabel(mood: number | null): { text: string; color: string } | null {
  if (mood === null) return null;
  if (mood >= 0.3) return { text: "mostly upbeat words", color: "hsl(var(--trait-consistent))" };
  if (mood <= -0.3) return { text: "mostly heavy words", color: "hsl(var(--trait-empathetic))" };
  return { text: "mixed feelings", color: "hsl(var(--iris-peach))" };
}

function DayCard({ day, peak }: { day: TimelineDay; peak: number }) {
  const navigate = useNavigate();
  const mood = moodLabel(day.mood);
  return (
    <li className="relative pl-8">
      <span className="absolute left-0 top-2 h-2.5 w-2.5 rounded-full bg-iris-violet shadow-[0_0_14px_hsl(var(--iris-violet))]" />
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h3 className="font-display text-2xl">{formatDay(day.date, { weekday: "long", day: "numeric", month: "long" })}</h3>
        <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
          {day.user_messages} {day.user_messages === 1 ? "message" : "messages"}
        </span>
        {mood ? (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: mood.color }} />
            {mood.text}
          </span>
        ) : null}
      </div>

      {/* how much of your busiest day this was */}
      <div className="mt-3 h-1 w-full max-w-md overflow-hidden rounded-full bg-white/[0.06]" aria-hidden="true">
        <div className="h-full rounded-full bg-gradient-to-r from-iris-violet to-iris-cyan" style={{ width: `${Math.max(3, (day.user_messages / peak) * 100)}%` }} />
      </div>

      {day.highlight ? (
        <blockquote className="mt-4 max-w-2xl border-l border-iris-peach/60 pl-4 text-[15px] italic leading-relaxed text-foreground/80">
          “{day.highlight}”
        </blockquote>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {day.conversations.map((conversation) => (
          <button
            key={conversation.id}
            type="button"
            onClick={() => navigate(`/app/chat?conversation_id=${conversation.id}&mode=${conversation.mode === "mirror" ? "mirror" : "reflection"}`)}
            className="group flex max-w-full items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs transition-colors hover:border-white/25 hover:bg-white/[0.07]"
            title="Open this conversation"
          >
            <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", conversation.mode === "mirror" ? "bg-iris-cyan" : "bg-iris-violet")} />
            <span className="truncate text-foreground/85">{conversation.title}</span>
            <span className="shrink-0 font-mono text-muted-foreground">{conversation.user_messages}</span>
          </button>
        ))}
      </div>
    </li>
  );
}

function MilestoneRow({ milestone }: { milestone: Milestone }) {
  const Icon = MILESTONE_ICON[milestone.kind] || Flag;
  return (
    <li className="flex gap-3">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-iris-cyan" aria-hidden="true" />
      <div>
        <p className="text-sm leading-snug text-foreground/90">{milestone.text}</p>
        <p className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{formatDay(milestone.date)}</p>
      </div>
    </li>
  );
}

export function MemoryPage() {
  const [range, setRange] = useState("all");
  const { data, isLoading, error, refetch } = useTimeline(range);

  if (isLoading && !data) return <LoadingState label="Laying out your timeline…" />;
  if (error || !data) return <ErrorState message={error instanceof Error ? error.message : "Couldn't load your timeline."} onRetry={() => void refetch()} />;

  const { summary, days, milestones, trait_series } = data;
  const peak = Math.max(...days.map((d) => d.user_messages), 1);
  const reflectionCount = summary.conversations_by_mode.reflection ?? 0;
  const mirrorCount = summary.conversations_by_mode.mirror ?? 0;

  return (
    <PageShell
      eyebrow="Timeline"
      title="Your story,"
      accent="day by day."
      subtitle="What you talked about, how much, and how your persona moved while you did. Counted straight from your conversations."
      actions={
        <div className="flex rounded-full border border-white/10 bg-white/[0.03] p-1" role="group" aria-label="Time range">
          {RANGES.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setRange(option.value)}
              aria-pressed={range === option.value}
              className={cn(
                "rounded-full px-3.5 py-1.5 text-xs font-medium transition-all",
                range === option.value ? "mode-pill-active text-primary-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      }
    >
      {days.length === 0 ? (
        <Panel>
          <p className="py-10 text-center text-muted-foreground">
            Nothing in this period. {range !== "all" ? "Try a longer range, or start a conversation." : "Start a conversation and it will show up here."}
          </p>
        </Panel>
      ) : (
        <>
          <Panel className="iris-border">
            <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
              <Stat value={summary.active_days} label="days you talked" />
              <Stat value={summary.user_messages.toLocaleString()} label="messages you sent" />
              <Stat value={summary.conversations} label={`conversations (${reflectionCount} reflection, ${mirrorCount} mirror)`} />
              <Stat value={summary.longest_streak} label="longest streak, in days" />
            </div>
          </Panel>

          <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
            <Panel title="How your persona moved" hint="hover to read a day">
              <TraitRiver series={trait_series} height={220} />
            </Panel>
            <Panel title="Milestones">
              {milestones.length ? (
                <ul className="space-y-4">
                  {milestones.slice(0, 7).map((milestone, i) => (
                    <MilestoneRow key={`${milestone.date}-${i}`} milestone={milestone} />
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">None yet.</p>
              )}
            </Panel>
          </div>

          <section aria-label="Days">
            <p className="eyebrow mb-6">Day by day · newest first</p>
            <ol className="relative space-y-10 before:absolute before:bottom-2 before:left-[4.5px] before:top-3 before:w-px before:bg-gradient-to-b before:from-iris-violet/60 before:via-white/10 before:to-transparent">
              {days.map((day) => (
                <DayCard key={day.date} day={day} peak={peak} />
              ))}
            </ol>
          </section>
        </>
      )}
    </PageShell>
  );
}
