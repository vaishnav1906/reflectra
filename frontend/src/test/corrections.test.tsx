import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

type Call = { url: string; body: Record<string, unknown> };
const calls: Call[] = [];
let respond: (call: Call) => { status?: number; body: unknown } = () => ({ body: {} });

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(async (url: string, init: RequestInit = {}) => {
    const call = { url, body: init.body ? JSON.parse(String(init.body)) : {} };
    calls.push(call);
    const { status = 200, body } = respond(call);
    return { ok: status < 300, status, json: async () => body } as Response;
  }),
}));

// The real picker is a large library; a stand-in with the same props is enough here.
vi.mock("emoji-picker-react", () => ({
  default: ({ onEmojiClick, searchPlaceholder }: { onEmojiClick: (d: { emoji: string }) => void; searchPlaceholder: string }) => (
    <div>
      <input placeholder={searchPlaceholder} />
      {["😂", "🔥"].map((emoji) => (
        <button key={emoji} onClick={() => onEmojiClick({ emoji })}>{`pick ${emoji}`}</button>
      ))}
    </div>
  ),
  Theme: { DARK: "dark" },
  EmojiStyle: { NATIVE: "native" },
  SuggestionMode: { RECENT: "recent" },
}));

import { ReplyFeedback } from "@/components/chat/ReplyFeedback";
import { TraitCheck } from "@/components/portrait/TraitCheck";
import { ReflectionCheck } from "@/components/portrait/ReflectionCheck";
import { ChatInput } from "@/components/chat/ChatInput";
import type { PortraitTrait } from "@/hooks/useReflectra";

const wrap = (node: React.ReactNode) =>
  render(<QueryClientProvider client={new QueryClient()}>{node}</QueryClientProvider>);

beforeEach(() => {
  calls.length = 0;
  respond = () => ({ body: {} });
  localStorage.clear();
});

describe("ReplyFeedback", () => {
  it("thumbs up is one tap", async () => {
    render(<ReplyFeedback messageId="m1" mode="reflection" />);
    fireEvent.click(screen.getByRole("button", { name: "Good reply" }));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0]).toEqual({ url: "/api/feedback/reply/m1", body: { verdict: "up", reasons: [] } });
    expect(await screen.findByText("Glad that landed.")).toBeInTheDocument();
  });

  it("thumbs down asks what missed, with mirror-specific reasons", async () => {
    render(<ReplyFeedback messageId="m2" mode="mirror" />);
    fireEvent.click(screen.getByRole("button", { name: "Not quite me" }));
    expect(calls).toHaveLength(0); // nothing sent until they choose
    fireEvent.click(screen.getByRole("button", { name: /Doesn't sound like me/ }));
    fireEvent.click(screen.getByRole("button", { name: /Too long/ }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0].body).toEqual({ verdict: "down", reasons: ["not_my_voice", "too_long"] });
  });

  it("tapping the same thumb again takes it back", async () => {
    render(<ReplyFeedback messageId="m3" mode="reflection" initial="up" />);
    fireEvent.click(screen.getByRole("button", { name: "Good reply" }));
    await waitFor(() => expect(calls[0].body).toEqual({ verdict: "clear", reasons: [] }));
  });
});

const trait: PortraitTrait = {
  key: "communication_style",
  name: "Communication",
  low: "Concise",
  high: "Elaborate",
  score: 0.37,
  confidence: 0.65,
  confidence_label: "well established",
  evidence_count: 133,
  reading: "You get to the point.",
};

describe("TraitCheck", () => {
  it("yes reports how much more sure it became", async () => {
    respond = () => ({ body: { previous_score: 0.37, new_score: 0.37, previous_confidence: 0.65, new_confidence: 0.7, counts_as_messages: 15 } });
    wrap(<TraitCheck trait={trait} />);
    fireEvent.click(screen.getByRole("button", { name: /Yes, Communication/ }));
    expect(await screen.findByText(/65% → 70%/)).toBeInTheDocument();
    expect(calls[0].body).toEqual({ verdict: "agree" });
  });

  it("not quite previews the change before saving it", async () => {
    respond = (call) => ({
      body: { previous_score: 0.37, new_score: 0.34, previous_confidence: 0.65, new_confidence: 0.47, counts_as_messages: 15, saved: !call.body.dry_run },
    });
    wrap(<TraitCheck trait={trait} />);
    fireEvent.click(screen.getByRole("button", { name: "Not quite" }));
    const save = screen.getByRole("button", { name: /Save/ });
    expect(save).toBeDisabled(); // no saving blind
    const slider = screen.getByRole("slider");
    fireEvent.change(slider, { target: { value: "10" } });
    fireEvent.pointerUp(slider);
    expect(await screen.findByText(/move 37 → 34/)).toBeInTheDocument();
    expect(calls[0].body).toEqual({ verdict: "disagree", self_score: 0.1, dry_run: true });
    fireEvent.click(save);
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(calls[1].body).toEqual({ verdict: "disagree", self_score: 0.1 });
    expect(await screen.findByText(/Moved 37 → 34/)).toBeInTheDocument();
  });

  it("shows the server's reason when it can't apply", async () => {
    respond = () => ({ status: 422, body: { detail: "Reflectra hasn't read this trait yet. Chat a little first." } });
    wrap(<TraitCheck trait={trait} />);
    fireEvent.click(screen.getByRole("button", { name: /Yes, Communication/ }));
    expect(await screen.findByText(/hasn't read this trait yet/)).toBeInTheDocument();
  });
});

describe("ReflectionCheck", () => {
  it("not really hides it and passes on what was off", async () => {
    wrap(<ReflectionCheck id="r1" />);
    fireEvent.click(screen.getByRole("button", { name: /Not really/ }));
    fireEvent.change(screen.getByLabelText(/What's off about it/), { target: { value: "one bad week" } });
    fireEvent.click(screen.getByRole("button", { name: /Hide it/ }));
    expect(await screen.findByText(/This one's gone/)).toBeInTheDocument();
    expect(calls[0]).toEqual({ url: "/api/feedback/reflection/r1", body: { verdict: "disagree", note: "one bad week" } });
  });

  it("spot on is one tap", async () => {
    wrap(<ReflectionCheck id="r2" />);
    fireEvent.click(screen.getByRole("button", { name: /Spot on/ }));
    expect(await screen.findByText("You said this is spot on.")).toBeInTheDocument();
    expect(calls[0].body).toEqual({ verdict: "agree", note: null });
  });
});

describe("Emoji button", () => {
  it("opens the full picker and inserts at the cursor, several in a row", async () => {
    render(<ChatInput onSend={() => {}} />);
    const box = screen.getByLabelText("Message") as HTMLTextAreaElement;
    fireEvent.change(box, { target: { value: "ok bet" } });
    box.setSelectionRange(2, 2);
    fireEvent.click(screen.getByRole("button", { name: "Add an emoji" }));
    fireEvent.click(await screen.findByRole("button", { name: "pick 😂" }));
    fireEvent.click(screen.getByRole("button", { name: "pick 🔥" }));
    expect(box.value).toBe("ok😂🔥 bet");
    expect(screen.getByPlaceholderText("Search emoji")).toBeInTheDocument();
  });
});
