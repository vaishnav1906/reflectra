import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Tutorial } from "@/components/tutorial/Tutorial";
import { SLIDES, targetFor } from "@/components/tutorial/slides";
import { isNewAccount, markTutorialDone, shouldAutoStartTutorial, tutorialDone } from "@/lib/tutorial";

const DAY = 86_400_000;

beforeEach(() => localStorage.clear());

describe("the tutorial", () => {
  it("goes through every slide to the Export PDF slide and the ending", () => {
    const onStart = vi.fn();
    render(<Tutorial onClose={vi.fn()} onStart={onStart} />);
    expect(screen.getByRole("heading", { name: "Welcome to Reflectra" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /show me/i }));
    for (let i = 1; i < SLIDES.length - 1; i++) {
      expect(screen.getByRole("heading", { name: SLIDES[i].title })).toBeInTheDocument();
      if (i < SLIDES.length - 2) fireEvent.click(screen.getByRole("button", { name: /^next/i }));
    }
    expect(screen.getByRole("heading", { name: /take your portrait with you/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^next/i }));
    expect(screen.getByRole("heading", { name: "You're all set" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Skip" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /start talking/i }));
    expect(onStart).toHaveBeenCalled();
  });

  it("can be skipped from any slide, or with Esc", () => {
    const onClose = vi.fn();
    render(<Tutorial onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("moves with the arrow keys and back again", () => {
    render(<Tutorial onClose={vi.fn()} />);
    const dialog = screen.getByRole("dialog");
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(screen.getByRole("heading", { name: SLIDES[2].title })).toBeInTheDocument();
    fireEvent.keyDown(dialog, { key: "ArrowLeft" });
    expect(screen.getByRole("heading", { name: SLIDES[1].title })).toBeInTheDocument();
  });

  it("swipes on a phone", () => {
    render(<Tutorial onClose={vi.fn()} />);
    const dialog = screen.getByRole("dialog");
    fireEvent.touchStart(dialog, { touches: [{ clientX: 300, clientY: 400 }] });
    fireEvent.touchEnd(dialog, { changedTouches: [{ clientX: 120, clientY: 410 }] });
    expect(screen.getByRole("heading", { name: SLIDES[1].title })).toBeInTheDocument();
  });

  it("every screen slide has a spot to point at, on a PC and on a phone", () => {
    for (const slide of SLIDES.filter((s) => s.kind === "screen")) {
      for (const device of ["desktop", "mobile"] as const) {
        const target = targetFor(slide.key, device);
        expect(target, `${device}/${slide.key}`).not.toBeNull();
        expect(target!.x + target!.w).toBeLessThanOrEqual(100.5);
        expect(target!.y + target!.h).toBeLessThanOrEqual(100.5);
      }
    }
  });
});

describe("when it shows by itself", () => {
  const now = Date.parse("2026-11-18T10:00:00Z");

  it("only for new accounts that haven't seen it", () => {
    expect(shouldAutoStartTutorial("u1", new Date(now - DAY).toISOString(), now)).toBe(true);
    expect(shouldAutoStartTutorial("u1", new Date(now - 30 * DAY).toISOString(), now)).toBe(false); // existing user
    expect(shouldAutoStartTutorial(null, new Date(now).toISOString(), now)).toBe(false);
    expect(isNewAccount(null, now)).toBe(false);
  });

  it("never again once finished or skipped", () => {
    expect(tutorialDone("u1")).toBe(false);
    markTutorialDone("u1");
    expect(tutorialDone("u1")).toBe(true);
    expect(shouldAutoStartTutorial("u1", new Date(now).toISOString(), now)).toBe(false);
    expect(tutorialDone("u2")).toBe(false); // per person
  });
});
