import { useEffect, useRef } from "react";
import { ArrowDown } from "lucide-react";
import { clamp, easeInOut, easeOut, prefersReducedMotion, span, useScrollScene } from "./scroll";
import { themeRgb } from "@/lib/theme";

/**
 * Scene 1: "Thoughts become a mirror".
 * Drifting particles (stray thoughts) are pulled into an iridescent oval mirror
 * as you scroll; then the wordmark rises inside it with a rippling reflection.
 */

const THOUGHTS = [
  { text: "why do i always say yes", x: 14, y: 22 },
  { text: "maybe i'm just tired", x: 78, y: 18 },
  { text: "it's fine. i'm fine.", x: 84, y: 68 },
  { text: "i should've said something", x: 10, y: 60 },
  { text: "what if i'm not good enough", x: 70, y: 80 },
  { text: "3am again", x: 30, y: 84 },
  { text: "proud of myself today?", x: 48, y: 12 },
  { text: "who am i when no one's watching", x: 24, y: 40 },
];

let STOPS: [number, number, number][] = [
  [196, 186, 255], // iris violet
  [150, 232, 245], // ice cyan
  [255, 205, 176], // peach
];

function irisColor(t: number): [number, number, number] {
  const x = ((t % 1) + 1) % 1;
  const seg = x * STOPS.length;
  const i = Math.floor(seg) % STOPS.length;
  const f = seg - Math.floor(seg);
  const a = STOPS[i];
  const b = STOPS[(i + 1) % STOPS.length];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}

type Particle = {
  sx: number; sy: number; // scattered start (0..1)
  angle: number; jitter: number; inner: boolean; ix: number; iy: number;
  phase: number; size: number; color: string;
};

function makeParticles(count: number): Particle[] {
  STOPS = themeRgb(); // your colour on the landing page too
  let seed = 7;
  const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const gauss = () => {
    let u = 0, v = 0;
    while (!u) u = rand();
    while (!v) v = rand();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };
  return Array.from({ length: count }, () => {
    const angle = rand() * Math.PI * 2;
    const inner = rand() < 0.22;
    const r = Math.sqrt(rand());
    const theta = rand() * Math.PI * 2;
    const [cr, cg, cb] = irisColor(angle / (Math.PI * 2) + 0.15);
    return {
      sx: rand(), sy: rand(), angle, jitter: gauss(), inner,
      ix: r * Math.cos(theta) * 0.92, iy: r * Math.sin(theta) * 0.92,
      phase: rand() * Math.PI * 2, size: 0.7 + rand() * 1.5,
      color: `${Math.round(cr)},${Math.round(cg)},${Math.round(cb)}`,
    };
  });
}

export function HeroMirror({ onStart }: { onStart: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const progress = useRef(0);

  const sectionRef = useScrollScene<HTMLElement>((p) => {
    progress.current = p;
    const stage = stageRef.current;
    if (!stage) return;
    stage.style.setProperty("--intro", (1 - span(p, 0, 0.14)).toFixed(3));
    stage.style.setProperty("--thoughts", (1 - span(p, 0.1, 0.36)).toFixed(3));
    stage.style.setProperty("--pull", easeOut(span(p, 0.04, 0.4)).toFixed(3));
    stage.style.setProperty("--title", easeOut(span(p, 0.56, 0.78)).toFixed(3));
    stage.style.setProperty("--reflect", easeOut(span(p, 0.64, 0.86)).toFixed(3));
    stage.style.setProperty("--cta", easeOut(span(p, 0.76, 0.92)).toFixed(3));
    stage.style.setProperty("--cue", p > 0.02 ? "0" : "1");
    stage.dataset.live = p > 0.7 ? "true" : "false";
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    const stage = stageRef.current;
    if (!canvas || !stage) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduce = prefersReducedMotion();
    let width = 0, height = 0;
    let particles: Particle[] = [];
    let visible = true;
    let frame = 0;

    const layout = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = stage.clientWidth;
      height = stage.clientHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      particles = makeParticles(width < 760 ? 800 : 1400);
    };

    const draw = (time: number) => {
      const t = time / 1000;
      const p = reduce ? 1 : progress.current;
      const g = easeInOut(span(p, 0.04, 0.55));
      const sheen = span(p, 0.42, 0.75);
      const fadeOut = 1 - 0.45 * span(p, 0.9, 1);

      const portrait = width < 760;
      const cx = width / 2;
      const cy = height * (portrait ? 0.4 : 0.41);
      const rx = portrait ? Math.min(width * 0.34, height * 0.2) : Math.min(width * 0.22, height * 0.235);
      const ry = rx * 1.36;
      const sweep = t * 0.35;

      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = "lighter";

      for (const d of particles) {
        // Free drift (thoughts wandering)
        const fx = d.sx * width + Math.sin(t * 0.25 + d.phase) * 18;
        const fy = d.sy * height + Math.cos(t * 0.21 + d.phase) * 18;
        // Target on the mirror: rim or faint glass dust inside
        let tx: number, ty: number;
        if (d.inner) {
          tx = cx + d.ix * rx;
          ty = cy + d.iy * ry;
        } else {
          const wobble = 1 + d.jitter * 0.018 + Math.sin(t * 0.8 + d.phase) * 0.004;
          tx = cx + Math.cos(d.angle) * rx * wobble;
          ty = cy + Math.sin(d.angle) * ry * wobble;
        }
        const x = fx + (tx - fx) * g;
        const y = fy + (ty - fy) * g;

        // A slow highlight travels around the rim once the mirror has formed
        let glint = 0;
        if (!d.inner && sheen > 0) {
          const delta = Math.abs(((d.angle - sweep) % (Math.PI * 2) + Math.PI * 3) % (Math.PI * 2) - Math.PI);
          glint = Math.max(0, 1 - delta / 0.9) * sheen;
        }
        const twinkle = 0.55 + 0.45 * Math.sin(t * 1.6 + d.phase * 3);
        const base = d.inner ? 0.18 + 0.12 * g : 0.32 + 0.38 * g;
        const alpha = clamp((base * twinkle + glint * 0.7) * fadeOut, 0, 1);
        const size = d.size * (d.inner ? 0.8 : 1 + 0.5 * g + glint * 1.2);

        ctx.fillStyle = `rgba(${d.color},${alpha.toFixed(3)})`;
        if (size < 1.6) {
          ctx.fillRect(x - size / 2, y - size / 2, size, size);
        } else {
          ctx.beginPath();
          ctx.arc(x, y, size / 2, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // Soft glass bloom inside the mirror
      if (g > 0.3) {
        const bloom = ctx.createRadialGradient(cx, cy, 0, cx, cy, ry);
        bloom.addColorStop(0, `rgba(190,180,255,${(0.08 * span(g, 0.3, 1)).toFixed(3)})`);
        bloom.addColorStop(1, "rgba(190,180,255,0)");
        ctx.fillStyle = bloom;
        ctx.beginPath();
        ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";

      if (!reduce && visible) frame = requestAnimationFrame(draw);
    };

    layout();
    const onResize = () => {
      layout();
      if (reduce) draw(0);
    };
    window.addEventListener("resize", onResize);

    // Only animate while the hero is on screen.
    const observer = new IntersectionObserver(([entry]) => {
      const was = visible;
      visible = entry.isIntersecting;
      if (visible && !was && !reduce) frame = requestAnimationFrame(draw);
    });
    observer.observe(stage);

    frame = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return (
    <section ref={sectionRef} id="top" className="relative h-[360vh]" aria-label="Reflectra">
      <div
        ref={stageRef}
        className="hero-stage sticky top-0 h-[100svh] overflow-hidden"
        style={{
          background:
            "radial-gradient(70% 60% at 50% 42%, hsl(calc(var(--ink-h) + 7) calc(40% * var(--ink-k)) 12%) 0%, hsl(calc(var(--ink-h) + -5) calc(22% * var(--ink-k)) 5%) 55%, hsl(calc(var(--ink-h) + -5) calc(18% * var(--ink-k)) 3%) 100%)",
        }}
      >
        <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" aria-hidden="true" />

        {/* Stray thoughts drift toward the mirror and dissolve */}
        <div className="pointer-events-none absolute inset-0" aria-hidden="true">
          {THOUGHTS.map((thought) => (
            <span
              key={thought.text}
              className="hero-thought font-display italic"
              style={{
                // clamp keeps the centred label fully on screen on narrow viewports
                left: `clamp(var(--edge), calc(${thought.x}% + (50% - ${thought.x}%) * var(--pull, 0)), calc(100% - var(--edge)))`,
                top: `calc(${thought.y}% + (44% - ${thought.y}%) * var(--pull, 0))`,
              }}
            >
              {thought.text}
            </span>
          ))}
        </div>

        {/* Opening line */}
        <div className="hero-intro pointer-events-none absolute inset-x-0 top-1/2 -translate-y-1/2 px-6 text-center">
          <p className="eyebrow mb-5">A mirror for your mind</p>
          <h2 className="font-display text-[clamp(2.6rem,7vw,6.5rem)] leading-[0.95] text-balance">
            Every thought <em className="text-iridescent">leaves a trace.</em>
          </h2>
        </div>

        {/* Wordmark inside the mirror, with its reflection */}
        <div className="hero-title absolute inset-x-0 top-[41%] -translate-y-1/2 px-4 text-center">
          <h1 className="hero-word font-display">Reflectra</h1>
          <div className="hero-reflection font-display" aria-hidden="true">
            Reflectra
          </div>
        </div>

        <div className="hero-cta absolute inset-x-0 bottom-[clamp(28px,9vh,96px)] px-6 text-center">
          <p className="mx-auto max-w-xl text-[clamp(1rem,1.6vw,1.2rem)] text-foreground/75">
            An AI that listens long enough to understand you, then talks back like it&apos;s known you for years.
          </p>
          <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
            <button type="button" onClick={onStart} className="btn-mirror">
              Start reflecting
            </button>
            <a href="#conversation" className="btn-ghost-glass">
              See how it listens
            </a>
          </div>
        </div>

        <div className="hero-cue pointer-events-none absolute inset-x-0 bottom-8 flex flex-col items-center gap-2 text-foreground/50">
          <span className="eyebrow">Scroll</span>
          <ArrowDown className="h-4 w-4 animate-bounce" />
        </div>

        {/* Water-ripple filter for the reflection */}
        <svg className="absolute h-0 w-0" aria-hidden="true">
          <filter id="ripple">
            <feTurbulence type="fractalNoise" baseFrequency="0.012 0.09" numOctaves="1" seed="3">
              <animate attributeName="baseFrequency" dur="9s" values="0.012 0.09;0.016 0.11;0.012 0.09" repeatCount="indefinite" />
            </feTurbulence>
            <feDisplacementMap in="SourceGraphic" scale="9" />
          </filter>
        </svg>
      </div>
    </section>
  );
}
