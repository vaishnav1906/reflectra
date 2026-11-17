import { useId } from "react";
import { cn } from "@/lib/utils";

/** Reflectra's mark: a thin iridescent oval mirror. */
export function MirrorMark({ className, breathing = false }: { className?: string; breathing?: boolean }) {
  const id = useId();
  return (
    <svg
      viewBox="0 0 40 40"
      className={cn("h-8 w-8 shrink-0", breathing && "mirror-breathe", className)}
      role="img"
      aria-label="Reflectra"
    >
      <defs>
        <linearGradient id={`${id}-ring`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="hsl(var(--iris-violet))" />
          <stop offset="50%" stopColor="hsl(var(--iris-cyan))" />
          <stop offset="100%" stopColor="hsl(var(--iris-peach))" />
        </linearGradient>
        <radialGradient id={`${id}-glass`} cx="50%" cy="38%" r="60%">
          <stop offset="0%" stopColor="hsl(var(--iris-violet))" stopOpacity="0.28" />
          <stop offset="100%" stopColor="hsl(var(--iris-violet))" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx="20" cy="20" rx="12" ry="16" fill={`url(#${id}-glass)`} />
      <ellipse cx="20" cy="20" rx="12" ry="16" fill="none" stroke={`url(#${id}-ring)`} strokeWidth="1.6" />
      <path d="M14.5 13.5c1.6-3 4-4.6 6.5-4.6" fill="none" stroke="white" strokeOpacity="0.55" strokeWidth="1.1" strokeLinecap="round" />
    </svg>
  );
}
