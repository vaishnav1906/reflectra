/**
 * Your colour: one hue (and intensity) you pick; everything else follows from it.
 *
 * The app's palette is three colours with fixed relationships: the main colour, a
 * second colour 64° below it on the wheel, and a soft accent 130° above it, all at
 * lightness levels chosen to stay readable on the dark background. The default
 * (hue 252, 92%) is Reflectra's original violet / ice cyan / peach.
 */

export type Theme = { hue: number; saturation: number };

export const DEFAULT_THEME: Theme = { hue: 252, saturation: 92 };
export const MIN_SATURATION = 30;
const STORAGE_KEY = "reflectra:theme";

export const PRESETS: { name: string; theme: Theme }[] = [
  { name: "Moonlit", theme: DEFAULT_THEME },
  { name: "Ocean", theme: { hue: 205, saturation: 88 } },
  { name: "Forest", theme: { hue: 150, saturation: 60 } },
  { name: "Sunset", theme: { hue: 15, saturation: 92 } },
  { name: "Rose", theme: { hue: 330, saturation: 80 } },
  { name: "Gold", theme: { hue: 45, saturation: 90 } },
];

const wrap = (hue: number) => ((Math.round(hue) % 360) + 360) % 360;
const clamp = (value: number, low: number, high: number) => Math.max(low, Math.min(high, value));

export function cleanTheme(theme: Partial<Theme> | null | undefined): Theme {
  return {
    hue: wrap(Number(theme?.hue ?? DEFAULT_THEME.hue)),
    saturation: clamp(Math.round(Number(theme?.saturation ?? DEFAULT_THEME.saturation)), MIN_SATURATION, 100),
  };
}

/** The three colours, as "H S% L%" triplets like the CSS variables use. */
export function palette(theme: Theme) {
  const { hue, saturation } = cleanTheme(theme);
  const secondarySat = Math.round(clamp(saturation * 0.91, MIN_SATURATION, 100));
  const accentSat = Math.round(clamp(saturation + 8, MIN_SATURATION, 100));
  return {
    primary: `${hue} ${saturation}% 82%`,
    secondary: `${wrap(hue - 64)} ${secondarySat}% 76%`,
    accent: `${wrap(hue + 130)} ${accentSat}% 82%`,
  };
}

/** How the dark background follows your colour: same hue, stronger tint the more intense your pick. */
export function inkFor(theme: Theme) {
  const t = cleanTheme(theme);
  if (isDefault(t)) return { hue: 245, strength: 1, glow: 1 };
  const intensity = (t.saturation - MIN_SATURATION) / (100 - MIN_SATURATION);
  return {
    hue: wrap(t.hue - 7),
    strength: Math.round((1.4 + 0.8 * intensity) * 100) / 100,
    glow: Math.round((1.4 + 0.8 * intensity) * 100) / 100,
  };
}

/** Put the colours on the page. Every component reads these variables. */
export function applyTheme(theme: Theme) {
  if (typeof document === "undefined") return;
  const { primary, secondary, accent } = palette(theme);
  const style = document.documentElement.style;
  for (const name of ["--iris-violet", "--primary", "--ring", "--sidebar-primary", "--sidebar-ring", "--trait-introspective"]) {
    style.setProperty(name, primary);
  }
  style.setProperty("--iris-cyan", secondary);
  style.setProperty("--iris-peach", accent);
  style.setProperty("--accent", accent);
  // The dark surfaces take your hue too. The default keeps today's exact tint; a chosen
  // colour tints a little more, since a near-black hardly shows its hue otherwise.
  const ink = inkFor(theme);
  style.setProperty("--ink-h", String(ink.hue));
  style.setProperty("--ink-k", String(ink.strength));
  style.setProperty("--glow-k", String(ink.glow));
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", "#0b0a12");
}

/** Back to Reflectra's own colours: nothing chosen, nothing stored. */
export function forgetTheme() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* nothing stored */
  }
  applyTheme(DEFAULT_THEME);
}

export function storedTheme(): Theme | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? cleanTheme(JSON.parse(raw)) : null;
  } catch {
    return null;
  }
}

export function rememberTheme(theme: Theme) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cleanTheme(theme)));
  } catch {
    /* storage blocked: the colour still applies for this visit */
  }
}

export function isDefault(theme: Theme) {
  const t = cleanTheme(theme);
  return t.hue === DEFAULT_THEME.hue && t.saturation === DEFAULT_THEME.saturation;
}

/** The current colours as RGB, for canvas drawings (particles, confetti). */
export function themeRgb(): [number, number, number][] {
  const read = (name: string, fallback: string) =>
    (typeof document !== "undefined" ? getComputedStyle(document.documentElement).getPropertyValue(name).trim() : "") || fallback;
  return [read("--iris-violet", "252 92% 82%"), read("--iris-cyan", "188 84% 76%"), read("--iris-peach", "22 100% 82%")].map(hslToRgb);
}

function hslToRgb(triplet: string): [number, number, number] {
  const [h, s, l] = triplet.replace(/%/g, "").split(/\s+/).map(Number);
  const sat = s / 100;
  const light = l / 100;
  const k = (n: number) => (n + h / 30) % 12;
  const a = sat * Math.min(light, 1 - light);
  const f = (n: number) => light - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return [Math.round(f(0) * 255), Math.round(f(8) * 255), Math.round(f(4) * 255)];
}
