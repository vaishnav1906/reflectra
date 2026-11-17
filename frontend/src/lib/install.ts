import { useEffect, useReducer } from "react";

/**
 * Installing Reflectra to the home screen.
 *
 * Android and desktop Chrome/Edge fire `beforeinstallprompt`, which we keep so a
 * button can open the real install dialog. iPhone and iPad have no such event:
 * people add it from the Share menu, so we show them how instead.
 */

type InstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

let deferred: InstallPromptEvent | null = null;
let installedNow = false;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((listener) => listener());

/** Call once at startup, before React renders (the event can fire very early). */
export function setupInstall() {
  if (typeof window === "undefined") return;
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferred = event as InstallPromptEvent;
    notify();
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    installedNow = true;
    notify();
  });
}

export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia?.("(display-mode: standalone)").matches === true ||
    (navigator as unknown as { standalone?: boolean }).standalone === true
  );
}

/** iPhone or iPad (iPads report themselves as Macs, but have touch). */
export function isIos(): boolean {
  if (typeof navigator === "undefined") return false;
  return /iphone|ipad|ipod/i.test(navigator.userAgent) || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
}

export function useInstall() {
  const [, rerender] = useReducer((n: number) => n + 1, 0);
  useEffect(() => {
    listeners.add(rerender);
    return () => {
      listeners.delete(rerender);
    };
  }, []);
  return {
    installed: isStandalone() || installedNow,
    canPrompt: Boolean(deferred),
    ios: isIos(),
    /** Opens the browser's own install dialog. Resolves true if they installed. */
    async prompt(): Promise<boolean> {
      if (!deferred) return false;
      const event = deferred;
      deferred = null;
      notify();
      await event.prompt();
      const { outcome } = await event.userChoice;
      return outcome === "accepted";
    },
  };
}

/** Register the service worker in production (offline shell + notifications). */
export function registerServiceWorker() {
  if (!import.meta.env.PROD || typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => undefined);
  });
}
