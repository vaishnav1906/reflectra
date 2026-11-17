import { useMemo, useState } from "react";
import { PortraitTrait, TRAIT_COLOR, TRAIT_LABEL, TRAIT_ORDER, TraitKey, TraitPoint, formatDay } from "@/hooks/useReflectra";
import { useGrow } from "./useGrow";

/** A trait as a spectrum: marker = score, soft band = how unsure Reflectra still is. */
export function TraitSpectrum({ trait }: { trait: PortraitTrait }) {
  const grow = useGrow(1200);
  const color = TRAIT_COLOR[trait.key];
  const position = (0.5 + (trait.score - 0.5) * grow) * 100;
  const band = (1 - trait.confidence) * 22;

  return (
    <div>
      <div className="flex items-baseline justify-between gap-4">
        <h3 className="text-[15px] font-medium">{trait.name}</h3>
        <p className="font-display text-4xl leading-none" style={{ color }}>
          {Math.round((0.5 + (trait.score - 0.5) * grow) * 100)}
        </p>
      </div>
      <div
        className="relative mt-4 h-1.5 rounded-full bg-white/[0.07]"
        role="img"
        aria-label={`${trait.name}: ${Math.round(trait.score * 100)} out of 100, between ${trait.low} and ${trait.high}`}
      >
        <div
          className="absolute top-0 h-full rounded-full"
          style={{
            left: `${Math.max(0, position - band)}%`,
            width: `${Math.min(100, position + band) - Math.max(0, position - band)}%`,
            background: color,
            opacity: 0.28,
          }}
        />
        <div
          className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-4 ring-background"
          style={{ left: `${position}%`, background: color, boxShadow: `0 0 18px ${color}` }}
        />
      </div>
      <div className="mt-2 flex justify-between font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70">
        <span>{trait.low}</span>
        <span>{trait.high}</span>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-foreground/85">{trait.reading}</p>
      <p className="mt-1 text-xs text-muted-foreground">
        {Math.round(trait.confidence * 100)}% sure ({trait.confidence_label}), from {trait.evidence_count} signals in your messages
      </p>
    </div>
  );
}

/** Trait scores over the days the user talked, evenly spaced, with a hover readout. */
export function TraitRiver({ series, height = 240 }: { series: TraitPoint[]; height?: number }) {
  const grow = useGrow(1600);
  const [hover, setHover] = useState<number | null>(null);
  const width = 760;
  const pad = { left: 30, right: 14, top: 12, bottom: 26 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const xs = useMemo(() => series.map((_, i) => pad.left + (innerW * i) / Math.max(series.length - 1, 1)), [series, innerW, pad.left]);
  const y = (value: number) => pad.top + innerH * (1 - value);

  if (series.length < 2) {
    return <p className="py-10 text-center text-sm text-muted-foreground">This chart appears once you&apos;ve talked on at least two different days.</p>;
  }

  const active = hover ?? series.length - 1;
  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full touch-none"
        role="img"
        aria-label="How your four trait scores changed over the days you talked"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const x = ((event.clientX - rect.left) / rect.width) * width;
          let nearest = 0;
          xs.forEach((value, i) => {
            if (Math.abs(value - x) < Math.abs(xs[nearest] - x)) nearest = i;
          });
          setHover(nearest);
        }}
      >
        {[0, 0.5, 1].map((value) => (
          <g key={value}>
            <line x1={pad.left} x2={width - pad.right} y1={y(value)} y2={y(value)} stroke="hsl(0 0% 100% / 0.07)" strokeDasharray={value === 0.5 ? "3 5" : undefined} />
            <text x={pad.left - 8} y={y(value) + 3} textAnchor="end" className="fill-muted-foreground font-mono text-[9px]">
              {value * 100}
            </text>
          </g>
        ))}
        <line x1={xs[active]} x2={xs[active]} y1={pad.top} y2={pad.top + innerH} stroke="hsl(0 0% 100% / 0.16)" />
        {TRAIT_ORDER.map((key) => {
          const points = series.map((p, i) => (p[key] == null ? null : ([xs[i], y(p[key] as number)] as const))).filter(Boolean) as (readonly [number, number])[];
          if (points.length < 2) return null;
          const d = points.map(([px, py], i) => `${i ? "L" : "M"} ${px.toFixed(1)} ${py.toFixed(1)}`).join(" ");
          return (
            <g key={key}>
              <path d={d} fill="none" stroke={TRAIT_COLOR[key]} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" pathLength={1} strokeDasharray="1" strokeDashoffset={1 - grow} />
              {series[active]?.[key] != null && grow > 0.98 ? (
                <circle cx={xs[active]} cy={y(series[active][key] as number)} r="4" fill={TRAIT_COLOR[key]} stroke="hsl(var(--background))" strokeWidth="2" />
              ) : null}
            </g>
          );
        })}
        <text x={pad.left} y={height - 6} className="fill-muted-foreground font-mono text-[9px] uppercase">
          {formatDay(series[0].date, { day: "numeric", month: "short", year: "2-digit" })}
        </text>
        <text x={width - pad.right} y={height - 6} textAnchor="end" className="fill-muted-foreground font-mono text-[9px] uppercase">
          {formatDay(series[series.length - 1].date, { day: "numeric", month: "short", year: "2-digit" })}
        </text>
      </svg>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs">
        <span className="font-mono uppercase tracking-widest text-muted-foreground">{formatDay(series[active].date)}</span>
        {TRAIT_ORDER.map((key: TraitKey) => (
          <span key={key} className="flex items-center gap-1.5 text-foreground/80">
            <span className="h-2 w-2 rounded-full" style={{ background: TRAIT_COLOR[key] }} />
            {TRAIT_LABEL[key].name}
            <span className="font-mono text-muted-foreground">{series[active][key] == null ? "–" : Math.round((series[active][key] as number) * 100)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/** A 24-hour clock of when the user talks: one spoke per hour, longest = busiest. */
export function RhythmClock({ hours }: { hours: number[] }) {
  const grow = useGrow(1300);
  const size = 300;
  const c = size / 2;
  const inner = 58;
  const outer = 116;
  const peak = Math.max(...hours, 1);
  const total = hours.reduce((a, b) => a + b, 0);
  const peakHour = hours.indexOf(Math.max(...hours));
  const hour12 = (h: number) => `${h % 12 || 12} ${h < 12 ? "am" : "pm"}`;

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="mx-auto w-full max-w-[300px]" role="img" aria-label={total ? `You talk most around ${hour12(peakHour)}` : "No messages yet"}>
      <circle cx={c} cy={c} r={inner} fill="none" stroke="hsl(0 0% 100% / 0.08)" />
      {hours.map((count, hour) => {
        const angle = ((hour / 24) * 360 - 90) * (Math.PI / 180);
        const length = (outer - inner) * (count / peak) * grow;
        const x1 = c + Math.cos(angle) * (inner + 4);
        const y1 = c + Math.sin(angle) * (inner + 4);
        const x2 = c + Math.cos(angle) * (inner + 4 + Math.max(length, 1.5));
        const y2 = c + Math.sin(angle) * (inner + 4 + Math.max(length, 1.5));
        const isPeak = total > 0 && hour === peakHour;
        return (
          <line
            key={hour}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke={isPeak ? "hsl(var(--iris-peach))" : "hsl(var(--iris-violet))"}
            strokeOpacity={count ? (isPeak ? 1 : 0.55) : 0.15}
            strokeWidth="6"
            strokeLinecap="round"
          >
            <title>{`${hour12(hour)}: ${count} messages`}</title>
          </line>
        );
      })}
      {[0, 6, 12, 18].map((hour) => {
        const angle = ((hour / 24) * 360 - 90) * (Math.PI / 180);
        return (
          <text key={hour} x={c + Math.cos(angle) * (outer + 24)} y={c + Math.sin(angle) * (outer + 24) + 3} textAnchor="middle" className="fill-muted-foreground font-mono text-[9px] uppercase">
            {hour12(hour).replace(" ", "")}
          </text>
        );
      })}
      <text x={c} y={c - 4} textAnchor="middle" className="fill-foreground font-display text-[26px]">
        {total ? hour12(peakHour) : "–"}
      </text>
      <text x={c} y={c + 14} textAnchor="middle" className="fill-muted-foreground font-mono text-[8px] uppercase tracking-widest">
        busiest hour
      </text>
    </svg>
  );
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function WeekBars({ days }: { days: number[] }) {
  const grow = useGrow(1100);
  const peak = Math.max(...days, 1);
  return (
    <div className="flex h-36 items-end gap-2" role="img" aria-label={`Messages by weekday. Busiest: ${DAYS[days.indexOf(Math.max(...days))]}`}>
      {days.map((count, i) => (
        <div key={DAYS[i]} className="flex h-full flex-1 flex-col items-center justify-end gap-2" title={`${DAYS[i]}: ${count} messages`}>
          <div
            className="w-full rounded-t-lg"
            style={{
              height: `${Math.max(2, (count / peak) * 100 * grow)}%`,
              background: count === peak && count ? "hsl(var(--iris-peach))" : "hsl(var(--iris-violet) / 0.4)",
            }}
          />
          <span className="font-mono text-[10px] uppercase text-muted-foreground">{DAYS[i][0]}</span>
        </div>
      ))}
    </div>
  );
}
