import { useId } from "react";
import { PortraitTrait, TRAIT_COLOR } from "@/hooks/useReflectra";
import { useGrow } from "./useGrow";

/**
 * "The shape of you": the four trait scores drawn as one soft, iridescent form.
 * Each axis runs from the trait's low pole (centre) to its high pole (edge).
 * The faint outer halo is uncertainty: it tightens as confidence grows.
 */

const SIZE = 420;
const C = SIZE / 2;
const R = 150;
const ANGLES = [-90, 0, 90, 180].map((deg) => (deg * Math.PI) / 180);

function point(angle: number, value: number): [number, number] {
  const radius = R * (0.18 + 0.82 * Math.max(0, Math.min(1, value)));
  return [C + Math.cos(angle) * radius, C + Math.sin(angle) * radius];
}

/** Closed Catmull-Rom spline through the points, as an SVG path. */
function smoothPath(points: [number, number][], tension = 0.5): string {
  const n = points.length;
  let d = `M ${points[0][0].toFixed(1)} ${points[0][1].toFixed(1)}`;
  for (let i = 0; i < n; i++) {
    const p0 = points[(i - 1 + n) % n];
    const p1 = points[i];
    const p2 = points[(i + 1) % n];
    const p3 = points[(i + 2) % n];
    const c1 = [p1[0] + ((p2[0] - p0[0]) * tension) / 3, p1[1] + ((p2[1] - p0[1]) * tension) / 3];
    const c2 = [p2[0] - ((p3[0] - p1[0]) * tension) / 3, p2[1] - ((p3[1] - p1[1]) * tension) / 3];
    d += ` C ${c1[0].toFixed(1)} ${c1[1].toFixed(1)}, ${c2[0].toFixed(1)} ${c2[1].toFixed(1)}, ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
  }
  return d + " Z";
}

/** Eight control points (axes + diagonals) so the form reads as a shape, not a kite. */
function shape(values: number[]): [number, number][] {
  const points: [number, number][] = [];
  for (let i = 0; i < 4; i++) {
    const next = (i + 1) % 4;
    points.push(point(ANGLES[i], values[i]));
    const mid = ANGLES[i] + Math.PI / 4;
    points.push(point(mid, ((values[i] + values[next]) / 2) * 0.86));
  }
  return points;
}

export function TraitShape({ traits }: { traits: PortraitTrait[] }) {
  const id = useId();
  const grow = useGrow();

  const ordered = traits.slice(0, 4);
  if (ordered.length < 4) return null;
  // Starts as a neutral circle (all 50) and settles into the person's shape.
  const values = ordered.map((t) => 0.5 + (t.score - 0.5) * grow);
  const halo = ordered.map((t, i) => Math.min(1, values[i] + (1 - t.confidence) * 0.22));

  const labelAnchor = ["middle", "start", "middle", "end"] as const;
  const labelOffset: [number, number][] = [[0, -22], [18, 4], [0, 34], [-18, 4]];

  return (
    <svg
      viewBox={`-96 -30 ${SIZE + 192} ${SIZE + 60}`}
      className="trait-shape mx-auto w-full max-w-[520px]"
      role="img"
      aria-label={"Trait scores: " + ordered.map((t) => `${t.name} ${Math.round(t.score * 100)} out of 100`).join(", ")}
    >
      <defs>
        <linearGradient id={`${id}-fill`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="hsl(var(--iris-violet))" stopOpacity="0.55" />
          <stop offset="50%" stopColor="hsl(var(--iris-cyan))" stopOpacity="0.35" />
          <stop offset="100%" stopColor="hsl(var(--iris-peach))" stopOpacity="0.5" />
        </linearGradient>
        <linearGradient id={`${id}-stroke`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="hsl(var(--iris-violet))" />
          <stop offset="50%" stopColor="hsl(var(--iris-cyan))" />
          <stop offset="100%" stopColor="hsl(var(--iris-peach))" />
        </linearGradient>
        <filter id={`${id}-glow`} x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="14" />
        </filter>
      </defs>

      {/* rings at 0 / 50 / 100 */}
      {[0, 0.5, 1].map((ring) => (
        <circle key={ring} cx={C} cy={C} r={R * (0.18 + 0.82 * ring)} fill="none" stroke="hsl(0 0% 100% / 0.07)" strokeDasharray={ring === 0.5 ? "3 5" : undefined} />
      ))}
      {ANGLES.map((angle, i) => {
        const [x, y] = point(angle, 1);
        return <line key={i} x1={C} y1={C} x2={x} y2={y} stroke="hsl(0 0% 100% / 0.06)" />;
      })}

      {/* uncertainty halo, glow, then the shape itself */}
      <path d={smoothPath(shape(halo))} fill={`url(#${id}-fill)`} opacity="0.22" />
      <path d={smoothPath(shape(values))} fill={`url(#${id}-fill)`} filter={`url(#${id}-glow)`} opacity="0.7" />
      <path d={smoothPath(shape(values))} fill={`url(#${id}-fill)`} stroke={`url(#${id}-stroke)`} strokeWidth="1.6" />

      {ordered.map((trait, i) => {
        const [x, y] = point(ANGLES[i], values[i]);
        const [lx, ly] = point(ANGLES[i], 1);
        return (
          <g key={trait.key}>
            <circle cx={x} cy={y} r={5} fill={TRAIT_COLOR[trait.key]} />
            <circle cx={x} cy={y} r={11} fill={TRAIT_COLOR[trait.key]} opacity="0.18" />
            <text x={lx + labelOffset[i][0]} y={ly + labelOffset[i][1]} textAnchor={labelAnchor[i]} className="fill-foreground text-[13px] font-medium">
              {trait.name.replace("Emotional expressiveness", "Expressiveness")}
            </text>
            <text x={lx + labelOffset[i][0]} y={ly + labelOffset[i][1] + 16} textAnchor={labelAnchor[i]} className="fill-muted-foreground font-mono text-[10px] uppercase tracking-widest">
              {Math.round(trait.score * 100)} · {trait.score >= 0.5 ? trait.high : trait.low}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
