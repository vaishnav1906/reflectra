import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

/** Data hooks for the Persona, Timeline, Reflections and How-it-works pages. */

export type TraitKey = "communication_style" | "emotional_expressiveness" | "decision_framing" | "reflection_depth";

export const TRAIT_ORDER: TraitKey[] = [
  "communication_style",
  "emotional_expressiveness",
  "decision_framing",
  "reflection_depth",
];

export const TRAIT_COLOR: Record<TraitKey, string> = {
  communication_style: "hsl(var(--iris-cyan))",
  emotional_expressiveness: "hsl(var(--iris-peach))",
  decision_framing: "hsl(var(--iris-violet))",
  reflection_depth: "hsl(var(--trait-empathetic))",
};

export const TRAIT_LABEL: Record<TraitKey, { name: string; low: string; high: string }> = {
  communication_style: { name: "Communication", low: "Concise", high: "Elaborate" },
  emotional_expressiveness: { name: "Emotional expressiveness", low: "Reserved", high: "Open" },
  decision_framing: { name: "Decision framing", low: "Hesitant", high: "Decisive" },
  reflection_depth: { name: "Reflection depth", low: "Surface", high: "Deep" },
};

export interface PortraitTrait {
  key: TraitKey;
  name: string;
  low: string;
  high: string;
  score: number;
  confidence: number;
  confidence_label: string;
  evidence_count: number;
  reading: string;
  feedback?: { verdict: "agree" | "disagree"; self_score: number | null; on: string | null } | null;
}

export type TraitPoint = { date: string; stability?: number | null } & Partial<Record<TraitKey, number | null>>;

export interface Evidence {
  quote: string;
  date: string | null;
  conversation_id: string | null;
}

export interface Reflection {
  id: string;
  title: string;
  insight: string;
  theme: string;
  evidence: Evidence[];
  confidence: number | null;
  created_at: string | null;
  feedback?: "agree" | "disagree" | null;
}

export interface Milestone {
  date: string;
  kind: string;
  text: string;
}

export interface Portrait {
  name: string;
  headline: string;
  first_date: string | null;
  last_date: string | null;
  active_days: number;
  user_messages: number;
  conversations: number;
  longest_streak: number;
  busiest_day: { date: string; user_messages: number } | null;
  conversations_by_mode: Record<string, number>;
  traits: PortraitTrait[];
  trait_series: TraitPoint[];
  milestones: Milestone[];
  reflections: Reflection[];
  reflections_read: number;
  hour_histogram: number[];
  weekday_histogram: number[];
  adaptation: string[];
  voice: {
    messages: number;
    median_words?: number;
    longest_words?: number;
    lowercase_share?: number;
    question_share?: number;
    emoji_share?: number;
    no_period_share?: number;
    abbreviations?: { word: string; count: number }[];
    phrases?: string[];
  };
}

export interface TimelineDay {
  date: string;
  user_messages: number;
  mood: number | null;
  depth: number | null;
  highlight: string | null;
  conversations: { id: string; title: string; mode: string; user_messages: number }[];
}

export interface Timeline {
  range: string;
  summary: {
    first_date: string | null;
    last_date: string | null;
    active_days: number;
    user_messages: number;
    conversations: number;
    longest_streak: number;
    busiest_day: { date: string; user_messages: number } | null;
    avg_messages_per_active_day: number;
    conversations_by_mode: Record<string, number>;
  };
  days: TimelineDay[];
  trait_series: TraitPoint[];
  milestones: Milestone[];
}

export interface ReflectionsState {
  reflections: Reflection[];
  earlier: Reflection[];
  status: {
    generated_at: string | null;
    messages_available: number;
    messages_read: number;
    new_messages_since: number;
    can_generate: boolean;
    reason: string | null;
    pattern_tracking: boolean;
  };
}

export interface SystemFacts {
  rules: {
    traits: {
      count: number;
      max_step_per_message: number;
      inertia: number;
      confidence_gain: number;
      confidence_loss: number;
      agree_within: number;
      conflict_beyond: number;
      confidence_floor: number;
      confidence_ceiling: number;
      snapshot_hours: number;
    };
    memory: {
      messages_searched: number;
      related_recalled: number;
      recent_recalled: number;
      turns_in_context: number;
      by_meaning?: boolean;
      meaning_min_similarity?: number;
      meaning_min_standout?: number;
    };
    mirror: { voice_samples: number; max_attempts: number };
    confidence: {
      source_weights: Record<string, number>;
      tiers: { tier: string; up_to: number; phrase_usage_frequency: number; tone_strength: number; style_enforcement_intensity: number }[];
    };
    reflections: { messages_read: number; min_messages: number; min_quotes: number };
    bootstrap: { confidence_by_evidence: Record<string, number>; counts_as_messages?: Record<string, number> };
    ai: { provider: string | null; reply_model: string | null; fast_model: string | null; hedge_seconds: number | null };
  };
  you: {
    messages: number;
    conversations: number;
    memory?: { by_meaning: number; recallable: number };
    feedback?: {
      replies: Record<string, { up: number; down: number }>;
      reasons: { reason: string; label: string; count: number }[];
      traits: { agree: number; disagree: number };
      reflections: { agree: number; disagree: number };
    };
    traits: { key: TraitKey; score: number; confidence: number; evidence_count: number }[];
    confidence: {
      center: number;
      interval: { lower: number; upper: number };
      tier: string;
      source_scores: Record<string, number>;
      source_contributions: Record<string, number>;
      facts?: Record<string, number>;
    };
    voice_samples_available: number;
    mirror: { replies_measured: number; avg_seconds: number | null; fallback_rate: number | null };
    reflections: number;
  };
}

const tzOffset = () => -new Date().getTimezoneOffset();

async function getJson<T>(url: string): Promise<T> {
  const res = await apiFetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body?.detail === "string" ? body.detail : `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

function useUserId(): string | null {
  return useAuth().user?.id ?? null;
}

export function usePortrait() {
  const userId = useUserId();
  return useQuery({
    queryKey: ["portrait", userId],
    enabled: Boolean(userId),
    staleTime: 30_000,
    queryFn: () => getJson<Portrait>(`/api/persona/portrait/${userId}?tz_offset_minutes=${tzOffset()}`),
  });
}

export function useTimeline(range: string) {
  const userId = useUserId();
  return useQuery({
    queryKey: ["timeline", userId, range],
    enabled: Boolean(userId),
    staleTime: 30_000,
    queryFn: () => getJson<Timeline>(`/api/analytics/timeline/${userId}?range=${range}&tz_offset_minutes=${tzOffset()}`),
  });
}

export function useReflections() {
  const userId = useUserId();
  return useQuery({
    queryKey: ["reflections", userId],
    enabled: Boolean(userId),
    staleTime: 30_000,
    queryFn: () => getJson<ReflectionsState>(`/api/analytics/reflections/${userId}`),
  });
}

export function useGenerateReflections() {
  const userId = useUserId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (force: boolean) => {
      const res = await apiFetch(`/api/analytics/reflections/${userId}/generate?force=${force}`, { method: "POST" });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof body?.detail === "string" ? body.detail : "Couldn't write reflections right now.");
      }
      return body as ReflectionsState;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["reflections", userId], data);
      void queryClient.invalidateQueries({ queryKey: ["portrait", userId] });
    },
  });
}

export function useSystemFacts() {
  const userId = useUserId();
  return useQuery({
    queryKey: ["system", userId],
    enabled: Boolean(userId),
    staleTime: 30_000,
    queryFn: () => getJson<SystemFacts>(`/api/analytics/system/${userId}`),
  });
}

export function formatDay(iso: string | null | undefined, options: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }): string {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1).toLocaleDateString(undefined, options);
}

export const pct = (value: number | null | undefined) => `${Math.round((value ?? 0) * 100)}`;

export interface FollowUp {
  id: string;
  what: string;
  quote: string;
  status: "open" | "done" | "dropped";
  said_on: string;
  due: string;
  overdue_by_days: number;
  closed_on: string | null;
  closed_by: string | null;
  conversation_id: string | null;
}

export interface FollowUps {
  open: FollowUp[];
  closed: FollowUp[];
  stats: { done: number; dropped: number; follow_through: number | null };
}

export function useFollowUps() {
  const userId = useUserId();
  return useQuery({
    queryKey: ["followups", userId],
    enabled: Boolean(userId),
    staleTime: 30_000,
    queryFn: () => getJson<FollowUps>(`/api/analytics/followups/${userId}?tz_offset_minutes=${tzOffset()}`),
  });
}

export function useSetFollowUp() {
  const userId = useUserId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, status }: { id: string; status: "done" | "dropped" | "open" }) => {
      const res = await apiFetch(`/api/analytics/followups/${userId}/${id}?status=${status}&tz_offset_minutes=${tzOffset()}`, { method: "POST" });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Couldn't update that.");
      return body as FollowUps;
    },
    onSuccess: (data) => queryClient.setQueryData(["followups", userId], data),
  });
}

export type PersonGroup = "family" | "partner" | "friends" | "work" | "other";

export interface PersonNote {
  id: string;
  text: string;
  quote: string | null;
  date: string | null;
  conversation_id: string | null;
  source: "chat" | "you";
}

export interface Person {
  id: string;
  name: string;
  aliases: string[];
  relationship: string | null;
  group: PersonGroup;
  description: string | null;
  birthday: string | null;
  birthday_note: string | null;
  notes: PersonNote[];
  status: "active" | "suggested" | "dismissed";
  mention_count: number;
  last_mentioned_at: string | null;
  created_at: string | null;
}

export interface PersonFields {
  name?: string;
  relationship?: string | null;
  description?: string | null;
  aliases?: string[];
  birthday?: string | null;
}

export function usePeople() {
  const userId = useUserId();
  return useQuery({
    queryKey: ["people", userId],
    enabled: Boolean(userId),
    staleTime: 15_000,
    queryFn: () => getJson<{ people: Person[]; suggestions: Person[] }>("/api/people"),
  });
}

async function sendJson<T>(url: string, method: string, body?: unknown): Promise<T> {
  const res = await apiFetch(url, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Couldn't save that.");
  return data as T;
}

/** Every change to People goes through here and refreshes the list. */
export function usePeopleActions() {
  const userId = useUserId();
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["people", userId] });
  const wrap = <A extends unknown[], R>(fn: (...args: A) => Promise<R>) =>
    async (...args: A) => {
      const result = await fn(...args);
      await refresh();
      return result;
    };
  return {
    add: wrap((fields: PersonFields) => sendJson<Person>("/api/people", "POST", fields)),
    edit: wrap((id: string, fields: PersonFields) => sendJson<Person>(`/api/people/${id}`, "PATCH", fields)),
    accept: wrap((id: string, fields: PersonFields = {}) => sendJson<Person>(`/api/people/${id}/accept`, "POST", fields)),
    dismiss: wrap((id: string) => sendJson(`/api/people/${id}/dismiss`, "POST")),
    remove: wrap((id: string) => sendJson(`/api/people/${id}`, "DELETE")),
    addNote: wrap((id: string, text: string) => sendJson<Person>(`/api/people/${id}/notes`, "POST", { text })),
    removeNote: wrap((id: string, noteId: string) => sendJson<Person>(`/api/people/${id}/notes/${noteId}`, "DELETE")),
  };
}

export type LifeKind = "about" | "situation" | "goal" | "preference" | "routine" | "place";

export interface LifeFact {
  id: string;
  kind: LifeKind;
  kind_label: string;
  text: string;
  quote: string | null;
  source: "chat" | "you";
  status: "active" | "resolved" | "outdated";
  pinned: boolean;
  mention_count: number;
  first_seen: string | null;
  last_seen: string | null;
  conversation_id: string | null;
}

export interface LifeMemory {
  facts: LifeFact[];
  kinds: { kind: LifeKind; label: string }[];
  in_replies: string[];
  reading_history: boolean;
}

export function useLifeMemory() {
  const userId = useUserId();
  return useQuery({
    queryKey: ["life", userId],
    enabled: Boolean(userId),
    staleTime: 10_000,
    // While past chats are being read in the background, check back every few seconds.
    refetchInterval: (query) => ((query.state.data as LifeMemory | undefined)?.reading_history ? 4000 : false),
    queryFn: () => getJson<LifeMemory>("/api/life"),
  });
}

export function useLifeActions() {
  const userId = useUserId();
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["life", userId] });
  const wrap = <A extends unknown[], R>(fn: (...args: A) => Promise<R>) =>
    async (...args: A) => {
      const result = await fn(...args);
      await refresh();
      return result;
    };
  return {
    add: wrap((kind: LifeKind, text: string) => sendJson<LifeFact>("/api/life", "POST", { kind, text })),
    edit: wrap((id: string, fields: Partial<Pick<LifeFact, "kind" | "text" | "status" | "pinned">>) =>
      sendJson<LifeFact>(`/api/life/${id}`, "PATCH", fields),
    ),
    remove: wrap((id: string) => sendJson(`/api/life/${id}`, "DELETE")),
    readHistory: wrap(() => sendJson<{ queued: boolean }>("/api/life/read-history", "POST")),
  };
}
