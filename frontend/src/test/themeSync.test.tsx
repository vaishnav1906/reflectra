import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const profile = { data: null as null | { theme: { hue: number; saturation: number } | null }, isFetchedAfterMount: true };
vi.mock("@/components/settings/AboutYou", () => ({ useProfile: () => profile }));
const saved: unknown[] = [];
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(async (_url: string, init: RequestInit) => {
    saved.push(JSON.parse(String(init.body)).theme);
    return { ok: true } as Response;
  }),
}));

import { useThemeSync } from "@/hooks/useThemeSync";
import { markThemePending, themePending } from "@/lib/themeAccount";
import { rememberTheme, storedTheme } from "@/lib/theme";

const FOREST = { hue: 150, saturation: 60 };
const SUNSET = { hue: 15, saturation: 92 };
const onScreen = () => document.documentElement.style.getPropertyValue("--iris-violet");

beforeEach(() => {
  localStorage.clear();
  saved.length = 0;
  document.documentElement.removeAttribute("style");
});

describe("Your colour across visits", () => {
  it("a choice not yet saved wins over the older account colour, and gets saved", async () => {
    rememberTheme(FOREST);
    markThemePending(true);
    profile.data = { theme: SUNSET }; // the account still has the old colour
    profile.isFetchedAfterMount = true;
    renderHook(() => useThemeSync());
    expect(storedTheme()).toEqual(FOREST); // not switched back to Sunset
    await vi.waitFor(() => expect(saved).toEqual([FOREST]));
    expect(themePending()).toBe(false);
  });

  it("a cached copy from earlier is never trusted", () => {
    rememberTheme(FOREST);
    profile.data = { theme: SUNSET };
    profile.isFetchedAfterMount = false;
    renderHook(() => useThemeSync());
    expect(storedTheme()).toEqual(FOREST);
    expect(onScreen()).toBe("");
  });

  it("a colour picked on another device comes through once it's settled here", () => {
    rememberTheme(FOREST);
    profile.data = { theme: SUNSET };
    profile.isFetchedAfterMount = true;
    renderHook(() => useThemeSync());
    expect(storedTheme()).toEqual(SUNSET);
    expect(onScreen()).toBe("15 92% 82%");
  });

  it("no colour on the account means the default here too", () => {
    rememberTheme(FOREST);
    profile.data = { theme: null };
    profile.isFetchedAfterMount = true;
    renderHook(() => useThemeSync());
    expect(storedTheme()).toBeNull();
    expect(onScreen()).toBe("252 92% 82%");
  });
});
