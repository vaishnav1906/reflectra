import { useEffect, useState } from "react";

/** Floating nav: transparent over the hero, frosted glass once you scroll. */
export function ImmersiveNav({ signedIn, onPrimary }: { signedIn: boolean; onPrimary: () => void }) {
  const [solid, setSolid] = useState(false);

  useEffect(() => {
    const onScroll = () => setSolid(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`immersive-nav ${solid ? "is-solid" : ""}`}>
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 md:px-8">
        <a href="#top" className="font-display text-2xl tracking-tight" aria-label="Reflectra, back to top">
          Reflectra
        </a>
        <nav className="hidden items-center gap-7 text-sm text-foreground/65 md:flex" aria-label="Sections">
          <a href="#conversation" className="transition-colors hover:text-foreground">How it listens</a>
          <a href="#traits" className="transition-colors hover:text-foreground">How it learns</a>
          <a href="#modes" className="transition-colors hover:text-foreground">Modes</a>
          <a href="#privacy" className="transition-colors hover:text-foreground">Privacy</a>
        </nav>
        <button type="button" onClick={onPrimary} className="btn-ghost-glass !px-5 !py-2">
          {signedIn ? "Open app" : "Sign in"}
        </button>
      </div>
    </header>
  );
}
