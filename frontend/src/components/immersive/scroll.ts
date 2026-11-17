import { useEffect, useRef } from "react";

/** Scroll-scene utilities: one shared rAF-throttled listener drives every scene. */

export const clamp = (v: number, min = 0, max = 1) => Math.min(max, Math.max(min, v));
export const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
export const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
/** Map progress p onto 0..1 between start and end. */
export const span = (p: number, start: number, end: number) => clamp((p - start) / (end - start));

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

type Listener = () => void;
const listeners = new Set<Listener>();
let scheduled = false;

function schedule() {
  if (scheduled) return;
  scheduled = true;
  requestAnimationFrame(() => {
    scheduled = false;
    listeners.forEach((listener) => listener());
  });
}

function subscribe(listener: Listener) {
  if (listeners.size === 0) {
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
  }
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
    }
  };
}

/**
 * Attach to a tall section that contains a `position: sticky` stage.
 * `onFrame(p)` receives 0 when the section's top reaches the viewport top and
 * 1 when its bottom reaches the viewport bottom. With reduced motion it is
 * called once with 1 (the finished state).
 */
export function useScrollScene<T extends HTMLElement>(onFrame: (progress: number) => void) {
  const ref = useRef<T>(null);
  const callback = useRef(onFrame);
  callback.current = onFrame;

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const reduce = prefersReducedMotion();

    const update = () => {
      if (reduce) {
        callback.current(1);
        return;
      }
      const rect = element.getBoundingClientRect();
      const travel = rect.height - window.innerHeight;
      callback.current(travel > 0 ? clamp(-rect.top / travel) : rect.top < window.innerHeight ? 1 : 0);
    };

    update();
    return subscribe(update);
  }, []);

  return ref;
}

/** Adds the `in` class to `.reveal` elements inside the container as they enter the viewport. */
export function useRevealOnScroll<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const targets = Array.from(root.querySelectorAll<HTMLElement>(".reveal"));
    if (prefersReducedMotion() || !("IntersectionObserver" in window)) {
      targets.forEach((el) => el.classList.add("in"));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            observer.unobserve(entry.target);
          }
        }),
      { threshold: 0.18 },
    );
    targets.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);
  return ref;
}
