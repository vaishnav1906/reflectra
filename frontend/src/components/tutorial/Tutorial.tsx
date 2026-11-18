import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ArrowLeft, ArrowRight, Download, MessageCircle, Sparkles, Users } from "lucide-react";
import { MirrorMark } from "@/components/MirrorMark";
import { prefersReducedMotion } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { SLIDES, type Device, type Slide, type Target, calloutTarget, screenSrc, slideText, targetFor } from "./slides";

/**
 * The guided tour: tappable slides over real screens. On each screen a pointer goes to
 * what matters and a ring pulses around it while the rest dims. Slides that explain
 * several parts (the Persona graphs, the People orbit) visit them one by one, with a
 * numbered marker on the screen and the explanation in large text below.
 * Tap (or click) the right side or Next to go on, the left side or Back to go back, swipe
 * on a phone, or use the arrow keys. Skip is always there, and so is Esc.
 */

const CALLOUT_MS = 3400;

function useDevice(): Device {
  const query = "(max-width: 767px)";
  const [mobile, setMobile] = useState(() => typeof window !== "undefined" && window.matchMedia?.(query).matches === true);
  useEffect(() => {
    const list = window.matchMedia?.(query);
    if (!list) return;
    const change = () => setMobile(list.matches);
    list.addEventListener?.("change", change);
    return () => list.removeEventListener?.("change", change);
  }, []);
  return mobile ? "mobile" : "desktop";
}

function Hand({ device }: { device: Device }) {
  return device === "mobile" ? (
    // A fingertip: on a phone you tap
    <svg viewBox="0 0 32 32" className="tut-hand">
      <path
        d="M12 4.5a2.5 2.5 0 0 1 5 0V14l1-.2a2.6 2.6 0 0 1 3 1.4l.3.7 1-.2a2.6 2.6 0 0 1 3 1.9l.1.4.6-.1a2.4 2.4 0 0 1 2.8 2.3V23c0 4.1-3.2 7.5-7.3 7.5h-2.4c-2.5 0-4.8-1.3-6.1-3.4L6.3 19.5a2.3 2.3 0 0 1 3.4-3l2.3 2V4.5Z"
        fill="white"
        stroke="#0b0a12"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  ) : (
    // An arrow: on a computer you click
    <svg viewBox="0 0 24 24" className="tut-arrow">
      <path d="M4 2l15 10.5-6.6 1.3L16 21l-3 1.4-3.6-7.2L4 19.5z" fill="white" stroke="#0b0a12" strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  );
}

function boxFor(target: Target, device: Device) {
  const pad = device === "mobile" ? 1.2 : 0.6; // breathing room around the button, in percent
  return {
    left: `${target.x - pad}%`,
    top: `${target.y - pad}%`,
    width: `${target.w + pad * 2}%`,
    height: `${target.h + pad * 2}%`,
  };
}
const centreOf = (target: Target) => ({ left: `${target.x + target.w / 2}%`, top: `${target.y + target.h / 2}%` });

/** A single button: the pointer glides in, taps, ripples, repeats. */
function Pointer({ slide, device }: { slide: Slide; device: Device }) {
  const target = targetFor(slide.key, device);
  if (!target) return null;
  return (
    <>
      <span className={cn("tut-spotlight", slide.gesture === "look" && "is-look")} style={boxFor(target, device)} aria-hidden="true" />
      {slide.gesture === "tap" ? (
        <span className="tut-pointer" style={centreOf(target)} aria-hidden="true">
          <span className="tut-ripple" />
          <Hand device={device} />
        </span>
      ) : null}
    </>
  );
}

/** Several parts of one screen, one at a time: spotlight and pointer travel between them. */
function Callouts({ slide, device, step }: { slide: Slide; device: Device; step: number }) {
  const callout = slide.callouts![step];
  const target = calloutTarget(slide.key, callout.id, device);
  if (!target) return null;
  return (
    <>
      <span className="tut-spotlight is-follow" style={boxFor(target, device)} aria-hidden="true" />
      <span className="tut-marker" style={{ left: `${target.x + target.w}%`, top: `${target.y}%` }} aria-hidden="true">
        {step + 1}
      </span>
      <span className="tut-pointer is-follow" style={centreOf(target)} aria-hidden="true">
        {/* Keyed by step so the press plays again at every stop. */}
        <span key={step} className={cn("tut-follow-press", callout.gesture === "tap" && "is-tap")}>
          {callout.gesture === "tap" ? <span className="tut-ripple" /> : null}
          <Hand device={device} />
        </span>
      </span>
    </>
  );
}

export function Tutorial({ onClose, onStart }: { onClose: () => void; onStart?: () => void }) {
  const device = useDevice();
  const [index, setIndex] = useState(0);
  const [step, setStep] = useState(0); // which callout, on slides that have them
  const slide = SLIDES[index];
  const last = index === SLIDES.length - 1;
  const box = useRef<HTMLDivElement>(null);
  const touch = useRef<{ x: number; y: number } | null>(null);

  const go = useCallback((delta: number) => setIndex((i) => Math.min(SLIDES.length - 1, Math.max(0, i + delta))), []);

  // Each callout gets a few seconds, then the next; it loops until you move on.
  useEffect(() => {
    setStep(0);
    const count = SLIDES[index].callouts?.length ?? 0;
    if (count < 2) return;
    const timer = window.setInterval(() => setStep((s) => (s + 1) % count), prefersReducedMotion() ? CALLOUT_MS * 1.5 : CALLOUT_MS);
    return () => window.clearInterval(timer);
  }, [index]);

  // Load the next screen ahead of time, so slides change instantly.
  useEffect(() => {
    const next = SLIDES[index + 1];
    if (next?.kind === "screen") new Image().src = screenSrc(next.key, device);
  }, [index, device]);

  useEffect(() => {
    box.current?.focus();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  const onKey = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") onClose();
    else if (event.key === "ArrowRight") (last ? onStart ?? onClose : () => go(1))();
    else if (event.key === "ArrowLeft") go(-1);
    else return;
    event.preventDefault();
  };

  // Tapping the screen itself: the left third goes back, the rest goes forward.
  const tapScreen = (event: React.MouseEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    go(event.clientX - rect.left < rect.width / 3 ? -1 : 1);
  };

  const screens = useMemo(() => SLIDES.filter((s) => s.kind === "screen").length, []);
  const callout = slide.callouts?.[step];
  const isCard = slide.kind !== "screen";

  const nav = (
    <div className="tutorial-nav">
      <button type="button" className="btn-ghost-glass !px-4 !py-2" onClick={() => go(-1)} disabled={index === 0} aria-label="Back">
        <ArrowLeft className="h-4 w-4" />
      </button>
      {last ? (
        <button type="button" className="btn-mirror !py-2.5" onClick={onStart ?? onClose} autoFocus>
          Start talking <ArrowRight className="h-4 w-4" />
        </button>
      ) : (
        <button type="button" className="btn-mirror !py-2.5" onClick={() => go(1)}>
          {index === 0 ? "Show me" : "Next"} <ArrowRight className="h-4 w-4" />
        </button>
      )}
    </div>
  );

  return createPortal(
    <div
      ref={box}
      className="tutorial safe-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Reflectra tutorial"
      tabIndex={-1}
      onKeyDown={onKey}
      onTouchStart={(event) => {
        const t = event.touches[0];
        touch.current = { x: t.clientX, y: t.clientY };
      }}
      onTouchEnd={(event) => {
        const start = touch.current;
        touch.current = null;
        if (!start) return;
        const t = event.changedTouches[0];
        const dx = t.clientX - start.x;
        if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(t.clientY - start.y)) go(dx < 0 ? 1 : -1);
      }}
    >
      <div className="tutorial-top">
        <div className="tutorial-progress" aria-hidden="true">
          {SLIDES.map((s, i) => (
            <span key={s.key} className={cn(i < index && "is-done", i === index && "is-now")} />
          ))}
        </div>
        {!last ? (
          <button type="button" className="tutorial-skip" onClick={onClose}>
            Skip
          </button>
        ) : null}
      </div>

      <div key={slide.key} className={cn("tutorial-slide", `is-${slide.kind}`)}>
        {isCard ? (
          // Welcome and ending: a full-screen card
          <div className="tutorial-card">
            <div className="tutorial-hero" aria-hidden="true">
              <span className="tutorial-hero-glow" />
              <MirrorMark className="tutorial-hero-mirror" breathing />
            </div>
            <div className="tutorial-copy">
              <p className="eyebrow !text-[0.66rem]">{slide.kind === "intro" ? "A quick tour" : "Done"}</p>
              <h2 className="tutorial-title is-big">{slide.title}</h2>
              <p className="tutorial-text">{slideText(slide, device)}</p>
            </div>
            {slide.kind === "intro" ? (
              <ul className="tutorial-features" aria-label="What you'll see">
                <li style={{ animationDelay: "0.35s" }}>
                  <MessageCircle className="h-4 w-4" /> Talking to it
                </li>
                <li style={{ animationDelay: "0.5s" }}>
                  <Sparkles className="h-4 w-4" /> What it learns about you
                </li>
                <li style={{ animationDelay: "0.65s" }}>
                  <Users className="h-4 w-4" /> Your people and patterns
                </li>
              </ul>
            ) : (
              <span className="tutorial-pdf-badge">
                <Download className="h-4 w-4" /> Export PDF lives on Persona
              </span>
            )}
            {nav}
            {slide.kind === "intro" ? <p className="tutorial-note">Example screens use a made-up person, Maya.</p> : null}
          </div>
        ) : (
          <>
            <div className={cn("tutorial-screen", device === "mobile" ? "is-phone" : "is-desktop")} onClick={tapScreen} role="presentation">
              <img src={screenSrc(slide.key, device)} alt="" draggable={false} />
              {slide.callouts ? <Callouts slide={slide} device={device} step={step} /> : <Pointer slide={slide} device={device} />}
            </div>

            <div className="tutorial-copy" aria-live="polite">
              <p className="eyebrow !text-[0.62rem]">
                {SLIDES.slice(0, index).filter((s) => s.kind === "screen").length + 1} of {screens}
              </p>
              <h2 className="tutorial-title">{slide.title}</h2>
              {callout ? (
                <>
                  <p className="tutorial-text is-lead">{slideText(slide, device)}</p>
                  <p key={callout.id} className="tutorial-callout">
                    <span className="tutorial-callout-num">{step + 1}</span>
                    {callout.label}
                  </p>
                  <div className="tutorial-steps" role="tablist" aria-label="Parts of this screen">
                    {slide.callouts!.map((c, i) => (
                      <button
                        key={c.id}
                        type="button"
                        role="tab"
                        aria-selected={i === step}
                        aria-label={`Part ${i + 1}`}
                        className={cn(i === step && "is-on")}
                        onClick={() => setStep(i)}
                      />
                    ))}
                  </div>
                </>
              ) : (
                <p className="tutorial-text">{slideText(slide, device)}</p>
              )}
            </div>
            {nav}
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}
