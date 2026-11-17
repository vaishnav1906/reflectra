import { EyeOff, Lock, Trash2 } from "lucide-react";
import { useRevealOnScroll } from "./scroll";

/** Scene 6 (privacy) and scene 7 (final call to action), plus the footer. */

const PROMISES = [
  {
    icon: EyeOff,
    title: "Incognito means nothing is saved",
    body: "Turn it on and the conversation never touches the database. No messages, no learning, no trace.",
  },
  {
    icon: Lock,
    title: "Locked to you",
    body: "Every request is tied to your login, and the database refuses anyone else. Not other users, not the public API.",
  },
  {
    icon: Trash2,
    title: "Gone means gone",
    body: "Clear your history or delete your account and your conversations, traits and insights are erased with it.",
  },
];

export function PrivacySection() {
  const ref = useRevealOnScroll<HTMLElement>();
  return (
    <section ref={ref} id="privacy" className="relative px-5 py-[18vh] md:px-8" aria-label="Privacy">
      <div className="mx-auto max-w-6xl">
        <div className="reveal max-w-2xl">
          <p className="eyebrow mb-3">04 · Yours alone</p>
          <h2 className="font-display text-[clamp(2.2rem,4.6vw,4rem)] leading-[1] text-balance">
            What you tell a mirror <em className="text-iridescent">should stay in the mirror.</em>
          </h2>
        </div>
        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {PROMISES.map(({ icon: Icon, title, body }, i) => (
            <article
              key={title}
              className="reveal glass-panel iris-border rounded-3xl p-6"
              style={{ transitionDelay: `${i * 120}ms` }}
            >
              <Icon className="h-5 w-5 text-iris-violet" aria-hidden="true" />
              <h3 className="mt-5 text-lg font-medium">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-foreground/60">{body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export function FinalCTA({ onStart }: { onStart: () => void }) {
  const ref = useRevealOnScroll<HTMLElement>();
  return (
    <section ref={ref} className="relative overflow-hidden px-5 pb-[14vh] pt-[8vh]" aria-label="Get started">
      <div className="final-frame relative mx-auto grid place-items-center text-center">
        <div className="final-ring absolute inset-0" aria-hidden="true" />
        <div className="relative px-8">
          <h2 className="reveal font-display text-[clamp(3rem,9vw,7.5rem)] leading-[0.9]">
            Meet <em className="text-iridescent">yourself.</em>
          </h2>
          <p className="reveal mx-auto mt-5 max-w-sm text-foreground/65" style={{ transitionDelay: "120ms" }}>
            Start with whatever&apos;s on your mind. Reflectra takes it from there.
          </p>
          <div className="reveal mt-8" style={{ transitionDelay: "220ms" }}>
            <button type="button" onClick={onStart} className="btn-mirror">
              Start reflecting
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

const GITHUB_URL = "https://github.com/vaishnav1906/reflectra";

/** The GitHub mark, inline so it needs no icon package. */
function GitHubMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" className={className} fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

export function ImmersiveFooter() {
  return (
    <footer className="border-t border-white/5 px-5 py-10 md:px-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 text-sm text-foreground/45 md:flex-row">
        <span className="font-display text-xl text-foreground/80">Reflectra</span>
        <nav className="flex flex-wrap justify-center gap-x-6 gap-y-2 whitespace-nowrap" aria-label="Footer">
          <a href="#conversation" className="hover:text-foreground">How it listens</a>
          <a href="#traits" className="hover:text-foreground">How it learns</a>
          <a href="#modes" className="hover:text-foreground">Modes</a>
          <a href="#privacy" className="hover:text-foreground">Privacy</a>
        </nav>
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="group inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-foreground/70 transition-colors hover:border-white/25 hover:bg-white/[0.07] hover:text-foreground"
          aria-label="Reflectra on GitHub (opens in a new tab)"
        >
          <GitHubMark className="h-4 w-4" />
          <span>GitHub</span>
          <span aria-hidden="true" className="transition-transform group-hover:translate-x-0.5">↗</span>
        </a>
      </div>
      <p className="mt-6 text-center text-xs text-foreground/35">© {new Date().getFullYear()} Reflectra</p>
    </footer>
  );
}
