import { describe, expect, it } from "vitest";
import { DEFAULT_THEME, applyTheme, cleanTheme, palette, themeRgb } from "@/lib/theme";

describe("Your colour", () => {
  it("the default reproduces the original violet, cyan and peach", () => {
    expect(palette(DEFAULT_THEME)).toEqual({ primary: "252 92% 82%", secondary: "188 84% 76%", accent: "22 100% 82%" });
  });

  it("the second colour and accent keep their places on the wheel", () => {
    const { primary, secondary, accent } = palette({ hue: 10, saturation: 70 });
    expect(primary).toBe("10 70% 82%");
    expect(secondary.startsWith("306 ")).toBe(true); // 64 below, wrapping past 0
    expect(accent.startsWith("140 ")).toBe(true); // 130 above
  });

  it("lightness stays fixed so text stays readable on the dark background", () => {
    for (const hue of [0, 60, 120, 180, 240, 300]) {
      const { primary, secondary, accent } = palette({ hue, saturation: 100 });
      expect(primary.endsWith(" 82%")).toBe(true);
      expect(secondary.endsWith(" 76%")).toBe(true);
      expect(accent.endsWith(" 82%")).toBe(true);
    }
  });

  it("odd input is tidied, never broken", () => {
    expect(cleanTheme({ hue: -30, saturation: 5 })).toEqual({ hue: 330, saturation: 30 });
    expect(cleanTheme({ hue: 725.4, saturation: 140 })).toEqual({ hue: 5, saturation: 100 });
    expect(cleanTheme(null)).toEqual(DEFAULT_THEME);
  });

  it("canvas colours come out as real RGB", () => {
    document.documentElement.style.setProperty("--iris-violet", "0 100% 50%");
    expect(themeRgb()[0]).toEqual([255, 0, 0]);
  });
});

import { inkFor } from "@/lib/theme";

describe("The background follows your colour", () => {
  it("the default keeps today's exact background", () => {
    expect(inkFor(DEFAULT_THEME)).toEqual({ hue: 245, strength: 1, glow: 1 });
  });

  it("a chosen colour moves the background's hue and tints it more", () => {
    const ink = inkFor({ hue: 150, saturation: 60 });
    expect(ink.hue).toBe(143);
    expect(ink.strength).toBeGreaterThan(1.3);
    expect(inkFor({ hue: 150, saturation: 100 }).strength).toBeGreaterThan(ink.strength);
  });

  it("applying a colour sets the background variables", () => {
    applyTheme({ hue: 10, saturation: 80 });
    const style = document.documentElement.style;
    expect(style.getPropertyValue("--ink-h")).toBe("3");
    expect(Number(style.getPropertyValue("--ink-k"))).toBeGreaterThan(1);
    applyTheme(DEFAULT_THEME);
    expect(style.getPropertyValue("--ink-h")).toBe("245");
    expect(style.getPropertyValue("--ink-k")).toBe("1");
  });
});
