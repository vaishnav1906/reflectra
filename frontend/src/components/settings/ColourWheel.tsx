import { useCallback, useEffect, useRef, useState } from "react";
import { Check, RotateCcw } from "lucide-react";
import { Panel } from "@/components/portrait/PageShell";
import { useQueryClient } from "@tanstack/react-query";
import { cacheTheme, markThemePending, saveThemeToAccount } from "@/lib/themeAccount";
import { DEFAULT_THEME, MIN_SATURATION, PRESETS, Theme, applyTheme, cleanTheme, forgetTheme, isDefault, palette, rememberTheme, storedTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { centreOf, withColourRipple } from "@/lib/motion";

/**
 * "Your colour": pick the main colour on a wheel (around = hue, out from the centre =
 * intensity). The second colour and the accent follow it automatically, so the
 * whole app stays in harmony and readable. Saved to your account.
 */

const SIZE = 220;
const R = SIZE / 2;
const KNOB_INNER = 0.18; // the centre is too washed out to be a theme colour

function toWheel(theme: Theme) {
  const fraction = KNOB_INNER + ((theme.saturation - MIN_SATURATION) / (100 - MIN_SATURATION)) * (1 - KNOB_INNER);
  const angle = (theme.hue * Math.PI) / 180;
  return { x: R + Math.sin(angle) * fraction * (R - 10), y: R - Math.cos(angle) * fraction * (R - 10) };
}

function fromPointer(x: number, y: number): Theme {
  const dx = x - R;
  const dy = y - R;
  const hue = ((Math.atan2(dx, -dy) * 180) / Math.PI + 360) % 360;
  const fraction = Math.min(1, Math.hypot(dx, dy) / (R - 10));
  const saturation = MIN_SATURATION + Math.max(0, (fraction - KNOB_INNER) / (1 - KNOB_INNER)) * (100 - MIN_SATURATION);
  return cleanTheme({ hue, saturation });
}

export function ColourWheel({ saved }: { saved?: Theme | null }) {
  const [theme, setTheme] = useState<Theme>(() => cleanTheme(saved ?? storedTheme() ?? DEFAULT_THEME));
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const wheel = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const saveTimer = useRef<number | null>(null);
  const unsaved = useRef<Theme | null>(null);
  const queryClient = useQueryClient();

  // Leaving Settings before the save goes out: send it now rather than lose it.
  useEffect(
    () => () => {
      if (saveTimer.current && unsaved.current) {
        window.clearTimeout(saveTimer.current);
        void saveThemeToAccount(unsaved.current).catch(() => undefined);
      }
    },
    [],
  );

  useEffect(() => {
    if (saved) setTheme(cleanTheme(saved));
  }, [saved?.hue, saved?.saturation]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Show it everywhere at once; save to the account a moment after you stop moving. */
  const choose = useCallback((next: Theme) => {
    const clean = cleanTheme(next);
    setTheme(clean);
    applyTheme(clean);
    rememberTheme(clean);
    markThemePending(true);
    cacheTheme(queryClient, clean); // nothing may read the old colour from the cache
    unsaved.current = clean;
    setStatus("saving");
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => {
      saveTimer.current = null;
      unsaved.current = null;
      saveThemeToAccount(clean)
        .then(() => setStatus("saved"))
        .catch(() => setStatus("error"));
    }, 600);
  }, [queryClient]);

  /** Everyone's default: clears your choice on this device and on your account. */
  const reset = () => {
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = null;
    unsaved.current = null;
    setTheme(DEFAULT_THEME);
    forgetTheme();
    markThemePending(true);
    cacheTheme(queryClient, null);
    setStatus("saving");
    saveThemeToAccount(null)
      .then(() => setStatus("saved"))
      .catch(() => setStatus("error"));
  };

  const pick = (event: React.PointerEvent) => {
    const box = wheel.current?.getBoundingClientRect();
    if (!box) return;
    choose(fromPointer(((event.clientX - box.left) / box.width) * SIZE, ((event.clientY - box.top) / box.height) * SIZE));
  };

  const knob = toWheel(theme);
  const colours = palette(theme);

  return (
    <Panel title="Your colour" hint={status === "saving" ? "saving…" : status === "saved" ? "saved to your account" : status === "error" ? "couldn't save; it'll stay on this device" : undefined}>
      <div className="grid items-center gap-8 md:grid-cols-[auto_1fr]">
        <div
          ref={wheel}
          className="colour-wheel relative mx-auto touch-none select-none"
          style={{ width: SIZE, height: SIZE }}
          onPointerDown={(event) => {
            dragging.current = true;
            (event.target as Element).setPointerCapture?.(event.pointerId);
            // The first touch ripples the new colour out from your finger; dragging after that is live.
            withColourRipple(() => pick(event), event.clientX, event.clientY);
          }}
          onPointerMove={(event) => dragging.current && pick(event)}
          onPointerUp={() => (dragging.current = false)}
          onPointerCancel={() => (dragging.current = false)}
          role="slider"
          tabIndex={0}
          aria-label="Your colour: arrow keys turn the hue, up and down change intensity"
          aria-valuemin={0}
          aria-valuemax={359}
          aria-valuenow={theme.hue}
          aria-valuetext={`hue ${theme.hue}, intensity ${theme.saturation}%`}
          onKeyDown={(event) => {
            const step = event.shiftKey ? 15 : 5;
            const moves: Record<string, Partial<Theme>> = {
              ArrowLeft: { hue: theme.hue - step },
              ArrowRight: { hue: theme.hue + step },
              ArrowUp: { saturation: theme.saturation + step },
              ArrowDown: { saturation: theme.saturation - step },
            };
            if (moves[event.key]) {
              event.preventDefault();
              choose({ ...theme, ...moves[event.key] });
            }
          }}
        >
          <span
            className="colour-wheel-knob"
            style={{ left: knob.x, top: knob.y, background: `hsl(${colours.primary})` }}
            aria-hidden="true"
          />
        </div>

        <div className="space-y-5">
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "Main", note: "you pick", colour: colours.primary },
              { label: "Second", note: "follows it", colour: colours.secondary },
              { label: "Accent", note: "follows it", colour: colours.accent },
            ].map((swatch) => (
              <div key={swatch.label} className="rounded-2xl border border-white/8 bg-white/[0.02] p-3">
                <span className="block h-10 rounded-xl" style={{ background: `hsl(${swatch.colour})`, boxShadow: `0 0 24px -6px hsl(${swatch.colour})` }} />
                <p className="mt-2 text-xs text-foreground">{swatch.label}</p>
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{swatch.note}</p>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <span className="btn-mirror pointer-events-none !py-2">Preview</span>
            <span className="font-display text-2xl">
              Every thought <em className="text-iridescent">leaves a trace.</em>
            </span>
          </div>

          <div className="flex flex-wrap gap-2" role="group" aria-label="Ready-made colours">
            {PRESETS.map((preset) => {
              const selected = preset.theme.hue === theme.hue && preset.theme.saturation === theme.saturation;
              return (
                <button
                  key={preset.name}
                  type="button"
                  onClick={(event) => {
                    const { x, y } = centreOf(event.currentTarget);
                    withColourRipple(() => (isDefault(preset.theme) ? reset() : choose(preset.theme)), x, y);
                  }}
                  aria-pressed={selected}
                  className={cn("reply-reason", selected && "is-on")}
                >
                  <span className="h-3 w-3 rounded-full" style={{ background: `hsl(${palette(preset.theme).primary})` }} />
                  {preset.name}
                  {selected ? <Check className="h-3 w-3" /> : null}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            className="btn-ghost-glass !py-2 disabled:cursor-default disabled:opacity-40"
            onClick={(event) => {
              const { x, y } = centreOf(event.currentTarget);
              withColourRipple(reset, x, y);
            }}
            disabled={isDefault(theme)}
            title={isDefault(theme) ? "You're on Reflectra's default colours" : undefined}
          >
            <RotateCcw className="h-4 w-4" /> Reset to default
          </button>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Everyone starts on Reflectra&apos;s violet. Drag around the wheel for the colour, toward the edge for more intensity. The other two colours keep the same
            relationship to it as the original violet, cyan and peach, so everything stays readable.
          </p>
        </div>
      </div>
    </Panel>
  );
}
