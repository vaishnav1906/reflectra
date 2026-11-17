import { flushSync } from "react-dom";

/** True when the person asked their device for less motion. */
export function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
  } catch {
    return false;
  }
}

type TransitionDoc = Document & {
  startViewTransition?: (update: () => void) => { ready: Promise<void>; finished: Promise<void> };
};

/**
 * Change the colours with a ripple: the new colours spread out in a circle from
 * (x, y) across the whole screen. Falls back to an instant change where the browser
 * can't do it, or when reduced motion is on.
 */
export function withColourRipple(change: () => void, x: number, y: number) {
  const doc = document as TransitionDoc;
  if (!doc.startViewTransition || prefersReducedMotion()) {
    change();
    return;
  }
  const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
  const root = document.documentElement;
  root.classList.add("colour-ripple");
  const transition = doc.startViewTransition(() => flushSync(change));
  transition.ready
    .then(() => {
      root.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 700, easing: "cubic-bezier(0.16, 1, 0.3, 1)", pseudoElement: "::view-transition-new(root)" },
      );
    })
    .catch(() => undefined);
  transition.finished.finally(() => root.classList.remove("colour-ripple")).catch(() => undefined);
}

/** Centre of an element on screen, for starting a ripple there. */
export function centreOf(element: Element | null): { x: number; y: number } {
  const box = element?.getBoundingClientRect();
  return box ? { x: box.left + box.width / 2, y: box.top + box.height / 2 } : { x: window.innerWidth / 2, y: window.innerHeight / 2 };
}

/**
 * Erasing: the mirror fogs over, then wipes clean. Resolves when it is clear, so the
 * caller can move on; the overlay fades away by itself afterwards.
 */
export function playEraseFog(): Promise<void> {
  if (prefersReducedMotion() || typeof document === "undefined") return Promise.resolve();
  const overlay = document.createElement("div");
  overlay.className = "erase-fog";
  overlay.setAttribute("role", "status");
  overlay.innerHTML = `
    <div class="erase-fog-mirror" aria-hidden="true">
      <svg viewBox="0 0 120 160"><ellipse cx="60" cy="80" rx="54" ry="74" fill="none" stroke="currentColor" stroke-width="2"/></svg>
      <span class="erase-fog-mist"></span>
      <span class="erase-fog-wipe"></span>
    </div>
    <p class="erase-fog-text">Wiped clean.</p>`;
  document.body.appendChild(overlay);
  window.setTimeout(() => overlay.classList.add("is-leaving"), 2000);
  window.setTimeout(() => overlay.remove(), 2600);
  return new Promise((resolve) => window.setTimeout(resolve, 1900));
}
