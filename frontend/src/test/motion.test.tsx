import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { markShared, sharedWords } from "@/lib/sharedWords";
import { WeekReel, type WeekReelData } from "@/components/week/WeekReel";

describe("shared words in a reflection's quotes", () => {
  it("finds the words that come back across quotes, loosely", () => {
    const shared = sharedWords(["I keep skipping the gym again", "skipped gym because of exams", "exams are stressing me"]);
    expect(shared.has("skipp") || shared.has("skip")).toBe(true);
    expect(shared.has("gym")).toBe(false); // too short to count as a theme word
    expect(shared.has("exam")).toBe(true);
  });

  it("marks only those words inside a quote", () => {
    const parts = markShared("exams are stressing me", new Set(["exam"]));
    expect(parts.filter((p) => p.shared).map((p) => p.text)).toEqual(["exams"]);
  });
});

const WEEK: WeekReelData = {
  activeDays: 3,
  messages: 42,
  conversations: 4,
  days: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((label, i) => ({ label, messages: i % 2 ? 0 : 10, mood: null })),
  people: [{ id: "p1", name: "Riya", relationship: "best friend" }],
  going: [],
  pattern: null,
};

describe("the week reel", () => {
  it("steps through its cards with the keyboard and closes at the end", () => {
    const onClose = vi.fn();
    render(<WeekReel data={WEEK} onClose={onClose} />);
    const reel = screen.getByRole("dialog", { name: /your week/i });
    expect(screen.getByText("1 / 4 · tap or swipe")).toBeInTheDocument(); // intro, days, people, end
    fireEvent.keyDown(reel, { key: "ArrowRight" });
    fireEvent.keyDown(reel, { key: "ArrowRight" });
    expect(screen.getByText("Riya")).toBeInTheDocument();
    fireEvent.keyDown(reel, { key: "ArrowRight" });
    fireEvent.keyDown(reel, { key: "ArrowRight" });
    expect(onClose).toHaveBeenCalled();
  });

  it("Esc closes it", () => {
    const onClose = vi.fn();
    render(<WeekReel data={WEEK} onClose={onClose} />);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});
