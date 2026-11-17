import { useRef } from "react";
import { easeInOut, span, useScrollScene } from "./scroll";

/**
 * Scene 3: "It learns you. Slowly."
 * The four traits Reflectra actually models settle from neutral (0.5) to a
 * learned value while confidence rings fill, mirroring the real update rule
 * (each message moves a trait only part of the way).
 */

const TRAITS = [
  { key: "communication", name: "Communication", low: "Concise", high: "Elaborate", target: 0.32, confidence: 0.74, hue: "var(--iris-cyan)" },
  { key: "emotion", name: "Emotional expressiveness", low: "Reserved", high: "Open", target: 0.64, confidence: 0.61, hue: "var(--iris-peach)" },
  { key: "decision", name: "Decision framing", low: "Hesitant", high: "Decisive", target: 0.38, confidence: 0.55, hue: "var(--iris-violet)" },
  { key: "depth", name: "Reflection depth", low: "Surface", high: "Deep", target: 0.78, confidence: 0.82, hue: "var(--trait-empathetic)" },
];

const R = 70; // gauge radius
const ARC = Math.PI * R * 1.5; // 270deg arc length

export function TraitsScene() {
  const stageRef = useRef<HTMLDivElement>(null);

  const sectionRef = useScrollScene<HTMLElement>((p) => {
    const stage = stageRef.current;
    if (!stage) return;
    const learn = easeInOut(span(p, 0.12, 0.72));
    stage.style.setProperty("--heading", span(p, 0, 0.12).toFixed(3));
    stage.style.setProperty("--caption", span(p, 0.7, 0.85).toFixed(3));
    TRAITS.forEach((trait, i) => {
      // Small hesitations early on, like real evidence arriving message by message.
      const wobble = Math.sin(learn * Math.PI * 3 + i) * 0.06 * (1 - learn);
      const value = 0.5 + (trait.target - 0.5) * learn + wobble;
      const confidence = 0.1 + (trait.confidence - 0.1) * easeInOut(span(p, 0.2, 0.8));
      const el = stage.querySelector<HTMLElement>(`[data-trait="${trait.key}"]`);
      if (!el) return;
      el.style.setProperty("--value", value.toFixed(4));
      el.style.setProperty("--confidence", confidence.toFixed(4));
      const label = el.querySelector<HTMLElement>("[data-number]");
      if (label) label.textContent = Math.round(value * 100).toString();
      const conf = el.querySelector<HTMLElement>("[data-confidence]");
      if (conf) conf.textContent = `${Math.round(confidence * 100)}% sure`;
    });
  });

  return (
    <section ref={sectionRef} id="traits" className="relative h-[300vh]" aria-label="How Reflectra learns you">
      <div ref={stageRef} className="traits-stage sticky top-0 flex h-[100svh] items-center overflow-hidden">
        <div className="mx-auto w-full max-w-6xl px-5 md:px-8">
          <div className="max-w-2xl">
            <p className="eyebrow mb-3">02 · It learns you</p>
            <h2 className="font-display text-[clamp(2.2rem,4.6vw,4rem)] leading-[1] text-balance">
              Not who you say you are. <em className="text-iridescent">Who you keep turning out to be.</em>
            </h2>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-x-3 gap-y-4 md:mt-10 md:grid-cols-4 md:gap-6">
            {TRAITS.map((trait) => (
              <figure key={trait.key} data-trait={trait.key} className="trait-gauge" style={{ ["--hue" as string]: `hsl(${trait.hue})` }}>
                <svg viewBox="0 0 180 180" className="mx-auto w-full max-w-[124px] md:max-w-[200px]" aria-hidden="true">
                  {/* confidence ring */}
                  <circle cx="90" cy="90" r={R + 14} className="trait-confidence" pathLength="1" />
                  {/* track */}
                  <circle cx="90" cy="90" r={R} className="trait-track" strokeDasharray={`${ARC} ${2 * Math.PI * R}`} />
                  {/* value */}
                  <circle cx="90" cy="90" r={R} className="trait-value" strokeDasharray={`${ARC} ${2 * Math.PI * R}`} style={{ ["--arc" as string]: ARC }} />
                </svg>
                <div className="trait-center">
                  <span data-number className="font-display text-3xl md:text-5xl">50</span>
                </div>
                <figcaption className="mt-2 text-center">
                  <p className="text-[13px] font-medium leading-tight md:text-sm">{trait.name}</p>
                  <p className="font-mono text-[11px] text-foreground/45">
                    {trait.low} ↔ {trait.high}
                  </p>
                  <p data-confidence className="mt-1 font-mono text-[11px] text-foreground/60">10% sure</p>
                </figcaption>
              </figure>
            ))}
          </div>

          <p className="traits-caption mt-5 max-w-2xl text-[clamp(0.9rem,1.5vw,1.15rem)] leading-relaxed text-foreground/70 md:mt-10">
            One message can only nudge it a little. It takes a pattern, the same thing showing up again and again,
            before Reflectra decides that&apos;s really you. And it gets more certain the longer you talk.
          </p>
        </div>
      </div>
    </section>
  );
}
