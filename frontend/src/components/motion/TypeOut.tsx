import { useEffect, useState } from "react";
import { prefersReducedMotion } from "@/lib/motion";

/** Text that types itself out after `delay` ms, about 40 characters a second. */
export function TypeOut({ text, delay = 0 }: { text: string; delay?: number }) {
  const instant = prefersReducedMotion();
  const [count, setCount] = useState(instant ? text.length : 0);
  useEffect(() => {
    if (instant) return;
    let frame = 0;
    const start = window.setTimeout(() => {
      const began = performance.now();
      const step = (now: number) => {
        const next = Math.min(text.length, Math.round((now - began) * 0.04));
        setCount(next);
        if (next < text.length) frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
    }, delay);
    return () => {
      window.clearTimeout(start);
      cancelAnimationFrame(frame);
    };
  }, [text, delay, instant]);
  return (
    <>
      <span>{text.slice(0, count)}</span>
      {/* The rest keeps its space, so the layout doesn't jump while it types. */}
      <span className="invisible" aria-hidden="true">{text.slice(count)}</span>
    </>
  );
}
