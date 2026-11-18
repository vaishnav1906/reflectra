import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ArrowLeft, ArrowRight, Download } from "lucide-react";
import { MirrorMark } from "@/components/MirrorMark";
import { cn } from "@/lib/utils";
import { SLIDES, type Device, type Slide, screenSrc, slideText, targetFor } from "./slides";

/**
 * The guided tour: tappable slides over real screens. On each screen a pointer glides to
 * the one thing that matters, taps it, and a ring pulses around it while the rest dims.
 * Tap (or click) the right side or Next to go on, the left side or Back to go back, swipe
 * on a phone, or use the arrow keys. Skip is always there, and so is Esc.
 */

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

/** The animated pointer and the spotlight around the button it points at. */
function Pointer({ slide, device }: { slide: Slide; device: Device }) {
  const target = targetFor(slide.key, device);
  if (!target) return null;
  const pad = device === "mobile" ? 1.2 : 0.6; // percent of breathing room around the button
  const box = {
    left: `${target.x - pad}%`,
    top: `${target.y - pad}%`,
    width: `${target.w + pad * 2}%`,
    height: `${target.h + pad * 2}%`,
  };
  const tip = { left: `${target.x + target.w / 2}%`, top: `${target.y + target.h / 2}%` };
  return (
    <>
      <span className={cn("tut-spotlight", slide.gesture === "look" && "is-look")} style={box} aria-hidden="true" />
      {slide.gesture === "tap" ? (
        <span className="tut-pointer" style={tip} aria-hidden="true">
          <span className="tut-ripple" />
          {device === "mobile" ? (
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
          )}
        </span>
      ) : null}
    </>
  );
}

export function Tutorial({ onClose, onStart }: { onClose: () => void; onStart?: () => void }) {
  const device = useDevice();
  const [index, setIndex] = useState(0);
  const slide = SLIDES[index];
  const last = index === SLIDES.length - 1;
  const box = useRef<HTMLDivElement>(null);
  const touch = useRef<{ x: number; y: number } | null>(null);

  const go = useCallback((step: number) => setIndex((i) => Math.min(SLIDES.length - 1, Math.max(0, i + step))), []);

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
        {slide.kind === "screen" ? (
          <div
            className={cn("tutorial-screen", device === "mobile" ? "is-phone" : "is-desktop")}
            onClick={tapScreen}
            role="presentation"
          >
            <img src={screenSrc(slide.key, device)} alt="" draggable={false} />
            <Pointer slide={slide} device={device} />
          </div>
        ) : (
          <div className="tutorial-hero" aria-hidden="true">
            <MirrorMark className="h-24 w-24" breathing />
            {slide.kind === "end" ? (
              <span className="tutorial-pdf-badge">
                <Download className="h-4 w-4" /> Export PDF lives on Persona
              </span>
            ) : null}
          </div>
        )}

        <div className="tutorial-copy" aria-live="polite">
          <p className="eyebrow !text-[0.62rem]">
            {slide.kind === "screen" ? `${SLIDES.slice(0, index).filter((s) => s.kind === "screen").length + 1} of ${screens}` : slide.kind === "intro" ? "A quick tour" : "Done"}
          </p>
          <h2 className="tutorial-title">{slide.title}</h2>
          <p className="tutorial-text">{slideText(slide, device)}</p>
          {slide.kind === "intro" ? <p className="tutorial-note">Example screens use a made-up person, Maya.</p> : null}
        </div>

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
      </div>
    </div>,
    document.body,
  );
}
