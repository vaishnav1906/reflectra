import { useId } from "react";
import { Person, PersonGroup } from "@/hooks/useReflectra";
import { cn } from "@/lib/utils";

/**
 * Your people in orbit around your mirror.
 *
 * Distance is recency: whoever you talked about this week is on the inner ring,
 * this month the middle, everyone else the outer. Size is how often they come up.
 * Each kind of relationship has its own side of the sky and its own colour.
 */

export const GROUP_COLOR: Record<PersonGroup, string> = {
  family: "hsl(var(--iris-peach))",
  partner: "hsl(var(--trait-empathetic))",
  friends: "hsl(var(--iris-cyan))",
  work: "hsl(var(--iris-violet))",
  other: "hsl(var(--muted-foreground))",
};

export const GROUP_LABEL: Record<PersonGroup, string> = {
  family: "Family",
  partner: "Partner",
  friends: "Friends",
  work: "Work & study",
  other: "Others",
};

// Where each group sits around the mirror (degrees, 0 = right, clockwise).
const SECTOR: Record<PersonGroup, number> = { family: -90, friends: 0, work: 90, partner: 180, other: 135 };
const RINGS = [120, 175, 228];
const SIZE = 540;
const C = SIZE / 2;

function ringFor(person: Person, now = Date.now()) {
  if (!person.last_mentioned_at) return 2;
  const days = (now - new Date(person.last_mentioned_at).getTime()) / 86_400_000;
  return days <= 7 ? 0 : days <= 30 ? 1 : 2;
}

function initials(name: string) {
  const parts = name.trim().split(/\s+/);
  return (parts[0]?.[0] ?? "").toUpperCase() + (parts[1]?.[0] ?? "").toUpperCase();
}

export function layoutPeople(people: Person[]) {
  const byGroup = new Map<PersonGroup, Person[]>();
  for (const person of people) byGroup.set(person.group, [...(byGroup.get(person.group) ?? []), person]);
  const placed: { person: Person; x: number; y: number; r: number }[] = [];
  for (const [group, members] of byGroup) {
    const spread = Math.min(80, 22 * members.length); // degrees the group fans across
    members.forEach((person, i) => {
      const ring = ringFor(person);
      const offset = members.length === 1 ? 0 : -spread / 2 + (spread * i) / (members.length - 1);
      const jitter = ((i * 37) % 11) - 5; // keep same-ring neighbours from lining up
      const angle = ((SECTOR[group] + offset + jitter) * Math.PI) / 180;
      const radius = RINGS[ring] + (i % 2 ? 10 : -6);
      const r = 15 + Math.min(13, Math.log2(1 + person.mention_count) * 3);
      placed.push({ person, x: C + Math.cos(angle) * radius, y: C + Math.sin(angle) * radius, r });
    });
  }
  return placed;
}

export function PeopleOrbit({
  people,
  selectedId,
  onSelect,
  dimOthers = false,
}: {
  people: Person[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** You opened someone: the others fade back a little. */
  dimOthers?: boolean;
}) {
  const id = useId();
  const placed = layoutPeople(people);
  const now = Date.now();
  // Each person sways slowly along their ring, at their own pace.
  const sway = (i: number) =>
    ({ transformOrigin: `${C}px ${C}px`, animationDuration: `${16 + (i % 5) * 3}s`, animationDelay: `${-(i * 2.3)}s` }) as React.CSSProperties;
  // Arriving: everyone flies out from you to their place, one after another.
  const enter = (x: number, y: number, i: number) =>
    ({ "--fx": `${C - x}px`, "--fy": `${C - y}px`, animationDelay: `${0.1 + i * 0.06}s` }) as React.CSSProperties;
  // The person you open glides a little toward you.
  const focus = (x: number, y: number, selected: boolean) => {
    if (!selected) return undefined;
    const distance = Math.hypot(x - C, y - C) || 1;
    return { transform: `translate(${((C - x) / distance) * 16}px, ${((C - y) / distance) * 16}px)` };
  };

  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className={cn("people-orbit mx-auto w-full max-w-[540px]", dimOthers && selectedId && "has-selection")} role="group" aria-label="Your people">
      <defs>
        <radialGradient id={`${id}-glass`} cx="50%" cy="38%" r="60%">
          <stop offset="0%" stopColor="hsl(var(--iris-violet))" stopOpacity="0.4" />
          <stop offset="100%" stopColor="hsl(var(--iris-violet))" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`${id}-ring`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="hsl(var(--iris-violet))" />
          <stop offset="50%" stopColor="hsl(var(--iris-cyan))" />
          <stop offset="100%" stopColor="hsl(var(--iris-peach))" />
        </linearGradient>
      </defs>

      {RINGS.map((radius, i) => (
        <circle key={radius} cx={C} cy={C} r={radius} fill="none" stroke="hsl(0 0% 100% / 0.07)" strokeDasharray={i === 0 ? undefined : "2 6"} />
      ))}
      <text x={C} y={C - RINGS[0] - 8} textAnchor="middle" className="fill-muted-foreground/60 font-mono text-[9px] uppercase tracking-[0.2em]">
        this week
      </text>
      <text x={C} y={C - RINGS[2] - 8} textAnchor="middle" className="fill-muted-foreground/40 font-mono text-[9px] uppercase tracking-[0.2em]">
        a while ago
      </text>

      {/* lines from you to each person */}
      {placed.map(({ person, x, y }, i) => (
        <g key={`l-${person.id}`} className="orbit-sway" style={sway(i)}>
          <g className="orbit-enter" style={enter(x, y, i)}>
            <g className="orbit-focus" style={focus(x, y, person.id === selectedId)}>
              <line
                x1={C}
                y1={C}
                x2={x}
                y2={y}
                stroke={GROUP_COLOR[person.group]}
                strokeOpacity={person.id === selectedId ? 0.5 : 0.1}
                strokeWidth={person.id === selectedId ? 1.4 : 1}
              />
            </g>
          </g>
        </g>
      ))}

      {/* you */}
      <g className="people-you">
        <ellipse cx={C} cy={C} rx={38} ry={50} fill={`url(#${id}-glass)`} />
        <ellipse cx={C} cy={C} rx={38} ry={50} fill="none" stroke={`url(#${id}-ring)`} strokeWidth="1.6" />
        <text x={C} y={C + 4} textAnchor="middle" className="fill-foreground font-display text-[15px]">
          you
        </text>
      </g>

      {placed.map(({ person, x, y, r }, i) => {
        const selected = person.id === selectedId;
        const color = GROUP_COLOR[person.group];
        const justMentioned = person.last_mentioned_at ? now - new Date(person.last_mentioned_at).getTime() < 2 * 86_400_000 : false;
        return (
          <g key={person.id} className="orbit-sway" style={sway(i)}>
          <g className="orbit-enter" style={enter(x, y, i)}>
          <g className={cn("orbit-focus", selected && "is-focused")} style={focus(x, y, selected)}>
          <g
            className={cn("people-node", selected && "is-selected")}
            style={{ "--float-delay": `${(i % 7) * -0.9}s` } as React.CSSProperties}
            role="button"
            tabIndex={0}
            aria-pressed={selected}
            aria-label={`${person.name}${person.relationship ? `, ${person.relationship}` : ""}`}
            onClick={() => onSelect(person.id)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelect(person.id);
              }
            }}
          >
            {justMentioned ? (
              <circle cx={x} cy={y} r={r} fill="none" stroke={color} className="people-ripple" aria-hidden="true">
                <title>{`${person.name} came up in the last couple of days`}</title>
              </circle>
            ) : null}
            {selected ? <circle cx={x} cy={y} r={r + 7} fill="none" stroke={color} strokeOpacity="0.6" className="people-node-halo" /> : null}
            <circle cx={x} cy={y} r={r} style={{ fill: "hsl(var(--ink-h) calc(20% * var(--ink-k)) 8%)" }} stroke={color} strokeWidth={selected ? 2 : 1.3} />
            <circle cx={x} cy={y} r={r} fill={color} fillOpacity={selected ? 0.28 : 0.14} />
            {/* Turned back the other way, so the names stay upright while the ring sways. */}
            <g className="orbit-upright" style={{ ...sway(i), transformOrigin: `${x}px ${y}px` }}>
              <text x={x} y={y + 4} textAnchor="middle" className="pointer-events-none fill-foreground text-[11px] font-medium">
                {initials(person.name)}
              </text>
              <text x={x} y={y + r + 14} textAnchor="middle" className={cn("pointer-events-none text-[11px]", selected ? "fill-foreground" : "fill-muted-foreground")}>
                {person.name.length > 14 ? `${person.name.slice(0, 13)}…` : person.name}
              </text>
            </g>
          </g>
          </g>
          </g>
          </g>
        );
      })}
    </svg>
  );
}
