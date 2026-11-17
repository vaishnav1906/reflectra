import { useEffect, useState } from "react";
import { Check, Download, PlusSquare, Share, WifiOff, X } from "lucide-react";
import { Panel } from "@/components/portrait/PageShell";
import { useInstall } from "@/lib/install";
import { cn } from "@/lib/utils";

/** The steps for iPhone and iPad, where there's no install button to press for them. */
function IosSteps({ compact = false }: { compact?: boolean }) {
  return (
    <ol className={cn("space-y-2 text-sm text-foreground/85", compact && "text-[13px]")}>
      <li className="flex items-center gap-2">
        <span className="install-step">1</span> Tap <Share className="h-4 w-4 text-iris-cyan" aria-label="Share" /> <b>Share</b> in Safari
      </li>
      <li className="flex items-center gap-2">
        <span className="install-step">2</span> Choose <PlusSquare className="h-4 w-4 text-iris-cyan" aria-hidden="true" /> <b>Add to Home Screen</b>
      </li>
      <li className="flex items-center gap-2">
        <span className="install-step">3</span> Open Reflectra from its new icon
      </li>
    </ol>
  );
}

/** Settings: "Get the app". */
export function InstallCard() {
  const install = useInstall();
  const [justInstalled, setJustInstalled] = useState(false);

  return (
    <Panel title="Get the app">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
        <img src="/icons/icon-192.png" alt="" className="h-16 w-16 shrink-0 rounded-2xl" />
        <div className="min-w-0 flex-1 space-y-3">
          {install.installed || justInstalled ? (
            <p className="flex items-center gap-2 text-[15px] text-foreground">
              <Check className="h-4 w-4 text-iris-cyan" /> Reflectra is installed on this device.
            </p>
          ) : (
            <>
              <p className="text-[15px] leading-relaxed text-foreground/85">
                Put Reflectra on your home screen: it opens full screen like any other app, works offline, and can send you
                reminders. Nothing to download from a store.
              </p>
              {install.canPrompt ? (
                <button
                  type="button"
                  className="btn-mirror !py-2.5"
                  onClick={async () => setJustInstalled(await install.prompt())}
                >
                  <Download className="h-4 w-4" /> Install Reflectra
                </button>
              ) : install.ios ? (
                <IosSteps />
              ) : (
                <p className="text-sm text-muted-foreground">
                  Open this page in Chrome or Edge on Android or a computer and an install button appears here. On an iPhone or
                  iPad, open it in Safari.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </Panel>
  );
}

const NUDGE_KEY = "reflectra:install-nudge-dismissed";

/** Phones only: a small, dismissible suggestion to install. Never shown again once closed. */
export function InstallNudge() {
  const install = useInstall();
  const [dismissed, setDismissed] = useState(() => {
    try {
      return localStorage.getItem(NUDGE_KEY) === "1";
    } catch {
      return true;
    }
  });
  const [showSteps, setShowSteps] = useState(false);
  if (dismissed || install.installed || !(install.canPrompt || install.ios)) return null;

  const close = () => {
    setDismissed(true);
    try {
      localStorage.setItem(NUDGE_KEY, "1");
    } catch {
      /* fine: it just shows again next time */
    }
  };

  return (
    <div className="install-nudge md:hidden" role="region" aria-label="Install Reflectra">
      <div className="flex items-center gap-3">
        <img src="/icons/icon-192.png" alt="" className="h-10 w-10 shrink-0 rounded-xl" />
        <p className="min-w-0 flex-1 text-[13px] leading-snug text-foreground/90">
          <b>Add Reflectra to your home screen</b>
          <span className="block text-muted-foreground">Full screen, offline, with reminders.</span>
        </p>
        {install.canPrompt ? (
          <button type="button" className="btn-mirror !px-3 !py-1.5 !text-xs" onClick={async () => (await install.prompt()) && close()}>
            Install
          </button>
        ) : (
          <button type="button" className="btn-mirror !px-3 !py-1.5 !text-xs" onClick={() => setShowSteps((v) => !v)} aria-expanded={showSteps}>
            How
          </button>
        )}
        <button type="button" onClick={close} className="rounded-full p-1.5 text-muted-foreground hover:text-foreground" aria-label="Not now">
          <X className="h-4 w-4" />
        </button>
      </div>
      {showSteps ? (
        <div className="mt-3 border-t border-white/10 pt-3 fade-in">
          <IosSteps compact />
        </div>
      ) : null}
    </div>
  );
}

/** A quiet line at the top when the connection drops. */
export function OfflineBanner() {
  const [offline, setOffline] = useState(() => typeof navigator !== "undefined" && navigator.onLine === false);
  useEffect(() => {
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  if (!offline) return null;
  return (
    <div className="offline-banner" role="status">
      <WifiOff className="h-3.5 w-3.5" /> You're offline. Reflectra will catch up when you're back.
    </div>
  );
}
