import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { PortraitTrait, TRAIT_COLOR } from "@/hooks/useReflectra";
import { cn } from "@/lib/utils";

/**
 * "Is this you?" under a trait reading.
 *
 * Yes makes Reflectra more sure. Not quite opens a slider for where you'd put
 * yourself; before saving it shows exactly what will change (the server works it out
 * with the same rule it then applies). Your view counts like ~15 of your messages,
 * so what you actually say in chat keeps the final word.
 */

type Preview = {
  previous_score: number;
  new_score: number;
  previous_confidence: number;
  new_confidence: number;
  counts_as_messages: number;
};

const pct = (value: number) => Math.round(value * 100);

export function TraitCheck({ trait, onPreview }: { trait: PortraitTrait; onPreview?: (score: number | null) => void }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(pct(trait.score));
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const color = TRAIT_COLOR[trait.key];
  const verdict = trait.feedback?.verdict;

  const send = async (body: { verdict: "agree" | "disagree"; self_score?: number; dry_run?: boolean }) => {
    const res = await apiFetch(`/api/feedback/trait/${trait.key}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Couldn't save that.");
    return data as Preview;
  };

  const agree = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await send({ verdict: "agree" });
      setDone(
        result.new_confidence > result.previous_confidence
          ? `Thanks. It's more sure now (${pct(result.previous_confidence)}% → ${pct(result.new_confidence)}%).`
          : "Thanks. Already noted today.",
      );
      void queryClient.invalidateQueries({ queryKey: ["portrait"] });
      void queryClient.invalidateQueries({ queryKey: ["system"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save that.");
    } finally {
      setBusy(false);
    }
  };

  const previewAt = async (next: number) => {
    try {
      setPreview(await send({ verdict: "disagree", self_score: next / 100, dry_run: true }));
    } catch {
      setPreview(null);
    }
  };

  const apply = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await send({ verdict: "disagree", self_score: value / 100 });
      setDone(`Moved ${pct(result.previous_score)} → ${pct(result.new_score)}. What you say in chat will keep refining it.`);
      setOpen(false);
      onPreview?.(null);
      void queryClient.invalidateQueries({ queryKey: ["portrait"] });
      void queryClient.invalidateQueries({ queryKey: ["system"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save that.");
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <p className="mt-4 flex items-start gap-2 border-t border-white/5 pt-3 text-xs text-muted-foreground fade-in" role="status">
        <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-iris-cyan" /> {done}
      </p>
    );
  }

  return (
    <div className="mt-4 border-t border-white/5 pt-3">
      {!open ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">
            {verdict === "agree" ? "You said this is you." : verdict === "disagree" ? "You corrected this." : "Is this you?"}
          </span>
          <div className="flex gap-1.5">
            <button type="button" onClick={() => void agree()} disabled={busy} className="trait-check-btn" aria-label={`Yes, ${trait.name} reads me right`}>
              {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />} Yes
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(true);
                setValue(pct(trait.score));
                setPreview(null);
                onPreview?.(trait.score);
              }}
              disabled={busy}
              className="trait-check-btn"
            >
              Not quite
            </button>
          </div>
        </div>
      ) : (
        <div className="fade-in">
          <p className="text-xs text-muted-foreground">Where would you put yourself?</p>
          <input
            type="range"
            min={0}
            max={100}
            value={value}
            onChange={(event) => {
              setValue(Number(event.target.value));
              onPreview?.(Number(event.target.value) / 100);
            }}
            onPointerUp={() => void previewAt(value)}
            onKeyUp={() => void previewAt(value)}
            onBlur={() => void previewAt(value)}
            className="trait-slider mt-3 w-full"
            style={{ "--trait": color } as React.CSSProperties}
            aria-label={`Where you'd put yourself on ${trait.name}, from ${trait.low} to ${trait.high}`}
          />
          <div className="mt-1 flex justify-between font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            <span>{trait.low}</span>
            <span style={{ color }}>{value}</span>
            <span>{trait.high}</span>
          </div>
          <p className="mt-3 min-h-[2.5em] text-xs leading-relaxed text-muted-foreground">
            {preview
              ? `It'll move ${pct(preview.previous_score)} → ${pct(preview.new_score)} and be ${
                  preview.new_confidence < preview.previous_confidence ? "less" : "more"
                } sure for now (${pct(preview.previous_confidence)}% → ${pct(preview.new_confidence)}%). Your view counts like ${preview.counts_as_messages} of your messages.`
              : "Drag to where you think you are. Your shape follows you."}
          </p>
          <div className="mt-2 flex justify-end gap-2">
            <button type="button" className="text-xs text-muted-foreground hover:text-foreground" onClick={() => {
                setOpen(false);
                onPreview?.(null);
              }}>
              Cancel
            </button>
            <button type="button" className={cn("btn-mirror !px-3 !py-1.5 !text-xs")} disabled={busy || !preview} onClick={() => void apply()}>
              {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : null} Save
            </button>
          </div>
        </div>
      )}
      {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
