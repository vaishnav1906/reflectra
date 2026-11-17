import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { ErrorState, LoadingState, PageShell, Panel, Stat } from "@/components/portrait/PageShell";
import { TraitRiver } from "@/components/portrait/Charts";
import { LooseEnds } from "@/components/portrait/LooseEnds";
import { formatDay, useLifeMemory, usePeople, useReflections, useTimeline } from "@/hooks/useReflectra";
import { PlayWeekButton, WeekReel } from "@/components/week/WeekReel";

/**
 * Your week: the Sunday digest. How much you talked and when, how you moved, who came
 * up, what's going on, and the loose ends still open. Everything counted from the
 * last seven days.
 */

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function moodWord(mood: number | null) {
  if (mood === null) return null;
  if (mood >= 0.3) return "lighter";
  if (mood <= -0.3) return "heavier";
  return "mixed";
}

export function WeekPage() {
  const timeline = useTimeline("7d");
  const people = usePeople();
  const life = useLifeMemory();
  const reflections = useReflections();
  const [params, setParams] = useSearchParams();
  const [playing, setPlaying] = useState(false);
  // Opened from the Sunday notification: the reel plays straight away.
  const autoplay = params.get("play") === "1";
  const ready = Boolean(timeline.data) && !people.isLoading && !life.isLoading && !reflections.isLoading;
  useEffect(() => {
    if (!autoplay || !ready) return;
    if (timeline.data?.summary.user_messages) setPlaying(true);
    const next = new URLSearchParams(params);
    next.delete("play");
    setParams(next, { replace: true });
  }, [autoplay, ready]); // eslint-disable-line react-hooks/exhaustive-deps

  if (timeline.isLoading) return <LoadingState label="Putting your week together…" />;
  if (timeline.error || !timeline.data) return <ErrorState message="Couldn't load your week." onRetry={() => void timeline.refetch()} />;

  const { summary, days, trait_series } = timeline.data;
  const weekAgo = Date.now() - 7 * 86_400_000;
  const recentPeople = (people.data?.people ?? []).filter((p) => p.last_mentioned_at && new Date(p.last_mentioned_at).getTime() >= weekAgo);
  const going = (life.data?.facts ?? []).filter((f) => f.status === "active" && (f.kind === "situation" || f.kind === "goal")).slice(0, 6);
  const newest = reflections.data?.reflections?.[0];
  const byDay = new Map(days.map((d) => [new Date(`${d.date}T00:00:00`).getDay(), d]));
  const peak = Math.max(1, ...days.map((d) => d.user_messages));
  const reel = {
    activeDays: summary.active_days,
    messages: summary.user_messages,
    conversations: summary.conversations,
    days: [1, 2, 3, 4, 5, 6, 0].map((weekday, i) => {
      const day = byDay.get(weekday);
      return { label: DAY_NAMES[i], messages: day?.user_messages ?? 0, mood: moodWord(day?.mood ?? null) };
    }),
    people: recentPeople.map((p) => ({ id: p.id, name: p.name, relationship: p.relationship })),
    going: going.map((f) => f.text),
    pattern: newest ? { title: newest.title, insight: newest.insight } : null,
  };

  return (
    <PageShell
      eyebrow="Your week"
      title="Seven days,"
      accent="looked back on."
      subtitle={
        summary.user_messages
          ? `You talked on ${summary.active_days} of the last 7 days and sent ${summary.user_messages} messages.`
          : "A quiet week. Nothing to look back on yet, and that's fine."
      }
      actions={summary.user_messages ? <PlayWeekButton onClick={() => setPlaying(true)} /> : undefined}
    >
      {playing ? <WeekReel data={reel} onClose={() => setPlaying(false)} /> : null}
      {summary.user_messages ? (
        <>
          <Panel className="iris-border">
            <div className="grid grid-cols-7 items-end gap-2" role="img" aria-label="Messages per day this week">
              {[1, 2, 3, 4, 5, 6, 0].map((weekday, i) => {
                const day = byDay.get(weekday);
                const mood = moodWord(day?.mood ?? null);
                return (
                  <div key={weekday} className="flex flex-col items-center gap-2">
                    <div className="flex h-28 w-full items-end justify-center">
                      <div
                        className="w-full max-w-[42px] rounded-t-xl bg-gradient-to-t from-iris-violet/70 to-iris-cyan/80"
                        style={{ height: `${day ? Math.max(6, (day.user_messages / peak) * 100) : 3}%`, opacity: day ? 1 : 0.15 }}
                        title={day ? `${day.user_messages} messages${mood ? `, ${mood} words` : ""}` : "no messages"}
                      />
                    </div>
                    <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{DAY_NAMES[i]}</span>
                    <span className="text-[10px] text-muted-foreground">{mood ?? ""}</span>
                  </div>
                );
              })}
            </div>
            <div className="mt-6 grid grid-cols-3 gap-4 border-t border-white/5 pt-5">
              <Stat value={summary.active_days} label="days you talked" />
              <Stat value={summary.user_messages} label="messages" />
              <Stat value={summary.conversations} label="conversations" />
            </div>
          </Panel>

          {trait_series.length > 1 ? (
            <Panel title="How you moved this week">
              <TraitRiver series={trait_series} height={180} />
            </Panel>
          ) : null}

          <div className="grid gap-6 md:grid-cols-2">
            <Panel title="Who came up">
              {recentPeople.length ? (
                <ul className="flex flex-wrap gap-2">
                  {recentPeople.map((p) => (
                    <li key={p.id}>
                      <Link to={`/app/people?person=${p.id}`} className="reply-reason">
                        {p.name}
                        {p.relationship ? <span className="text-muted-foreground">· {p.relationship}</span> : null}
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">Nobody from your People this week.</p>
              )}
            </Panel>
            <Panel title="Going on for you">
              {going.length ? (
                <ul className="space-y-2">
                  {going.map((f) => (
                    <li key={f.id} className="text-sm text-foreground/85">
                      {f.text}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">Nothing noted yet.</p>
              )}
              <Link to="/app/life" className="mt-4 inline-flex items-center gap-1 text-sm text-primary hover:underline">
                Your life <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </Panel>
          </div>

          {newest ? (
            <Panel title="A pattern worth noticing">
              <p className="font-display text-2xl leading-snug">{newest.title}</p>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">{newest.insight}</p>
              <p className="mt-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">written {formatDay(newest.created_at)}</p>
            </Panel>
          ) : null}
        </>
      ) : null}

      <LooseEnds />
    </PageShell>
  );
}
