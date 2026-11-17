import { useMemo, useRef } from "react";
import { span, useScrollScene } from "./scroll";

/** Scene 5: a manifesto that lights up word by word as you scroll. */

const TEXT =
  "Most apps remember what you said. Reflectra remembers who you are: how you talk when you're tired, what keeps weighing on you, the things you're quietly proud of. Then it talks back like someone who has actually been listening.";

// Highlight "who you are:" and the final word.
function emphasisIndices(words: string[]): Set<number> {
  const out = new Set<number>([words.length - 1]);
  const start = words.findIndex((w, i) => w === "who" && words[i + 1] === "you" && words[i + 2] === "are:");
  if (start >= 0) [start, start + 1, start + 2].forEach((i) => out.add(i));
  return out;
}

export function ManifestoScene() {
  const stageRef = useRef<HTMLDivElement>(null);
  const words = useMemo(() => TEXT.split(" "), []);
  const emphasis = useMemo(() => emphasisIndices(words), [words]);

  const sectionRef = useScrollScene<HTMLElement>((p) => {
    const stage = stageRef.current;
    if (!stage) return;
    const lit = span(p, 0.08, 0.85) * words.length;
    stage.querySelectorAll<HTMLElement>("[data-word]").forEach((el) => {
      const i = Number(el.dataset.word);
      el.style.setProperty("--lit", Math.max(0, Math.min(1, lit - i)).toFixed(3));
    });
  });

  return (
    <section ref={sectionRef} className="relative h-[240vh]" aria-label="Why Reflectra">
      <div ref={stageRef} className="sticky top-0 flex h-[100svh] items-center overflow-hidden">
        <p className="manifesto mx-auto max-w-5xl px-6 font-display text-[clamp(1.9rem,4.4vw,4.2rem)] leading-[1.12] text-balance md:px-10">
          {words.map((word, i) => (
            <span key={i} data-word={i} className={emphasis.has(i) ? "manifesto-word is-em" : "manifesto-word"}>
              {word}{" "}
            </span>
          ))}
        </p>
      </div>
    </section>
  );
}
