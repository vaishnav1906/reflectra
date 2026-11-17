import { useEffect, useRef, useState } from "react";

/**
 * Reveal `target` a few characters per frame, so a reply that arrives from the
 * model in two or three big chunks still reads as being typed.
 *
 * About 55 characters a second when it is keeping up, faster when it falls behind
 * (it never lags more than ~0.4s), and it restarts from the shared beginning if the
 * text changes to something else (a draft that was replaced).
 */
export function useTypewriter(target: string | null) {
  const [shown, setShown] = useState("");
  const shownRef = useRef("");
  const targetRef = useRef(target ?? "");
  targetRef.current = target ?? "";

  useEffect(() => {
    if (!target) {
      shownRef.current = "";
      setShown("");
      return;
    }
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      shownRef.current = target;
      setShown(target);
      return;
    }
    // A different draft: keep only what the two have in common.
    let common = 0;
    const current = shownRef.current;
    while (common < current.length && common < target.length && current[common] === target[common]) common++;
    if (common < current.length) {
      shownRef.current = current.slice(0, common);
      setShown(shownRef.current);
    }

    let frame = 0;
    let last = performance.now();
    const step = (now: number) => {
      const goal = targetRef.current;
      const behind = goal.length - shownRef.current.length;
      if (behind <= 0) return;
      const elapsed = Math.min(100, now - last);
      last = now;
      const perMs = Math.max(0.055, behind / 400); // catch up within ~0.4s
      const next = Math.min(goal.length, shownRef.current.length + Math.max(1, Math.round(elapsed * perMs)));
      shownRef.current = goal.slice(0, next);
      setShown(shownRef.current);
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target]);

  return { shown, shownRef };
}
