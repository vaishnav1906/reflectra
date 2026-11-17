import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, X } from "lucide-react";
import { apiFetch } from "@/lib/api";

/**
 * "Does this ring true?" under a reflection.
 *
 * Spot on raises how sure it is, and the next rewrite keeps it while the messages
 * still support it. Not really hides it, and the next rewrite is told not to say it
 * again, along with what you said was off.
 */
export function ReflectionCheck({ id, initial }: { id: string; initial?: "agree" | "disagree" | null }) {
  const queryClient = useQueryClient();
  const [verdict, setVerdict] = useState(initial ?? null);
  const [asking, setAsking] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async (next: "agree" | "disagree") => {
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/feedback/reflection/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ verdict: next, note: note.trim() || null }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(typeof body?.detail === "string" ? body.detail : "Couldn't save that.");
      }
      setVerdict(next);
      setAsking(false);
      // A rejected reflection leaves the page; give the thanks a moment first.
      window.setTimeout(() => {
        void queryClient.invalidateQueries({ queryKey: ["reflections"] });
        void queryClient.invalidateQueries({ queryKey: ["portrait"] });
        void queryClient.invalidateQueries({ queryKey: ["system"] });
      }, next === "disagree" ? 1600 : 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save that.");
    } finally {
      setBusy(false);
    }
  };

  if (verdict === "disagree" && !asking) {
    return (
      <p className="mt-6 border-t border-white/5 pt-4 text-sm text-muted-foreground fade-in" role="status">
        Got it. This one's gone, and it won&apos;t come back in other words.
      </p>
    );
  }

  return (
    <div className="mt-6 border-t border-white/5 pt-4">
      {!asking ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-sm text-muted-foreground">{verdict === "agree" ? "You said this is spot on." : "Does this ring true?"}</span>
          <div className="flex gap-2">
            <button
              type="button"
              className="trait-check-btn"
              onClick={() => void send("agree")}
              disabled={busy || verdict === "agree"}
              aria-pressed={verdict === "agree"}
            >
              {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />} Spot on
            </button>
            <button type="button" className="trait-check-btn" onClick={() => setAsking(true)} disabled={busy}>
              <X className="h-3 w-3" /> Not really
            </button>
          </div>
        </div>
      ) : (
        <div className="fade-in">
          <label className="text-sm text-muted-foreground" htmlFor={`off-${id}`}>
            What&apos;s off about it? <span className="text-muted-foreground/60">(optional, helps the next rewrite)</span>
          </label>
          <input
            id={`off-${id}`}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={300}
            placeholder="e.g. that was one bad week, not a pattern"
            className="mt-2 w-full rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm outline-none focus:border-iris-violet/60"
          />
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" className="text-xs text-muted-foreground hover:text-foreground" onClick={() => setAsking(false)}>
              Cancel
            </button>
            <button type="button" className="btn-mirror !px-3 !py-1.5 !text-xs" onClick={() => void send("disagree")} disabled={busy}>
              {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : null} Hide it
            </button>
          </div>
        </div>
      )}
      {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
