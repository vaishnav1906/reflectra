import { useRef } from "react";
import { clamp, easeInOut, span, useScrollScene } from "./scroll";

/**
 * Scene 4: "Two ways to talk."
 * One message, two replies. A glowing seam sweeps across the stage and reveals
 * Reflection mode on one side and Mirror mode (your own voice) on the other.
 * The Mirror reply is adapted from a real test run; the Reflection reply is illustrative.
 */

const MESSAGE = "ugh i have to text my landlord about the rent being late and i keep putting it off";

const MODES = [
  {
    key: "reflection",
    name: "Reflection",
    tagline: "A friend who notices.",
    reply:
      "You're not avoiding the landlord, you're avoiding the moment it becomes real. What's the worst version of how that text goes?",
    detail: "Warm, specific, honest. It asks one real question, or none.",
  },
  {
    key: "mirror",
    name: "Mirror",
    tagline: "You, talking back.",
    reply: "classic us. we both know waiting makes it worse, just send it and get it over with",
    detail: "Learns your casing, slang and rhythm from your own messages.",
  },
];

export function TwoMirrorsScene() {
  const stageRef = useRef<HTMLDivElement>(null);

  const sectionRef = useScrollScene<HTMLElement>((p) => {
    const stage = stageRef.current;
    if (!stage) return;
    stage.style.setProperty("--heading", span(p, 0, 0.1).toFixed(3));
    stage.style.setProperty("--message", span(p, 0.06, 0.2).toFixed(3));
    // The seam sweeps left to right; each card is revealed exactly as the seam crosses it.
    const seam = easeInOut(span(p, 0.2, 0.8));
    stage.style.setProperty("--seam", seam.toFixed(4));
    stage.style.setProperty("--left", clamp(seam * 2).toFixed(4));
    stage.style.setProperty("--right", clamp(seam * 2 - 1).toFixed(4));
  });

  return (
    <section ref={sectionRef} id="modes" className="relative h-[300vh]" aria-label="Two ways to talk">
      <div ref={stageRef} className="modes-stage sticky top-0 flex h-[100svh] items-center overflow-hidden">
        <div className="mx-auto w-full max-w-6xl px-5 md:px-8">
          <div className="text-center">
            <p className="eyebrow mb-3">03 · Two ways to talk</p>
            <h2 className="font-display text-[clamp(2.2rem,4.6vw,4rem)] leading-[1] text-balance">
              One message. <em className="text-iridescent">Two mirrors.</em>
            </h2>
          </div>

          <div className="modes-message mx-auto mt-5 max-w-xl md:mt-8">
            <div className="chat-bubble-user ml-auto w-fit max-w-full rounded-2xl rounded-br-md px-4 py-3 text-[14px] md:text-[15px]">
              {MESSAGE}
            </div>
          </div>

          <div className="modes-split relative mt-5 grid gap-3 md:mt-8 md:grid-cols-2 md:gap-6">
            <div className="modes-seam" aria-hidden="true" />
            {MODES.map((mode) => (
              <article key={mode.key} className={`modes-card modes-${mode.key} glass-panel rounded-3xl p-4 md:p-7`}>
                <p className="eyebrow">{mode.name} mode</p>
                <h3 className="mt-1 font-display text-2xl italic md:mt-2 md:text-3xl">{mode.tagline}</h3>
                <div className="chat-bubble-ai mt-3 rounded-2xl rounded-bl-md px-4 py-3 text-[14px] leading-relaxed md:mt-5 md:text-[15px]">
                  {mode.reply}
                </div>
                <p className="mt-4 hidden text-sm text-foreground/55 md:block">{mode.detail}</p>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
