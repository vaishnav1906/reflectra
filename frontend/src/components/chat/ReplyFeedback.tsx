import { useState } from "react";
import { Check, ThumbsDown, ThumbsUp } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Thumbs under a reply. Up is one tap. Down asks what missed (optional), and the
 * next replies are told to fix it. In Mirror, a thumbs up means "this sounds like
 * me" and that reply becomes an example of your voice.
 */

export type ReplyMode = "reflection" | "mirror";

const REASONS: Record<ReplyMode, { reason: string; label: string }[]> = {
  reflection: [
    { reason: "too_long", label: "Too long" },
    { reason: "missed_point", label: "Missed the point" },
    { reason: "wrong_about_me", label: "Got me wrong" },
    { reason: "too_preachy", label: "Too preachy" },
    { reason: "unrelated", label: "Brought up old stuff" },
  ],
  mirror: [
    { reason: "not_my_voice", label: "Doesn't sound like me" },
    { reason: "too_long", label: "Too long" },
    { reason: "missed_point", label: "Missed the point" },
    { reason: "wrong_about_me", label: "Got me wrong" },
    { reason: "unrelated", label: "Brought up old stuff" },
  ],
};

type Verdict = "up" | "down" | null;

export function ReplyFeedback({
  messageId,
  mode,
  initial = null,
  initialReasons = [],
  onChange,
}: {
  messageId: string;
  mode: ReplyMode;
  initial?: Verdict;
  initialReasons?: string[];
  onChange?: (verdict: Verdict, reasons: string[]) => void;
}) {
  const [verdict, setVerdict] = useState<Verdict>(initial);
  const [reasons, setReasons] = useState<string[]>(initialReasons);
  const [asking, setAsking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [thanks, setThanks] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const [sparks, setSparks] = useState(0); // bumps to replay the burst

  const send = async (next: "up" | "down" | "clear", chosen: string[] = []) => {
    setSaving(true);
    setError(false);
    try {
      const res = await apiFetch(`/api/feedback/reply/${messageId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ verdict: next, reasons: chosen }),
      });
      if (!res.ok) throw new Error(String(res.status));
      const stored: Verdict = next === "clear" ? null : next;
      if (next === "up") setSparks((n) => n + 1);
      setVerdict(stored);
      setReasons(chosen);
      onChange?.(stored, chosen);
      setThanks(
        next === "up"
          ? mode === "mirror"
            ? "Noted: that's you. It'll copy that."
            : "Glad that landed."
          : next === "down"
            ? chosen.length
              ? "Got it. The next replies will adjust."
              : "Noted."
            : null,
      );
      window.setTimeout(() => setThanks(null), 2600);
    } catch {
      setError(true);
    } finally {
      setSaving(false);
      setAsking(false);
    }
  };

  const toggle = (reason: string) =>
    setReasons((current) => (current.includes(reason) ? current.filter((r) => r !== reason) : [...current, reason]));

  return (
    <div className="reply-feedback">
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => void send(verdict === "up" ? "clear" : "up")}
          disabled={saving}
          aria-pressed={verdict === "up"}
          aria-label={mode === "mirror" ? "Sounds like me" : "Good reply"}
          title={mode === "mirror" ? "Sounds like me" : "Good reply"}
          className={cn("reply-feedback-btn", verdict === "up" && "is-on")}
        >
          <ThumbsUp className="h-3.5 w-3.5" />
          {sparks > 0 && verdict === "up" ? (
            <span key={sparks} className="reply-sparks" aria-hidden="true">
              {Array.from({ length: 8 }, (_, i) => (
                <span key={i} style={{ "--spark-angle": `${i * 45 + 20}deg` } as React.CSSProperties} />
              ))}
            </span>
          ) : null}
        </button>
        <button
          type="button"
          onClick={() => (verdict === "down" ? void send("clear") : setAsking((open) => !open))}
          disabled={saving}
          aria-pressed={verdict === "down"}
          aria-expanded={asking}
          aria-label={mode === "mirror" ? "Not quite me" : "Not a good reply"}
          title="Not quite"
          className={cn("reply-feedback-btn", verdict === "down" && "is-on")}
        >
          <ThumbsDown className="h-3.5 w-3.5" />
        </button>
        {thanks ? <span className="ml-1 text-[11px] text-muted-foreground fade-in">{thanks}</span> : null}
        {error ? <span className="ml-1 text-[11px] text-destructive">Couldn't save that.</span> : null}
      </div>

      {asking ? (
        <div className="reply-feedback-panel reply-unfold" role="group" aria-label="What missed?">
          <p className="mb-2 text-xs text-muted-foreground">What missed? (optional)</p>
          <div className="flex flex-wrap gap-1.5">
            {REASONS[mode].map(({ reason, label }, index) => (
              <button
                key={reason}
                type="button"
                style={{ animationDelay: `${0.12 + index * 0.05}s` }}
                onClick={() => toggle(reason)}
                aria-pressed={reasons.includes(reason)}
                className={cn("reply-reason", reasons.includes(reason) && "is-on")}
              >
                {reasons.includes(reason) ? <Check className="h-3 w-3" /> : null}
                {label}
              </button>
            ))}
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" className="text-xs text-muted-foreground hover:text-foreground" onClick={() => setAsking(false)}>
              Cancel
            </button>
            <button type="button" className="btn-mirror !px-3 !py-1.5 !text-xs" disabled={saving} onClick={() => void send("down", reasons)}>
              Send
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
