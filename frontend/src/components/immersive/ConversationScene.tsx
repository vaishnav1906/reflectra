import { useRef } from "react";
import { span, useScrollScene } from "./scroll";

/**
 * Scene 2: "Say anything."
 * A real Reflection-mode exchange plays out as you scroll. Phrases it picks up
 * light up in the user's messages and float into the "noticed" column.
 */

type Line = { from: "you" | "reflectra"; text: string; signals?: string[] };

// Lightly trimmed from a real Reflection-mode test conversation.
const LINES: Line[] = [
  { from: "you", text: "long day. had my thesis review and my guide basically tore apart chapter 3", signals: ["tore apart"] },
  { from: "reflectra", text: "That sounds exhausting. Did they give you a clear direction, or are you just staring at a mess right now?" },
  { from: "you", text: "idk, i spent like 3 weeks on it. maybe i'm just not cut out for research", signals: ["3 weeks", "not cut out"] },
  {
    from: "reflectra",
    text: "Three weeks of work getting shredded in an hour would make anyone want to quit. Does it feel like you're hitting a wall with the research itself, or are you just fried from the critique?",
  },
  { from: "you", text: "lol ok fair. but how do i even start fixing it", signals: ["lol ok fair"] },
  {
    from: "reflectra",
    text: "Pick the one part you felt surest about while writing it. Ignore the rest of the wreckage tonight and start there tomorrow.",
  },
];

const NOTICED = [
  { label: "Hurt by criticism", detail: "\"tore apart\"" },
  { label: "Effort it cost", detail: "\"3 weeks\"" },
  { label: "Self-doubt", detail: "\"not cut out\"" },
  { label: "Lets humor back in", detail: "\"lol ok fair\"" },
];

function renderWithSignals(line: Line) {
  if (!line.signals?.length) return line.text;
  const pattern = new RegExp(`(${line.signals.map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "g");
  return line.text.split(pattern).map((part, i) =>
    line.signals!.includes(part) ? (
      <mark key={i} className="convo-signal">
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

export function ConversationScene() {
  const stageRef = useRef<HTMLDivElement>(null);

  const sectionRef = useScrollScene<HTMLElement>((p) => {
    const stage = stageRef.current;
    if (!stage) return;
    const lineCount = LINES.length;
    // Lines appear across 8%..78% of the section; a typing indicator precedes each reply.
    const shown = Math.floor(span(p, 0.08, 0.78) * lineCount + 0.0001);
    stage.querySelectorAll<HTMLElement>("[data-line]").forEach((el) => {
      const i = Number(el.dataset.line);
      el.classList.toggle("on", i < shown || p >= 0.999);
    });
    const next = LINES[shown];
    stage.dataset.typing = next && next.from === "reflectra" && p < 0.8 ? "true" : "false";
    stage.querySelectorAll<HTMLElement>("[data-noticed]").forEach((el) => {
      const i = Number(el.dataset.noticed);
      el.classList.toggle("on", p > 0.22 + i * 0.15);
    });
    stage.style.setProperty("--heading", span(p, 0, 0.1).toFixed(3));
    // Keep the newest message in view inside the chat window.
    const scroller = stage.querySelector<HTMLElement>(".convo-scroll");
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
  });

  return (
    <section ref={sectionRef} id="conversation" className="relative h-[420vh]" aria-label="How Reflectra listens">
      <div ref={stageRef} className="convo-stage sticky top-0 flex h-[100svh] items-center overflow-hidden">
        <div className="mx-auto grid w-full max-w-6xl gap-10 px-5 md:grid-cols-[1.25fr_0.75fr] md:items-center md:px-8">
          <div>
            <p className="eyebrow mb-3">01 · It listens</p>
            <h2 className="font-display text-[clamp(2.2rem,4.6vw,4rem)] leading-[1] text-balance">
              Say anything. <em className="text-iridescent">It hears what you meant.</em>
            </h2>

            <div className="convo-window glass-panel iris-border mt-7 rounded-3xl">
              <div className="flex items-center gap-2 border-b border-white/5 px-5 py-3">
                <span className="h-2 w-2 rounded-full bg-iris-cyan pulse-indicator" />
                <span className="text-xs text-foreground/60">Reflection mode</span>
              </div>
              <div className="convo-scroll max-h-[46svh] space-y-3 overflow-hidden px-4 py-5 md:px-5">
                {LINES.map((line, i) => (
                  <div key={i} data-line={i} className={`convo-line ${line.from === "you" ? "is-you" : "is-ai"}`}>
                    <div className={`convo-bubble ${line.from === "you" ? "chat-bubble-user" : "chat-bubble-ai"}`}>
                      {renderWithSignals(line)}
                    </div>
                  </div>
                ))}
                <div className="convo-typing" aria-hidden="true">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
              </div>
            </div>
          </div>

          <aside className="hidden md:block" aria-label="What Reflectra noticed">
            <p className="eyebrow mb-4">What it picks up</p>
            <ul className="space-y-3">
              {NOTICED.map((item, i) => (
                <li key={item.label} data-noticed={i} className="convo-noticed glass-panel rounded-2xl px-4 py-3">
                  <p className="text-sm font-medium">{item.label}</p>
                  <p className="font-mono text-xs text-foreground/50">{item.detail}</p>
                </li>
              ))}
            </ul>
            <p className="mt-6 text-sm leading-relaxed text-foreground/55">
              Not keywords. Patterns: what it cost you, how you talk about yourself, and when the humor comes back.
            </p>
          </aside>
        </div>
      </div>
    </section>
  );
}
