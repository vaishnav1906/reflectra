import { ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Pause, Play, X } from "lucide-react";
import { MirrorMark } from "@/components/MirrorMark";
import { CountUp } from "@/components/motion/CountUp";
import { prefersReducedMotion } from "@/lib/motion";
import { cn } from "@/lib/utils";

/**
 * Your week as a short reel of cards, like stories: tap the right side (or swipe left)
 * for the next, the left side for the previous, hold to pause, Esc to close. Each card
 * moves on by itself after a few seconds, unless your device asks for less motion.
 */

export interface WeekReelData {
  activeDays: number;
  messages: number;
  conversations: number;
  /** Monday first: messages and a mood word for each day. */
  days: { label: string; messages: number; mood: string | null }[];
  people: { id: string; name: string; relationship?: string | null }[];
  going: string[];
  pattern: { title: string; insight: string } | null;
}

const CARD_MS = 5200;

export function WeekReel({ data, onClose }: { data: WeekReelData; onClose: () => void }) {
  const cards = buildCards(data);
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [elapsed, setElapsed] = useState(0); // ms into the current card
  const auto = !prefersReducedMotion();
  const box = useRef<HTMLDivElement>(null);
  const press = useRef<{ x: number; y: number; at: number } | null>(null);

  const go = useCallback(
    (step: number) => {
      setElapsed(0);
      setIndex((current) => {
        const next = current + step;
        if (next >= cards.length) {
          onClose();
          return current;
        }
        return Math.max(0, next);
      });
    },
    [cards.length, onClose],
  );

  // The timer for the current card.
  useEffect(() => {
    if (!auto || paused) return;
    let frame = 0;
    let last = performance.now();
    const tick = (now: number) => {
      setElapsed((e) => {
        const next = e + (now - last);
        if (next >= CARD_MS) {
          window.setTimeout(() => go(1), 0);
          return CARD_MS;
        }
        return next;
      });
      last = now;
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [auto, paused, index, go]);

  useEffect(() => {
    box.current?.focus();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  const onKey = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") onClose();
    else if (event.key === "ArrowRight") go(1);
    else if (event.key === "ArrowLeft") go(-1);
    else if (event.key === " ") {
      event.preventDefault();
      setPaused((p) => !p);
    } else return;
    event.stopPropagation();
  };

  return createPortal(
    <div
      ref={box}
      className="week-reel"
      role="dialog"
      aria-modal="true"
      aria-label="Your week, card by card"
      tabIndex={-1}
      onKeyDown={onKey}
    >
      <div className="week-reel-backdrop" onClick={onClose} />
      <div
        className="week-reel-stage"
        onPointerDown={(event) => {
          if ((event.target as HTMLElement).closest("button, a")) return;
          press.current = { x: event.clientX, y: event.clientY, at: performance.now() };
          setPaused(true);
        }}
        onPointerUp={(event) => {
          const start = press.current;
          press.current = null;
          setPaused(false);
          if (!start) return;
          const dx = event.clientX - start.x;
          const held = performance.now() - start.at > 350;
          if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1); // swipe
          else if (!held) {
            const rect = event.currentTarget.getBoundingClientRect();
            go(event.clientX - rect.left < rect.width / 3 ? -1 : 1); // tap
          }
        }}
        onPointerCancel={() => {
          press.current = null;
          setPaused(false);
        }}
      >
        <div className="week-reel-progress" aria-hidden="true">
          {cards.map((card, i) => (
            <span key={card.key}>
              <span style={{ transform: `scaleX(${i < index ? 1 : i > index ? 0 : auto ? elapsed / CARD_MS : 1})` }} />
            </span>
          ))}
        </div>
        <div className="week-reel-controls">
          <button type="button" onClick={() => setPaused((p) => !p)} aria-label={paused ? "Play" : "Pause"} className="week-reel-icon">
            {paused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
          </button>
          <button type="button" onClick={onClose} aria-label="Close" className="week-reel-icon">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div key={cards[index].key} className="week-card" aria-live="polite">
          {cards[index].body}
        </div>
        <p className="week-reel-hint" aria-hidden="true">
          {index + 1} / {cards.length} · tap or swipe
        </p>
      </div>
    </div>,
    document.body,
  );
}

function buildCards(data: WeekReelData): { key: string; body: ReactNode }[] {
  const peak = Math.max(1, ...data.days.map((d) => d.messages));
  const busiest = data.days.reduce((best, d) => (d.messages > best.messages ? d : best), data.days[0]);
  const cards: { key: string; body: ReactNode }[] = [
    {
      key: "intro",
      body: (
        <>
          <MirrorMark className="week-rise h-16 w-16" breathing />
          <p className="eyebrow week-rise mt-8" style={{ animationDelay: "0.1s" }}>Your week</p>
          <p className="week-big week-rise" style={{ animationDelay: "0.2s" }}>
            <CountUp value={data.messages} />
          </p>
          <p className="week-rise text-lg text-foreground/85" style={{ animationDelay: "0.35s" }}>
            messages, over <CountUp value={data.activeDays} /> {data.activeDays === 1 ? "day" : "days"} and {data.conversations}{" "}
            {data.conversations === 1 ? "conversation" : "conversations"}.
          </p>
        </>
      ),
    },
    {
      key: "days",
      body: (
        <>
          <p className="eyebrow week-rise">When you talked</p>
          <div className="week-bars mt-8" role="img" aria-label="Messages per day">
            {data.days.map((day, i) => (
              <div key={day.label} className="flex flex-col items-center gap-2">
                <div className="flex h-40 w-full items-end justify-center">
                  <span
                    className="week-bar"
                    style={{
                      height: `${day.messages ? Math.max(6, (day.messages / peak) * 100) : 3}%`,
                      opacity: day.messages ? 1 : 0.18,
                      animationDelay: `${0.15 + i * 0.08}s`,
                    }}
                  />
                </div>
                <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{day.label}</span>
                <span className="week-rise h-3 text-[10px] text-iris-peach" style={{ animationDelay: `${0.8 + i * 0.08}s` }}>
                  {day.mood ?? ""}
                </span>
              </div>
            ))}
          </div>
          {busiest?.messages ? (
            <p className="week-rise mt-6 text-foreground/85" style={{ animationDelay: "1.2s" }}>
              {fullDay(busiest.label)} was your biggest day.
            </p>
          ) : null}
        </>
      ),
    },
  ];

  if (data.people.length) {
    cards.push({
      key: "people",
      body: (
        <>
          <p className="eyebrow week-rise">Who came up</p>
          <ul className="mt-8 flex flex-wrap justify-center gap-3">
            {data.people.slice(0, 8).map((person, i) => (
              <li key={person.id} className="week-person" style={{ animationDelay: `${0.15 + i * 0.12}s` }}>
                <span className="font-display text-2xl">{person.name}</span>
                {person.relationship ? <span className="block text-xs text-muted-foreground">{person.relationship}</span> : null}
              </li>
            ))}
          </ul>
        </>
      ),
    });
  }

  if (data.going.length) {
    cards.push({
      key: "going",
      body: (
        <>
          <p className="eyebrow week-rise">Going on for you</p>
          <ul className="mt-8 space-y-3 text-left">
            {data.going.slice(0, 4).map((line, i) => (
              <li key={line} className="week-rise flex gap-3 text-lg text-foreground/90" style={{ animationDelay: `${0.15 + i * 0.15}s` }}>
                <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-iris-cyan" />
                {line}
              </li>
            ))}
          </ul>
        </>
      ),
    });
  }

  if (data.pattern) {
    cards.push({
      key: "pattern",
      body: (
        <>
          <p className="eyebrow week-rise">A pattern worth noticing</p>
          <p className="week-rise mt-6 font-display text-[clamp(1.8rem,5vw,2.6rem)] leading-tight text-balance" style={{ animationDelay: "0.15s" }}>
            {data.pattern.title}
          </p>
          <p className="week-rise mt-4 text-foreground/75" style={{ animationDelay: "0.45s" }}>
            {data.pattern.insight}
          </p>
        </>
      ),
    });
  }

  cards.push({
    key: "end",
    body: (
      <>
        <MirrorMark className="week-rise h-14 w-14" />
        <p className="week-rise mt-8 font-display text-[clamp(2rem,6vw,3rem)] leading-tight" style={{ animationDelay: "0.15s" }}>
          That was <em className="text-iridescent">your week.</em>
        </p>
        <p className="week-rise mt-3 text-muted-foreground" style={{ animationDelay: "0.35s" }}>
          The details are on the page behind this.
        </p>
      </>
    ),
  });
  return cards;
}

function fullDay(short: string) {
  return { Mon: "Monday", Tue: "Tuesday", Wed: "Wednesday", Thu: "Thursday", Fri: "Friday", Sat: "Saturday", Sun: "Sunday" }[short] ?? short;
}

export function PlayWeekButton({ onClick, className }: { onClick: () => void; className?: string }) {
  return (
    <button type="button" className={cn("btn-mirror !py-2.5", className)} onClick={onClick}>
      <Play className="h-4 w-4" /> Play your week
    </button>
  );
}
