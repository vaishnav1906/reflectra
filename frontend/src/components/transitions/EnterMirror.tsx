import { useEffect, useId, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { themeRgb } from "@/lib/theme";
import "./transitions.css";

/**
 * Plays once when you go from the landing page into the app.
 *
 * Stray thoughts drift in and fall into the mirror while it draws itself, the
 * line underneath counts up the messages Reflectra actually remembers about you,
 * and then the glass opens and you step through into the app.
 *
 * Runs at least MIN_MS so it reads as an intro, never longer than MAX_MS, and a
 * click or Escape skips it.
 */

const MIN_MS = 2400;
const MAX_MS = 3400;
const LEAVE_MS = 850;

const THOUGHTS = [
  "why do i always say yes",
  "3am again",
  "it's fine. i'm fine.",
  "proud of myself today?",
  "i should've said something",
  "who am i when no one's watching",
  "maybe i'm just tired",
  "ok but why tho",
];

const DEFAULT_IRIS: [number, number, number][] = [
  [196, 186, 255],
  [150, 232, 245],
  [255, 205, 176],
];

let IRIS = DEFAULT_IRIS;

function iris(t: number) {
  const x = ((t % 1) + 1) % 1;
  const seg = x * IRIS.length;
  const i = Math.floor(seg) % IRIS.length;
  const f = seg - Math.floor(seg);
  const a = IRIS[i];
  const b = IRIS[(i + 1) % IRIS.length];
  return `rgb(${Math.round(a[0] + (b[0] - a[0]) * f)}, ${Math.round(a[1] + (b[1] - a[1]) * f)}, ${Math.round(a[2] + (b[2] - a[2]) * f)})`;
}

const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const reducedMotion = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function useParticleCanvas(ref: React.RefObject<HTMLCanvasElement>, leaving: boolean) {
  const leavingRef = useRef(leaving);
  leavingRef.current = leaving;

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || reducedMotion()) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    IRIS = themeRgb(); // your colour, not always violet
    let seed = 11;
    const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    const particles = Array.from({ length: 170 }, () => ({
      sx: rand(),
      sy: rand(),
      angle: rand() * Math.PI * 2,
      delay: rand() * 0.35,
      speed: 0.75 + rand() * 0.5,
      size: 0.6 + rand() * 1.6,
      color: iris(rand()),
      wobble: rand() * Math.PI * 2,
      inner: rand() < 0.25,
    }));

    let frame = 0;
    let width = 0;
    let height = 0;
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const start = performance.now();
    let leaveStart = 0;
    const draw = (now: number) => {
      const t = (now - start) / 1000;
      ctx.clearRect(0, 0, width, height);
      const cx = width / 2;
      const cy = height / 2 - Math.min(60, height * 0.06);
      const rx = Math.min(110, width * 0.13);
      const ry = rx * 1.33;
      if (leavingRef.current && !leaveStart) leaveStart = now;
      const burst = leaveStart ? Math.min(1, (now - leaveStart) / 700) : 0;

      for (const p of particles) {
        const progress = easeInOut(Math.min(1, Math.max(0, (t * p.speed - p.delay) / 1.5)));
        // Spiral in: the angle turns as the particle travels toward the rim.
        const spin = (1 - progress) * 2.4;
        const a = p.angle + spin + t * 0.25;
        const rimScale = p.inner ? 0.35 + 0.5 * ((p.wobble % 1) + 0.2) : 1 + Math.sin(t * 2 + p.wobble) * 0.035;
        const tx = cx + Math.cos(a) * rx * rimScale;
        const ty = cy + Math.sin(a) * ry * rimScale;
        let x = p.sx * width + (tx - p.sx * width) * progress;
        let y = p.sy * height + (ty - p.sy * height) * progress;
        if (burst) {
          // Stepping through: everything rushes outward past you.
          const dx = x - cx;
          const dy = y - cy;
          x = cx + dx * (1 + burst * 6);
          y = cy + dy * (1 + burst * 6);
        }
        const alpha = (0.25 + 0.75 * progress) * (1 - burst);
        ctx.globalAlpha = alpha;
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(x, y, p.size * (1 + progress * 0.4), 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
    };
  }, [ref]);
}

function useCountUp(target: number | null, startAfterMs: number, durationMs = 900) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!target) return;
    let frame = 0;
    const timer = window.setTimeout(() => {
      const start = performance.now();
      const step = (now: number) => {
        const t = Math.min(1, (now - start) / durationMs);
        setValue(Math.round(target * (1 - Math.pow(1 - t, 3))));
        if (t < 1) frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
    }, startAfterMs);
    return () => {
      window.clearTimeout(timer);
      cancelAnimationFrame(frame);
    };
  }, [target, startAfterMs, durationMs]);
  return value;
}

export function EnterMirror({ onDone }: { onDone: () => void }) {
  const gradientId = useId();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { user } = useAuth();
  const [messages, setMessages] = useState<number | null>(null);
  const [phase, setPhase] = useState(0);
  const [leaving, setLeaving] = useState(false);
  const leavingRef = useRef(false);
  const mountedAt = useRef(performance.now());
  const doneRef = useRef(onDone);
  doneRef.current = onDone;
  const quick = reducedMotion();

  useParticleCanvas(canvasRef, leaving);
  const counted = useCountUp(messages && messages > 0 ? messages : null, 700);
  const firstName = (user?.display_name || "").trim().split(/\s+/)[0] || "";
  const name = firstName ? firstName.charAt(0).toUpperCase() + firstName.slice(1) : "";

  // What it really knows about you: how many of your messages it remembers.
  useEffect(() => {
    if (!user?.id) return;
    let cancelled = false;
    apiFetch(`/api/user/system-state?user_id=${encodeURIComponent(user.id)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        // -1: couldn't find out (server still waking up). Never claim "nothing yet" then.
        if (!cancelled) setMessages(typeof data?.messages === "number" ? data.messages : -1);
      })
      .catch(() => !cancelled && setMessages(-1));
    return () => {
      cancelled = true;
    };
  }, [user?.id]);

  const leave = () => {
    if (leavingRef.current) return;
    leavingRef.current = true;
    setLeaving(true);
    window.setTimeout(() => doneRef.current(), quick ? 300 : LEAVE_MS);
  };

  useEffect(() => {
    const timers = [window.setTimeout(() => setPhase(1), 750), window.setTimeout(() => setPhase(2), 1750)];
    const hardStop = window.setTimeout(leave, quick ? 900 : MAX_MS);
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && leave();
    window.addEventListener("keydown", onKey);
    return () => {
      [...timers, hardStop].forEach((t) => window.clearTimeout(t));
      window.removeEventListener("keydown", onKey);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Leave as soon as the intro has had its moment and the numbers are in.
  useEffect(() => {
    if (messages === null) return;
    const elapsed = performance.now() - mountedAt.current;
    const wait = window.setTimeout(leave, Math.max(0, (quick ? 600 : MIN_MS) - elapsed));
    return () => window.clearTimeout(wait);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages]);

  const lines =
    messages === -1 || messages === null
      ? [
          { line: "Polishing the glass", sub: "Reflectra" },
          { line: "Remembering what you've said", sub: "every conversation, in one place" },
          { line: name ? `Hey, ${name}.` : "There you are.", sub: "step through" },
        ]
      : messages > 0
      ? [
          { line: "Polishing the glass", sub: "Reflectra" },
          { line: `Remembering ${counted.toLocaleString()} messages`, sub: "everything you've said here" },
          { line: name ? `Hey, ${name}.` : "There you are.", sub: "step through" },
        ]
      : [
          { line: "Polishing the glass", sub: "Reflectra" },
          { line: "A clean mirror", sub: "nothing on it yet. that's where you come in" },
          { line: name ? `Hey, ${name}.` : "Hello, you.", sub: "step through" },
        ];
  const current = lines[Math.min(phase, lines.length - 1)];

  return (
    <div
      className={`enter-mirror${leaving ? " is-leaving" : ""}`}
      onClick={leave}
      role="status"
      aria-live="polite"
      aria-label="Opening Reflectra"
    >
      <canvas ref={canvasRef} aria-hidden="true" />

      {!quick
        ? THOUGHTS.map((thought, i) => {
            const angle = (i / THOUGHTS.length) * Math.PI * 2 + 0.4;
            return (
              <span
                key={thought}
                aria-hidden="true"
                className="enter-thought"
                style={
                  {
                    "--from-x": `${Math.cos(angle) * 42}vw`,
                    "--from-y": `${Math.sin(angle) * 38}vh`,
                    animationDelay: `${i * 70}ms`,
                  } as React.CSSProperties
                }
              >
                {thought}
              </span>
            );
          })
        : null}

      <div className="enter-stage">
        <div className="enter-glass" aria-hidden="true">
          <svg viewBox="0 0 120 160">
            <defs>
              <linearGradient id={`${gradientId}-ring`} x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="hsl(var(--iris-violet))" />
                <stop offset="50%" stopColor="hsl(var(--iris-cyan))" />
                <stop offset="100%" stopColor="hsl(var(--iris-peach))" />
              </linearGradient>
              <radialGradient id={`${gradientId}-glass`} cx="50%" cy="36%" r="65%">
                <stop offset="0%" stopColor="hsl(var(--iris-violet))" stopOpacity="0.42" />
                <stop offset="60%" stopColor="hsl(var(--iris-cyan))" stopOpacity="0.08" />
                <stop offset="100%" stopColor="hsl(var(--iris-violet))" stopOpacity="0" />
              </radialGradient>
            </defs>
            <ellipse className="enter-ring is-outer" cx="60" cy="80" rx="58" ry="78" stroke={`url(#${gradientId}-ring)`} />
            <ellipse className="enter-glass-fill" cx="60" cy="80" rx="48" ry="66" fill={`url(#${gradientId}-glass)`} />
            <ellipse className="enter-ring" cx="60" cy="80" rx="48" ry="66" stroke={`url(#${gradientId}-ring)`} />
            <path
              className="enter-glass-fill"
              d="M38 46c6-12 15-18 25-18"
              fill="none"
              stroke="white"
              strokeOpacity="0.5"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
          <div className="enter-sheen" />
        </div>

        <div className="enter-copy">
          <p key={`l${phase}`} className="enter-line">
            {current.line}
          </p>
          <p key={`s${phase}`} className="enter-sub">
            {current.sub}
          </p>
        </div>
      </div>

      <span className="enter-skip" aria-hidden="true">
        click to skip
      </span>
    </div>
  );
}

const FLAG = "reflectra:enter";

/**
 * Ask the app to play the entrance on its next load (set right before navigating in).
 * `waitMs` is for a trip out and back, like Google sign-in, which can take a while:
 * the entrance then stays due for that much longer.
 */
export function requestEntrance(waitMs = 0) {
  try {
    sessionStorage.setItem(FLAG, String(Date.now() + waitMs));
  } catch {
    /* storage blocked: no intro, nothing else changes */
  }
}

/** Was the entrance requested in the last few seconds? (Read-only: see clearEntranceRequest.) */
export function entranceRequested(): boolean {
  try {
    const at = Number(sessionStorage.getItem(FLAG) || 0);
    return Boolean(at) && Date.now() - at < 15000;
  } catch {
    return false;
  }
}

/** Mark the entrance as played, so a reload doesn't play it again. */
export function clearEntranceRequest() {
  try {
    sessionStorage.removeItem(FLAG);
  } catch {
    /* nothing to clear */
  }
}
