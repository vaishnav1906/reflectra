import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "@/lib/motion";

/** A number that counts up (or down) to its new value instead of jumping. */
export function useCountUp(value: number, duration = 900): number {
  const [shown, setShown] = useState(() => (prefersReducedMotion() ? value : 0));
  const from = useRef(shown);

  useEffect(() => {
    if (prefersReducedMotion() || typeof requestAnimationFrame === "undefined") {
      setShown(value);
      from.current = value;
      return;
    }
    const start = performance.now();
    const origin = from.current;
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const next = origin + (value - origin) * eased;
      setShown(next);
      from.current = next;
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);

  return shown;
}

export function CountUp({ value, suffix = "" }: { value: number; suffix?: string }) {
  const shown = useCountUp(value);
  return (
    <span className="tabular-nums">
      {Math.round(shown).toLocaleString()}
      {suffix}
    </span>
  );
}
