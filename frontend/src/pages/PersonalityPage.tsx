import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { ErrorState, LoadingState, PageShell, Panel, Stat } from "@/components/portrait/PageShell";
import { TraitShape } from "@/components/portrait/TraitShape";
import { TraitCheck } from "@/components/portrait/TraitCheck";
import { RhythmClock, TraitRiver, TraitSpectrum, WeekBars } from "@/components/portrait/Charts";
import { TimetableSection } from "@/components/timetable/TimetableSection";
import { ExportPortraitButton } from "@/components/transitions/PortraitPrint";
import { formatDay, pct, usePortrait } from "@/hooks/useReflectra";

/**
 * Persona: a live portrait built from the same data as the PDF report.
 * Every number here comes from the user's stored conversations.
 */
export function PersonalityPage() {
  const { data, isLoading, error, refetch } = usePortrait();
  // A trait you're correcting: the shape reshapes as you drag.
  const [preview, setPreview] = useState<{ key: string; score: number } | null>(null);

  if (isLoading) return <LoadingState label="Drawing your portrait…" />;
  if (error || !data) return <ErrorState message={error instanceof Error ? error.message : "Couldn't load your persona."} onRetry={() => void refetch()} />;

  const hasTraits = data.traits.length === 4;
  const voice = data.voice;
  const lateShare = (() => {
    const total = data.hour_histogram.reduce((a, b) => a + b, 0);
    if (!total) return 0;
    return [22, 23, 0, 1, 2, 3].reduce((sum, hour) => sum + data.hour_histogram[hour], 0) / total;
  })();

  return (
    <PageShell
      eyebrow="Persona"
      title="The shape of"
      accent={`${data.name}.`}
      actions={hasTraits ? <ExportPortraitButton className="btn-ghost-glass !py-2.5" label="Export PDF" /> : undefined}
      subtitle={
        hasTraits ? (
          <>
            <span className="text-foreground">{data.headline}</span> Learned from {data.user_messages.toLocaleString()} messages
            across {data.conversations} conversations{data.first_date ? `, since ${formatDay(data.first_date)}` : ""}.
          </>
        ) : (
          "Reflectra hasn't seen enough of you yet. Have a few conversations and this page fills in."
        )
      }
    >
      {hasTraits ? (
        <>
          {/* The shape */}
          <Panel className="iris-border overflow-hidden">
            <div className="grid items-center gap-6 lg:grid-cols-[1.1fr_0.9fr]">
              <TraitShape traits={data.traits} preview={preview} />
              <div>
                <p className="eyebrow mb-4">How to read it</p>
                <p className="text-[15px] leading-relaxed text-foreground/80">
                  Each direction is one trait, from its low side at the centre to its high side at the edge. A perfect circle
                  would be someone at 50 on everything. Yours bulges where you lean.
                </p>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                  The faint halo is doubt. It shrinks as Reflectra sees the same thing from you again and again.
                </p>
                <div className="mt-6 grid grid-cols-3 gap-4 border-t border-white/5 pt-6">
                  <Stat value={data.active_days} label="days you've talked" />
                  <Stat value={data.longest_streak} label="longest streak (days)" />
                  <Stat value={`${Math.round((data.traits.reduce((s, t) => s + t.confidence, 0) / 4) * 100)}%`} label="average trait confidence" />
                </div>
              </div>
            </div>
          </Panel>

          {/* Trait by trait */}
          <div className="grid gap-6 md:grid-cols-2">
            {data.traits.map((trait) => (
              <Panel key={trait.key}>
                <TraitSpectrum trait={trait} />
                {/* The big shape is off-screen while you drag down here, so a small live copy shows beside the slider. */}
                {preview?.key === trait.key ? (
                  <div className="mx-auto mt-4 max-w-[260px] fade-in">
                    <TraitShape traits={data.traits} preview={preview} />
                  </div>
                ) : null}
                <TraitCheck
                  trait={trait}
                  onPreview={(score) => setPreview((current) => (score === null ? (current?.key === trait.key ? null : current) : { key: trait.key, score }))}
                />
              </Panel>
            ))}
          </div>

          {/* Over time */}
          <Panel title="How you've moved" hint="one point per day you talked · hover to read a day">
            <TraitRiver series={data.trait_series} />
          </Panel>
        </>
      ) : null}

      {/* Rhythm */}
      <Panel title="When you talk">
        <div className="grid items-center gap-8 md:grid-cols-[auto_1fr]">
          <RhythmClock hours={data.hour_histogram} />
          <div>
            <WeekBars days={data.weekday_histogram} />
            <div className="mt-6 grid grid-cols-2 gap-4 border-t border-white/5 pt-6">
              <Stat value={`${Math.round(lateShare * 100)}%`} label="of your messages come between 10 pm and 4 am" />
              <Stat
                value={data.busiest_day ? data.busiest_day.user_messages : "–"}
                label={data.busiest_day ? `messages on your biggest day, ${formatDay(data.busiest_day.date)}` : "no busiest day yet"}
              />
            </div>
          </div>
        </div>
      </Panel>

      {/* Voice */}
      {voice.messages >= 5 ? (
        <Panel title="How you write" hint={`measured over your last ${voice.messages} messages · this is what Mirror mode copies`}>
          <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
            <Stat value={voice.median_words ?? "–"} label="words in a typical message" />
            <Stat value={`${pct(voice.lowercase_share)}%`} label="typed with no capital letters" />
            <Stat value={`${pct(voice.question_share)}%`} label="contain a question" />
            <Stat value={`${pct(voice.emoji_share)}%`} label="contain an emoji" />
          </div>
          {(voice.abbreviations?.some((a) => a.count >= 2) || voice.phrases?.length) ? (
            <div className="mt-6 flex flex-wrap gap-2 border-t border-white/5 pt-6">
              {voice.abbreviations?.filter((a) => a.count >= 2).map((a) => (
                <span key={a.word} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 font-mono text-xs text-foreground/80">
                  {a.word} <span className="text-muted-foreground">×{a.count}</span>
                </span>
              ))}
              {voice.phrases?.map((phrase) => (
                <span key={phrase} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs italic text-foreground/80">
                  “{phrase}”
                </span>
              ))}
            </div>
          ) : null}
        </Panel>
      ) : null}

      {/* What keeps coming up + adaptation */}
      <div className="grid gap-6 md:grid-cols-2">
        <Panel title="What keeps coming up">
          {data.reflections.length ? (
            <ul className="space-y-4">
              {data.reflections.slice(0, 3).map((reflection) => (
                <li key={reflection.id}>
                  <p className="font-display text-xl leading-snug">{reflection.title}</p>
                  {reflection.evidence[0] ? (
                    <p className="mt-1 border-l border-iris-peach/60 pl-3 text-sm italic text-muted-foreground">“{reflection.evidence[0].quote}”</p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No patterns written yet.</p>
          )}
          <Link to="/app/reflections" className="mt-6 inline-flex items-center gap-1 text-sm text-primary hover:underline">
            Open Reflections <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </Panel>

        <Panel title="How Reflectra talks to you because of this">
          <ul className="space-y-3">
            {data.adaptation.map((line) => (
              <li key={line} className="flex gap-3 text-[15px] leading-relaxed text-foreground/85">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-iris-cyan" />
                {line}
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      {/* Life context the user sets by hand */}
      <div>
        <p className="eyebrow mb-3">Your week, in your words</p>
        <TimetableSection />
      </div>
    </PageShell>
  );
}
