import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import portrait from "./fixtures/portrait.json";
import reflections from "./fixtures/reflections.json";
import settings from "./fixtures/settings.json";
import system from "./fixtures/system.json";
import timeline30 from "./fixtures/timeline_30d.json";
import timelineAll from "./fixtures/timeline_all.json";

/**
 * The signed-in pages, rendered against payloads captured from the real backend
 * (every personal string replaced, shape untouched). If the API and a page drift
 * apart, the page throws here instead of in front of a user.
 */

type Call = { url: string; method: string; body: unknown };
const calls: Call[] = [];
let overrides: Record<string, (call: Call) => { status?: number; body: unknown }> = {};

const json = (body: unknown, status = 200) =>
  ({ ok: status >= 200 && status < 300, status, json: async () => body, blob: async () => new Blob(["%PDF"]) }) as unknown as Response;

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(async (url: string, init: RequestInit = {}) => {
    const call: Call = { url, method: init.method ?? "GET", body: init.body ? JSON.parse(String(init.body)) : undefined };
    calls.push(call);
    for (const [fragment, handler] of Object.entries(overrides)) {
      if (url.includes(fragment)) {
        const result = handler(call);
        return json(result.body, result.status ?? 200);
      }
    }
    if (url.includes("/persona/portrait/")) return json(portrait);
    if (url.includes("/analytics/timeline/")) return json(url.includes("range=30d") ? timeline30 : timelineAll);
    if (url.includes("/analytics/reflections/")) return json(reflections);
    if (url.includes("/analytics/system/")) return json(system);
    if (url.includes("/analytics/followups/")) {
      return json({
        open: [
          { id: "f1", what: "text landlord about the rent", quote: "i'll text my landlord tomorrow", status: "open", said_on: "2026-11-14", due: "2026-11-15", overdue_by_days: 2, closed_on: null, closed_by: null, conversation_id: "c1" },
        ],
        closed: [
          { id: "f2", what: "finish chapter 3", quote: "ima finish chapter 3 tonight", status: "done", said_on: "2026-11-10", due: "2026-11-10", overdue_by_days: 0, closed_on: "2026-11-11", closed_by: "said_in_chat", conversation_id: null },
        ],
        stats: { done: 3, dropped: 1, follow_through: 0.75 },
      });
    }
    if (url.includes("/user/profile")) {
      return json({
        display_name: "Sam",
        email: "sam@example.com",
        birth_date: "2004-03-14",
        age: 22,
        notifications: { enabled: false, follow_ups: true, weekly_digest: true, daily_check_in: false, check_in_time: "21:00", birthdays: true, quiet_start: "22:30", quiet_end: "08:00" },
        member_since: null,
      });
    }
    if (url.includes("/persona/voice-import")) return json(call.method === "GET" ? { imported: null } : {});
    if (url.includes("/schedule-context/")) {
      return json({
        schedule_context: { classes_per_day: 3, study_hours: 2, has_deadlines: false, is_exam_period: false },
        derived_context: { workload_level: "moderate" },
      });
    }
    if (url.includes("/user/settings/update")) return json({ status: "success" });
    if (url.includes("/user/settings")) return json(settings);
    return json({});
  }),
}));

const signOut = vi.fn(async () => {});
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: { id: "00000000-0000-0000-0000-0000000000aa", display_name: "Sam", email: "sam@example.com" }, signOut, loading: false }),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }));

import { ArchitecturePage } from "@/pages/ArchitecturePage";
import { MemoryPage } from "@/pages/MemoryPage";
import { PersonalityPage } from "@/pages/PersonalityPage";
import { ReflectionsPage } from "@/pages/ReflectionsPage";
import { SettingsPage } from "@/pages/SettingsPage";

function show(page: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{page}</MemoryRouter>
    </QueryClientProvider>,
  );
}

const sent = (fragment: string, method = "POST") => calls.filter((c) => c.url.includes(fragment) && c.method === method);

beforeEach(() => {
  calls.length = 0;
  overrides = {};
  localStorage.setItem("user_id", "00000000-0000-0000-0000-0000000000aa");
});

describe("signed-in pages render real payloads", () => {
  it("Persona shows the shape, four traits and the voice numbers", async () => {
    show(<PersonalityPage />);
    expect(await screen.findByText("How to read it")).toBeInTheDocument();
    for (const trait of portrait.traits) expect(screen.getAllByText(trait.name).length).toBeGreaterThan(0);
    expect(screen.getByText("How you write")).toBeInTheDocument();
    expect(screen.getByText("When you talk")).toBeInTheDocument();
    expect(document.querySelectorAll("svg").length).toBeGreaterThan(3);
  });

  it("Persona explains itself when nothing has been learned yet", async () => {
    overrides["/persona/portrait/"] = () => ({ body: { ...portrait, traits: [], trait_series: [], reflections: [], voice: { messages: 0 } } });
    show(<PersonalityPage />);
    expect(await screen.findByText(/hasn't seen enough of you yet/)).toBeInTheDocument();
  });

  it("Timeline lists every day and refetches when the range changes", async () => {
    show(<MemoryPage />);
    expect(await screen.findByText("Milestones")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem").length).toBeGreaterThanOrEqual(timelineAll.days.length);
    fireEvent.click(screen.getByRole("button", { name: "30 days" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("range=30d"))).toBe(true));
  });

  it("Reflections shows each pattern with its quotes and does not auto-generate when some exist", async () => {
    show(<ReflectionsPage />);
    expect(await screen.findByText(reflections.reflections[0].title)).toBeInTheDocument();
    expect(screen.getAllByText("In your words").length).toBe(reflections.reflections.length);
    expect(sent("/generate")).toHaveLength(0);
  });

  it("Reflections writes the first set by itself when there is enough to read", async () => {
    const empty = { reflections: [], earlier: [], status: { ...reflections.status, generated_at: null, can_generate: true, new_messages_since: 40 } };
    overrides["/generate"] = () => ({ body: reflections });
    overrides["/analytics/reflections/"] = () => ({ body: empty });
    show(<ReflectionsPage />);
    await waitFor(() => expect(sent("/generate")).toHaveLength(1));
  });

  it("Reflections lists loose ends and settles one", async () => {
    show(<ReflectionsPage />);
    expect(await screen.findByText("text landlord about the rent")).toBeInTheDocument();
    expect(screen.getByText(/followed through on 75%/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: 'Mark "text landlord about the rent" as done' }));
    await waitFor(() => expect(sent("/analytics/followups/")).toHaveLength(1));
    expect(sent("/analytics/followups/")[0].url).toContain("status=done");
  });

  it("How it works renders the rules and the user's live numbers", async () => {
    show(<ArchitecturePage />);
    await waitFor(() => expect(calls.some((c) => c.url.includes("/analytics/system/"))).toBe(true));
    await waitFor(() => expect(document.body.textContent).toContain(String(system.rules.memory.messages_searched)));
    expect(document.body.textContent).not.toMatch(/NaN|undefined/);
  });
});

describe("Settings", () => {
  it("shows About you with the age worked out from the birth date", async () => {
    show(<SettingsPage />);
    expect(await screen.findByText(/you're 22/)).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Notifications" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("switch", { name: "Follow-ups" })).toBeDisabled(); // off until notifications are on
  });

  it("offers the voice import and the animated PDF export", async () => {
    show(<SettingsPage />);
    expect(await screen.findByText("Teach Mirror how you text")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import your own chats" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /PDF/ }));
    expect(await screen.findByRole("dialog", { name: "Exporting your portrait" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Developing your/ })).toBeInTheDocument();
    await waitFor(() => expect(calls.some((c) => c.url.includes("/user/export-persona-report"))).toBe(true));
    expect(calls.find((c) => c.url.includes("/user/export-persona-report"))!.url).toContain("tz_offset_minutes=");
  });

  it("saves a switch with the full settings object and rolls back if the server refuses", async () => {
    show(<SettingsPage />);
    const learning = await screen.findByRole("switch", { name: "Keep learning about me" });
    await waitFor(() => expect(learning).not.toBeDisabled());
    expect(learning).toHaveAttribute("aria-checked", String(settings.settings.pattern_tracking));

    fireEvent.click(learning);
    await waitFor(() => expect(sent("/user/settings/update")).toHaveLength(1));
    expect(sent("/user/settings/update")[0].body).toMatchObject({
      pattern_tracking: !settings.settings.pattern_tracking,
      persona_mirroring: settings.settings.persona_mirroring,
      daily_reflections: expect.any(Boolean),
    });

    overrides["/user/settings/update"] = () => ({ status: 500, body: { detail: "Database is down" } });
    await waitFor(() => expect(learning).not.toBeDisabled());
    const before = learning.getAttribute("aria-checked");
    fireEvent.click(learning);
    expect(await screen.findByText("Database is down")).toBeInTheDocument();
    expect(learning).toHaveAttribute("aria-checked", before);
  });

  it("sends the chosen mirror strength", async () => {
    show(<SettingsPage />);
    const light = await screen.findByRole("radio", { name: /Light/ });
    await waitFor(() => expect(light).not.toBeDisabled());
    fireEvent.click(light);
    await waitFor(() => expect(sent("/user/settings/update")).toHaveLength(1));
    expect(sent("/user/settings/update")[0].body).toMatchObject({ twin_mirror_intensity: 0.3 });
    await waitFor(() => expect(light).toHaveAttribute("aria-checked", "true"));
  });

  it("import previews first and only saves on the second step", async () => {
    const result = {
      saved: false,
      recognised: 1,
      total_traits: 4,
      notes: ["Works as a nurse"],
      traits: [
        { trait: "communication_style", applied: true, strength: "strong", evidence: "keeps messages short", previous_score: 0.5, new_score: 0.31, previous_confidence: 0.2, new_confidence: 0.4 },
        { trait: "reflection_depth", applied: false, strength: "none", evidence: "", previous_score: 0.5, new_score: 0.5, previous_confidence: 0.2, new_confidence: 0.2 },
      ],
    };
    overrides["/persona/bootstrap"] = () => ({ body: result });
    show(<SettingsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Import a description of you" }));

    const read = await screen.findByRole("button", { name: "Read it" });
    expect(read).toBeDisabled(); // under 40 words
    fireEvent.change(screen.getByLabelText("Description of you"), { target: { value: Array(45).fill("word").join(" ") } });
    expect(read).not.toBeDisabled();
    fireEvent.click(read);

    expect(await screen.findByText("“keeps messages short”")).toBeInTheDocument();
    expect(screen.getByText("Works as a nurse", { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/not mentioned/)).toBeInTheDocument();
    expect(sent("/persona/bootstrap")).toHaveLength(1);
    expect(sent("/persona/bootstrap")[0].body).toMatchObject({ dry_run: true });

    fireEvent.click(screen.getByRole("button", { name: "Save 1 reading" }));
    await waitFor(() => expect(sent("/persona/bootstrap")).toHaveLength(2));
    expect(sent("/persona/bootstrap")[1].body).toMatchObject({ dry_run: false });
  });

  it("import shows the server's reason instead of failing silently", async () => {
    overrides["/persona/bootstrap"] = () => ({ status: 503, body: { detail: "The AI is busy. Nothing was changed." } });
    show(<SettingsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Import a description of you" }));
    fireEvent.change(await screen.findByLabelText("Description of you"), { target: { value: Array(45).fill("word").join(" ") } });
    fireEvent.click(screen.getByRole("button", { name: "Read it" }));
    expect(await screen.findByText("The AI is busy. Nothing was changed.")).toBeInTheDocument();
  });

  it("erase stays locked until CLEAR is typed, then calls the server once", async () => {
    show(<SettingsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Erase" }));
    const confirm = await screen.findByRole("button", { name: "Erase", hidden: false });
    const dialog = screen.getByRole("alertdialog");
    const action = Array.from(dialog.querySelectorAll("button")).find((b) => b.textContent?.trim() === "Erase") as HTMLButtonElement;
    expect(confirm).toBeTruthy();
    expect(action).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Type CLEAR to confirm"), { target: { value: "clear" } });
    expect(action).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Type CLEAR to confirm"), { target: { value: "CLEAR" } });
    expect(action).not.toBeDisabled();
    fireEvent.click(action);
    await waitFor(() => expect(sent("/user/clear-data")).toHaveLength(1));
    expect(sent("/user/delete-account", "DELETE")).toHaveLength(0);
  });

  it("delete account needs DELETE typed and signs the user out", async () => {
    show(<SettingsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /^Delete$/ }));
    const dialog = await screen.findByRole("alertdialog");
    const action = Array.from(dialog.querySelectorAll("button")).find((b) => b.textContent?.trim() === "Delete account") as HTMLButtonElement;
    expect(action).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Type DELETE to confirm"), { target: { value: "DELETE" } });
    fireEvent.click(action);
    await waitFor(() => expect(sent("/user/delete-account", "DELETE")).toHaveLength(1));
    await waitFor(() => expect(signOut).toHaveBeenCalled());
  });
});
