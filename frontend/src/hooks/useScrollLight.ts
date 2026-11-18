import { RefObject, useEffect } from "react";
import { prefersReducedMotion } from "@/lib/motion";

function scrollParent(element: HTMLElement | null): HTMLElement | null {
  let node = element?.parentElement ?? null;
  while (node) {
    const overflow = getComputedStyle(node).overflowY;
    if (overflow === "auto" || overflow === "scroll") return node;
    node = node.parentElement;
  }
  return null;
}

/**
 * Light running down a list's thread as you scroll: sets `--lit` (px) on the list and
 * marks each `[data-thread-stop]` child it has reached with `data-lit`. With `fill`, the
 * matching element inside each stop (e.g. a numbered circle) also gets `--fill` from 0 to
 * 1 as the light passes through it. Writes to the DOM directly, so scrolling never
 * re-renders the page.
 */
export function useScrollLight(listRef: RefObject<HTMLElement>, deps: unknown[] = [], options: { fill?: string } = {}) {
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const scroller = scrollParent(list);
    const stops = Array.from(list.querySelectorAll<HTMLElement>("[data-thread-stop]"));
    const fills = options.fill ? stops.map((stop) => stop.querySelector<HTMLElement>(options.fill as string)) : [];
    if (prefersReducedMotion()) {
      list.style.setProperty("--lit", `${list.offsetHeight}px`);
      stops.forEach((stop) => stop.setAttribute("data-lit", ""));
      fills.forEach((el) => el?.style.setProperty("--fill", "1"));
      return;
    }
    let frame = 0;
    const update = () => {
      frame = 0;
      const box = list.getBoundingClientRect();
      const view = scroller?.getBoundingClientRect() ?? { top: 0, height: window.innerHeight };
      const line = view.top + view.height * 0.62; // where the light has got to on screen
      const lit = Math.max(0, Math.min(box.height, line - box.top));
      list.style.setProperty("--lit", `${lit}px`);
      stops.forEach((stop, i) => {
        const reached = stop.offsetTop <= lit;
        if (reached !== stop.hasAttribute("data-lit")) stop.toggleAttribute("data-lit", reached);
        const el = fills[i];
        if (el) {
          const top = stop.offsetTop + el.offsetTop;
          const fill = Math.max(0, Math.min(1, (lit - top) / Math.max(1, el.offsetHeight)));
          el.style.setProperty("--fill", fill.toFixed(3));
        }
      });
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    (scroller ?? window).addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      (scroller ?? window).removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      cancelAnimationFrame(frame);
    };
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
}
