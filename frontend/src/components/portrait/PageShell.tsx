import { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Shared frame for the signed-in pages: eyebrow, serif title, subtitle, scrollable body. */
export function PageShell({
  eyebrow,
  title,
  accent,
  subtitle,
  actions,
  children,
  className,
}: {
  eyebrow: string;
  title: string;
  accent?: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className="h-screen overflow-y-auto scrollbar-thin">
      <div className={cn("mx-auto w-full max-w-5xl px-5 pb-24 pt-10 md:px-10 md:pt-14", className)}>
        <header className="fade-in flex flex-wrap items-end justify-between gap-5">
          <div className="min-w-0">
            <p className="eyebrow mb-3">{eyebrow}</p>
            <h1 className="!text-[clamp(2.2rem,5vw,3.6rem)] !leading-[1.02] text-balance">
              {title} {accent ? <em className="text-iridescent">{accent}</em> : null}
            </h1>
            {subtitle ? <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">{subtitle}</p> : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </header>
        <div className="mt-10 space-y-6">{children}</div>
      </div>
    </div>
  );
}

export function Panel({ children, className, title, hint }: { children: ReactNode; className?: string; title?: string; hint?: ReactNode }) {
  return (
    <section className={cn("glass-panel rounded-3xl p-6 md:p-7", className)}>
      {title ? (
        <div className="mb-5 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="eyebrow !text-foreground/70">{title}</h2>
          {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function Stat({ value, label, className }: { value: ReactNode; label: string; className?: string }) {
  return (
    <div className={className}>
      <p className="font-display text-4xl leading-none md:text-5xl">{value}</p>
      <p className="mt-2 text-xs leading-snug text-muted-foreground">{label}</p>
    </div>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex h-screen items-center justify-center text-sm text-muted-foreground" role="status">
      {label}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="max-w-md text-sm text-muted-foreground">{message}</p>
      {onRetry ? (
        <button type="button" className="btn-ghost-glass" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}
