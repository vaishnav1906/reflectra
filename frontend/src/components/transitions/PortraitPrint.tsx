import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, Download, FileText, RotateCcw, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { usePortrait } from "@/hooks/useReflectra";
import { TraitShape } from "@/components/portrait/TraitShape";
import "./transitions.css";

/**
 * Exporting the PDF portrait, shown as a print developing in a darkroom.
 *
 * A sheet feeds in, your real trait shape develops on it out of the blur, lines of
 * text fill in, pages stack up behind it, and when the server's PDF actually
 * arrives the print drops into the tray and the download starts. The steps advance
 * on their own, but the last one waits for the real file, so it never claims to be
 * finished before it is.
 */

const PAGES = 6;
const STEP_MS = 800;
const MIN_MS = 3000;
const FILE_NAME = "reflectra-portrait.pdf";

type Stage = "working" | "done" | "error";

function readableSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function burstConfetti(canvas: HTMLCanvasElement | null) {
  if (!canvas || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = window.innerWidth * dpr;
  canvas.height = window.innerHeight * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const colors = ["#c4baff", "#96e8f5", "#ffcdb0", "#ffffff"];
  const cx = window.innerWidth / 2;
  const cy = window.innerHeight / 2;
  const bits = Array.from({ length: 90 }, () => {
    const angle = Math.random() * Math.PI * 2;
    const speed = 4 + Math.random() * 9;
    return {
      x: cx,
      y: cy,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 4,
      size: 2 + Math.random() * 4,
      spin: Math.random() * Math.PI,
      color: colors[Math.floor(Math.random() * colors.length)],
    };
  });
  const start = performance.now();
  const step = (now: number) => {
    const t = (now - start) / 1000;
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    for (const b of bits) {
      b.x += b.vx;
      b.y += b.vy;
      b.vy += 0.32;
      b.vx *= 0.985;
      b.spin += 0.2;
      ctx.globalAlpha = Math.max(0, 1 - t / 1.6);
      ctx.fillStyle = b.color;
      ctx.save();
      ctx.translate(b.x, b.y);
      ctx.rotate(b.spin);
      ctx.fillRect(-b.size / 2, -b.size / 4, b.size, b.size / 2);
      ctx.restore();
    }
    if (t < 1.6) requestAnimationFrame(step);
    else ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
  };
  requestAnimationFrame(step);
}

function PrintOverlay({
  stage,
  step,
  steps,
  size,
  error,
  onClose,
  onRetry,
}: {
  stage: Stage;
  step: number;
  steps: string[];
  size: number;
  error: string | null;
  onClose: () => void;
  onRetry: () => void;
}) {
  const { data } = usePortrait();
  const confettiRef = useRef<HTMLCanvasElement>(null);
  const developed = stage === "done" || step >= 1;
  const pagesIn = stage === "done" ? PAGES - 1 : Math.min(PAGES - 1, Math.max(0, step * 2 - 1));

  useEffect(() => {
    if (stage === "done") burstConfetti(confettiRef.current);
  }, [stage]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && stage !== "working" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [stage, onClose]);

  return createPortal(
    <div className="print-backdrop" role="dialog" aria-modal="true" aria-label="Exporting your portrait">
      <canvas ref={confettiRef} className="print-confetti" aria-hidden="true" />
      <div className="print-panel">
        <div className="print-stack" aria-hidden="true">
          {Array.from({ length: PAGES - 1 }, (_, i) => (
            <div
              key={i}
              className={`print-sheet is-behind${i < pagesIn ? " is-in" : ""}`}
              style={{ transform: i < pagesIn ? `translate(${(i + 1) * 5}px, ${(i + 1) * -4}px) rotate(${(i + 1) * 1.4}deg)` : undefined }}
            />
          ))}
          <div className={`print-front${stage === "done" ? " is-done" : ""}`}>
            <p className="font-mono text-[8px] uppercase tracking-[0.3em] text-muted-foreground">Reflectra · portrait</p>
            <p className="mt-1 font-display text-xl leading-tight text-foreground">
              {data?.name ? (
                <>
                  The shape of <em className="text-iridescent">{data.name}</em>
                </>
              ) : (
                "Your portrait"
              )}
            </p>
            <div className={`print-shape${developed ? "" : " is-latent"}`}>
              {data && data.traits.length === 4 ? (
                <TraitShape traits={data.traits} />
              ) : (
                <svg viewBox="0 0 100 100">
                  <ellipse cx="50" cy="50" rx="34" ry="40" fill="none" stroke="hsl(var(--iris-violet))" strokeWidth="1.5" />
                </svg>
              )}
            </div>
            {[0.92, 0.78, 0.86, 0.6, 0.82, 0.7].map((width, i) => (
              <div key={i} className={`print-line${step > 1 + Math.floor(i / 2) || stage === "done" ? " is-filled" : ""}`} style={{ width: `${width * 100}%` }}>
                <i />
              </div>
            ))}
            {stage === "working" ? <div className="print-scan" /> : null}
          </div>
        </div>

        <div className="min-w-0">
          <p className="eyebrow mb-3">Exporting</p>
          <h2 className="font-display text-[clamp(2rem,4vw,2.8rem)] leading-[1.05]">
            {stage === "done" ? (
              <>
                Printed. <em className="text-iridescent">That&apos;s you.</em>
              </>
            ) : stage === "error" ? (
              "The print didn't take."
            ) : (
              <>
                Developing your <em className="text-iridescent">portrait</em>
              </>
            )}
          </h2>

          {stage === "error" ? (
            <>
              <p className="mt-4 text-sm leading-relaxed text-muted-foreground">{error}</p>
              <div className="mt-6 flex gap-3">
                <button type="button" className="btn-mirror" onClick={onRetry}>
                  <RotateCcw className="h-4 w-4" /> Try again
                </button>
                <button type="button" className="btn-ghost-glass" onClick={onClose}>
                  Close
                </button>
              </div>
            </>
          ) : (
            <ol className="print-steps mt-6" aria-live="polite">
              {steps.map((label, i) => {
                const done = stage === "done" || i < step;
                const active = stage === "working" && i === step;
                return (
                  <li key={label} className={`print-step${done ? " is-done" : ""}${active ? " is-active" : ""}`}>
                    <span className="print-dot">{done ? <Check className="h-3 w-3" strokeWidth={3} /> : null}</span>
                    <span className="text-sm">{label}</span>
                  </li>
                );
              })}
            </ol>
          )}

          {stage === "done" ? (
            <div className="print-tray">
              <FileText className="h-5 w-5 shrink-0 text-iris-cyan" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-foreground">{FILE_NAME}</p>
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  {PAGES} pages · {readableSize(size)} · saved to your downloads
                </p>
              </div>
              <button type="button" onClick={onClose} className="rounded-full p-1.5 text-muted-foreground hover:text-foreground" aria-label="Close">
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>,
    document.body,
  );
}

/** Export the PDF with the developing-print animation. Render `overlay` somewhere in the page. */
export function usePortraitExport() {
  const { user } = useAuth();
  const { data } = usePortrait();
  const [open, setOpen] = useState(false);
  const [stage, setStage] = useState<Stage>("working");
  const [step, setStep] = useState(0);
  const [size, setSize] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const run = useRef(0);

  const messages = data?.user_messages;
  const steps = [
    messages ? `Reading your ${messages.toLocaleString()} messages` : "Reading your conversations",
    "Developing your shape",
    "Pulling out patterns, in your own words",
    `Binding ${PAGES} pages`,
  ];

  const close = useCallback(() => setOpen(false), []);

  const start = useCallback(async () => {
    if (!user?.id) return;
    const id = ++run.current;
    setOpen(true);
    setStage("working");
    setStep(0);
    setError(null);
    const began = performance.now();

    // The steps tick along on their own; the last one waits for the real file.
    const ticker = window.setInterval(() => {
      if (run.current === id) setStep((s) => Math.min(s + 1, 3));
    }, STEP_MS);

    try {
      const res = await apiFetch(
        `/api/user/export-persona-report?user_id=${encodeURIComponent(user.id)}&tz_offset_minutes=${-new Date().getTimezoneOffset()}`,
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(typeof body?.detail === "string" ? body.detail : "Couldn't build the report. Try again in a moment.");
      }
      const blob = await res.blob();
      const wait = MIN_MS - (performance.now() - began);
      if (wait > 0) await new Promise((resolve) => window.setTimeout(resolve, wait));
      if (run.current !== id) return;

      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = FILE_NAME;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 4000);

      setSize(blob.size);
      setStage("done");
      window.setTimeout(() => run.current === id && setOpen(false), 4200);
    } catch (err) {
      if (run.current !== id) return;
      setError(err instanceof Error ? err.message : "Couldn't build the report.");
      setStage("error");
    } finally {
      window.clearInterval(ticker);
    }
  }, [user?.id]);

  const overlay = open ? (
    <PrintOverlay stage={stage} step={step} steps={steps} size={size} error={error} onClose={close} onRetry={() => void start()} />
  ) : null;

  return { start, overlay, busy: open && stage === "working" };
}

export function ExportPortraitButton({ className = "btn-ghost-glass !px-4 !py-2", label = "PDF" }: { className?: string; label?: string }) {
  const { start, overlay, busy } = usePortraitExport();
  return (
    <>
      <button type="button" className={className} onClick={() => void start()} disabled={busy}>
        <Download className="h-4 w-4" /> {label}
      </button>
      {overlay}
    </>
  );
}
