import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

// The first reply of a new conversation must stay as it arrived: not reloaded from the
// server (which dropped its "remembered" and People chips, or showed the reply twice).

const calls: string[] = [];
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(async (url: string) => {
    calls.push(url);
    const body = url.includes("/messages")
      ? [
          { id: "u1", role: "user", content: "ananya cancelled our call", created_at: new Date().toISOString() },
          { id: "a1", role: "assistant", content: "That's a lot.", created_at: new Date().toISOString() },
        ]
      : url.includes("/conversations")
        ? { conversations: [] }
        : {};
    return { ok: true, status: 200, json: async () => body } as Response;
  }),
}));

vi.mock("@/lib/chatStream", () => ({
  ChatError: class extends Error {},
  sendChat: vi.fn(async () => ({
    reply: "That's a lot.",
    conversation_id: "c-new",
    title: "Ananya cancelled",
    mode: "reflection",
    message_id: "a1",
    people_used: [{ id: "p1", name: "Ananya" }],
    remembered: [{ said: "probably just the massing", when: "3 days ago", conversation_id: "c-old" }],
  })),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: { id: "u-1", display_name: "Maya", email: "maya@example.com" }, loading: false }),
}));
vi.mock("emoji-picker-react", () => ({ default: () => null, Theme: {}, EmojiStyle: {}, SuggestionMode: {} }));

import { ChatProvider } from "@/contexts/ChatContext";
import { ChatPage } from "@/pages/ChatPage";

// jsdom has no layout, so no scrolling.
Element.prototype.scrollIntoView = () => undefined;

beforeEach(() => {
  calls.length = 0;
  localStorage.setItem("user_id", "u-1");
});

describe("a new conversation's first reply", () => {
  it("keeps its chips and isn't reloaded over or duplicated", async () => {
    render(
      <MemoryRouter initialEntries={["/app/chat?mode=reflection"]}>
        <ChatProvider>
          <ChatPage />
        </ChatProvider>
      </MemoryRouter>,
    );
    const box = screen.getByRole("textbox");
    fireEvent.change(box, { target: { value: "ananya cancelled our call" } });
    fireEvent.keyDown(box, { key: "Enter", code: "Enter" });

    expect(await screen.findByText(/remembered 3 days ago/i)).toBeInTheDocument();
    expect(screen.getByText(/knew Ananya/i)).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 50));
    expect(calls.some((url) => url.includes("/conversations/c-new/messages"))).toBe(false);
    await waitFor(() => expect(screen.getAllByText("That's a lot.")).toHaveLength(1));
  });
});
