// A made-up person, "Maya", for screenshots and the demo video.
// Every API response the app asks for is answered from here, so no real account
// or real conversation ever appears in the README media.

const DAY = 86_400_000;
const now = new Date();
const iso = (d) => new Date(d).toISOString();
const dayOnly = (d) => iso(d).slice(0, 10);
const ago = (days, hours = 0) => new Date(now.getTime() - days * DAY - hours * 3_600_000);

export const USER = {
  id: "00000000-0000-4000-8000-000000000001",
  display_name: "Maya Rao",
  email: "maya@example.com",
};

const CONV = {
  thesis: "10000000-0000-4000-8000-000000000001",
  ananya: "10000000-0000-4000-8000-000000000002",
  sunday: "10000000-0000-4000-8000-000000000003",
  mirror: "10000000-0000-4000-8000-000000000004",
  run: "10000000-0000-4000-8000-000000000005",
  newChat: "10000000-0000-4000-8000-000000000099",
};

// ---------------------------------------------------------------- traits
const TRAITS = [
  {
    key: "communication_style", name: "Communication", low: "Concise", high: "Elaborate",
    score: 0.34, confidence: 0.66, evidence_count: 141, confidence_label: "well established",
    reading: "You get to the point. Your messages are short and you rarely pad them.",
    feedback: { verdict: "agree", self_score: null, on: iso(ago(6)) },
  },
  {
    key: "emotional_expressiveness", name: "Emotional expressiveness", low: "Reserved", high: "Open",
    score: 0.71, confidence: 0.64, evidence_count: 102, confidence_label: "well established",
    reading: "You say how you feel, plainly and often.", feedback: null,
  },
  {
    key: "decision_framing", name: "Decision framing", low: "Hesitant", high: "Decisive",
    score: 0.44, confidence: 0.52, evidence_count: 88, confidence_label: "taking shape",
    reading: "You are quick on small calls and careful on big ones.", feedback: null,
  },
  {
    key: "reflection_depth", name: "Reflection depth", low: "Surface", high: "Deep",
    score: 0.77, confidence: 0.69, evidence_count: 77, confidence_label: "well established",
    reading: "You dig for the why behind what you do.", feedback: null,
  },
];

function traitSeries(days) {
  const out = [];
  for (let i = days.length - 1; i >= 0; i--) {
    const t = 1 - i / Math.max(1, days.length - 1);
    const wobble = (k) => Math.sin(i * 1.7 + k) * 0.04 * (1 - t);
    out.push({
      date: dayOnly(days[i]),
      stability: 0.4 + 0.45 * t,
      communication_style: 0.5 + (0.34 - 0.5) * t + wobble(1),
      emotional_expressiveness: 0.5 + (0.71 - 0.5) * t + wobble(2),
      decision_framing: 0.5 + (0.44 - 0.5) * t + wobble(3),
      reflection_depth: 0.5 + (0.77 - 0.5) * t + wobble(4),
    });
  }
  return out;
}

// ---------------------------------------------------------------- reflections
const REFLECTIONS = [
  {
    id: "20000000-0000-4000-8000-000000000001",
    title: "Deadlines are when you finally start",
    insight:
      "You plan early and genuinely mean it, but the real work only begins once the date feels close. The guilt in between costs you more energy than the work itself.",
    theme: "work",
    evidence: [
      { date: dayOnly(ago(41)), quote: "i had three weeks for this model and i started it last night", conversation_id: CONV.thesis },
      { date: dayOnly(ago(9)), quote: "why do i only start working when it's basically too late", conversation_id: CONV.thesis },
    ],
    confidence: 0.78,
    created_at: iso(ago(2)),
    feedback: "agree",
  },
  {
    id: "20000000-0000-4000-8000-000000000002",
    title: "Ananya is where you go to think out loud",
    insight:
      "When something is bothering you, a call with Ananya comes up before you've decided anything. You use her to hear your own thoughts, not to get answers.",
    theme: "relationships",
    evidence: [
      { date: dayOnly(ago(23)), quote: "called ananya and halfway through i realised what i actually wanted", conversation_id: CONV.ananya },
      { date: dayOnly(ago(5)), quote: "gonna call ananya, i think better when i say it out loud", conversation_id: CONV.ananya },
    ],
    confidence: 0.71,
    created_at: iso(ago(2)),
    feedback: null,
  },
  {
    id: "20000000-0000-4000-8000-000000000003",
    title: "Running resets your head",
    insight: "On days you run before class you describe yourself as calmer and more focused, and you notice it every time.",
    theme: "health",
    evidence: [
      { date: dayOnly(ago(30)), quote: "ran before studio and honestly my head is so much clearer", conversation_id: CONV.run },
      { date: dayOnly(ago(12)), quote: "skipped my run again and i feel foggy all day", conversation_id: CONV.run },
      { date: dayOnly(ago(3)), quote: "the run this morning made the whole day feel lighter", conversation_id: CONV.run },
    ],
    confidence: 0.69,
    created_at: iso(ago(2)),
    feedback: null,
  },
];

// ---------------------------------------------------------------- timeline
const ACTIVE_DAY_OFFSETS = [0, 1, 3, 4, 6, 9, 12, 16, 20, 23, 27, 30, 35, 41, 48, 56, 63, 77, 92, 110, 131, 156, 181, 199];
const HIGHLIGHTS = [
  "the run this morning made the whole day feel lighter",
  "gonna call ananya, i think better when i say it out loud",
  "submitted the site analysis. finally.",
  "mom called and asked about placements again lol",
  "why do i only start working when it's basically too late",
  "kabir cooked tonight, small win",
  "skipped my run again and i feel foggy all day",
  "presented my concept and prof iyer actually liked it",
  "called ananya and halfway through i realised what i actually wanted",
  "ran before studio and honestly my head is so much clearer",
];
const TITLES = ["Thesis panic, round two", "Call with Ananya", "Sunday reset", "Morning run", "Placement talk with Mom", "Studio crit", "Late-night model making", "Flat dinner with Kabir"];

function timelineDays(rangeDays) {
  const offsets = ACTIVE_DAY_OFFSETS.filter((o) => rangeDays == null || o < rangeDays);
  return offsets.map((o, i) => {
    const messages = [9, 14, 6, 11, 4, 17, 8, 12, 5, 21, 7, 10][i % 12];
    return {
      date: dayOnly(ago(o)),
      user_messages: messages,
      mood: [0.5, -0.4, 0.1, 0.6, -0.1, 0.3][i % 6],
      depth: 0.3 + ((i * 37) % 60) / 100,
      highlight: HIGHLIGHTS[i % HIGHLIGHTS.length],
      conversations: [
        { id: Object.values(CONV)[i % 5], title: TITLES[i % TITLES.length], mode: i % 4 === 3 ? "mirror" : "reflection", user_messages: messages },
        ...(i % 3 === 0 ? [{ id: Object.values(CONV)[(i + 2) % 5], title: TITLES[(i + 3) % TITLES.length], mode: "reflection", user_messages: 3 }] : []),
      ],
    };
  });
}

const MILESTONES = [
  { date: dayOnly(ago(2)), kind: "reflection", text: "Reflectra noticed a new pattern: Deadlines are when you finally start." },
  { date: dayOnly(ago(18)), kind: "trait", text: "Your reflection depth settled on the deep side and has stayed there (now 77/100)." },
  { date: dayOnly(ago(46)), kind: "import", text: "Imported 420 of your WhatsApp messages so Mirror sounds like you." },
  { date: dayOnly(ago(92)), kind: "activity", text: "Your most talkative day: 31 messages." },
  { date: dayOnly(ago(131)), kind: "trait", text: "Your emotional expressiveness settled on the open side (now 71/100)." },
  { date: dayOnly(ago(199)), kind: "start", text: "Your first conversation with Reflectra." },
];

function timeline(range) {
  const rangeDays = { "7d": 7, "30d": 30, "90d": 90, "1y": 365 }[range] ?? null;
  const days = timelineDays(rangeDays);
  const total = days.reduce((s, d) => s + d.user_messages, 0);
  const convs = days.reduce((s, d) => s + d.conversations.length, 0);
  return {
    range_days: rangeDays,
    summary: {
      first_date: days.at(-1)?.date ?? null,
      last_date: days[0]?.date ?? null,
      active_days: days.length,
      user_messages: rangeDays ? total : 412,
      conversations: rangeDays ? convs : 63,
      longest_streak: rangeDays === 7 ? 2 : 4,
      busiest_day: days.length ? { date: days[5 % days.length].date, user_messages: rangeDays ? Math.max(...days.map((d) => d.user_messages)) : 31 } : null,
      avg_messages_per_active_day: days.length ? Math.round((total / days.length) * 10) / 10 : 0,
      conversations_by_mode: { reflection: Math.round(convs * 0.75), mirror: Math.round(convs * 0.25) },
    },
    days,
    trait_series: traitSeries(days.map((d) => new Date(d.date))),
    milestones: MILESTONES.filter((m) => rangeDays == null || new Date(m.date) >= ago(rangeDays)),
    range: range || "all",
  };
}

// ---------------------------------------------------------------- portrait
function portrait() {
  const t = timeline("all");
  return {
    name: "Maya",
    generated_at: iso(now),
    first_date: t.summary.first_date,
    last_date: t.summary.last_date,
    active_days: 58,
    user_messages: 412,
    conversations: 63,
    longest_streak: 4,
    busiest_day: { date: dayOnly(ago(92)), user_messages: 31 },
    conversations_by_mode: { reflection: 47, mirror: 16 },
    traits: TRAITS,
    trait_series: t.trait_series,
    milestones: MILESTONES,
    reflections: REFLECTIONS,
    reflections_read: 160,
    hour_histogram: [14, 9, 4, 1, 0, 0, 2, 9, 12, 7, 6, 8, 10, 7, 6, 9, 11, 13, 15, 18, 24, 31, 37, 29],
    weekday_histogram: [58, 61, 49, 66, 44, 52, 82],
    voice: {
      messages: 160,
      median_words: 11,
      longest_words: 94,
      lowercase_share: 0.83,
      question_share: 0.22,
      emoji_share: 0.08,
      no_period_share: 0.71,
      abbreviations: [{ word: "ngl", count: 14 }, { word: "lol", count: 22 }, { word: "rn", count: 9 }, { word: "tbh", count: 6 }],
      phrases: ["honestly", "small win", "i think better when"],
    },
    headline: "Digs for the why, and open about feelings.",
    adaptation: [
      "Keeps its replies short, because you do.",
      "Meets feelings head-on instead of steering around them.",
      "Goes after the why with you, not just the what.",
      "In Mirror mode it writes in lowercase, the way you do.",
    ],
  };
}

// ---------------------------------------------------------------- people
const PEOPLE = [
  {
    id: "30000000-0000-4000-8000-000000000001", name: "Ananya", aliases: ["anu"], relationship: "best friend", group: "friends",
    description: "Known her since school. Brutally honest, the first person I call when I'm stuck.",
    birthday: "1999-02-14", birthday_note: null, mention_count: 23, last_mentioned_at: iso(ago(0, 3)), created_at: iso(ago(120)),
    notes: [
      { id: "n1", date: dayOnly(ago(5)), text: "Helped you decide to ask for the thesis extension", quote: "gonna call ananya, i think better when i say it out loud", source: "chat" },
      { id: "n2", date: dayOnly(ago(23)), text: "Talking to her is how you work out what you want", quote: null, source: "chat" },
    ],
  },
  {
    id: "30000000-0000-4000-8000-000000000002", name: "Mom", aliases: ["amma"], relationship: "mother", group: "family",
    description: "Worries a lot, asks about placements every call. Means well.",
    birthday: null, birthday_note: null, mention_count: 15, last_mentioned_at: iso(ago(1)), created_at: iso(ago(150)),
    notes: [{ id: "n3", date: dayOnly(ago(1)), text: "Asked about placements again", quote: "mom called and asked about placements again lol", source: "chat" }],
  },
  {
    id: "30000000-0000-4000-8000-000000000003", name: "Rohan", aliases: [], relationship: "younger brother", group: "family",
    description: "In 11th grade. Wants to do design like me.", birthday: null, birthday_note: null, mention_count: 6,
    last_mentioned_at: iso(ago(16)), created_at: iso(ago(140)), notes: [],
  },
  {
    id: "30000000-0000-4000-8000-000000000004", name: "Prof. Iyer", aliases: ["iyer"], relationship: "thesis guide", group: "work",
    description: "Strict but fair. Likes bold concepts, hates late submissions.", birthday: null, birthday_note: null, mention_count: 11,
    last_mentioned_at: iso(ago(4)), created_at: iso(ago(90)), notes: [],
  },
  {
    id: "30000000-0000-4000-8000-000000000005", name: "Kabir", aliases: [], relationship: "flatmate", group: "friends",
    description: "Cooks when I'm drowning in deadlines. Terrible at doing dishes.", birthday: null, birthday_note: null, mention_count: 8,
    last_mentioned_at: iso(ago(6)), created_at: iso(ago(80)), notes: [],
  },
  {
    id: "30000000-0000-4000-8000-000000000006", name: "Meera", aliases: [], relationship: "studio partner", group: "work",
    description: "Splits the model-making with me. Calm under pressure.", birthday: null, birthday_note: null, mention_count: 4,
    last_mentioned_at: iso(ago(35)), created_at: iso(ago(60)), notes: [],
  },
].map((p) => ({ ...p, status: "active" }));

const SUGGESTIONS = [
  {
    id: "30000000-0000-4000-8000-000000000009", name: "Dev", aliases: [], relationship: "classmate", group: "friends", description: null,
    birthday: null, birthday_note: null, mention_count: 3, last_mentioned_at: iso(ago(2)), created_at: iso(ago(9)), status: "suggested",
    notes: [{ id: "n9", date: dayOnly(ago(2)), text: "Offered to share his site photos", quote: "dev said he'd send me his site photos tonight", source: "chat" }],
  },
];

// ---------------------------------------------------------------- your life
const LIFE_KINDS = [
  { kind: "about", label: "About you" },
  { kind: "situation", label: "Going on now" },
  { kind: "goal", label: "Working toward" },
  { kind: "routine", label: "Routines" },
  { kind: "preference", label: "Likes and dislikes" },
  { kind: "place", label: "Places" },
];
const fact = (id, kind, text, quote, extra = {}) => ({
  id: `40000000-0000-4000-8000-00000000000${id}`, kind, kind_label: LIFE_KINDS.find((k) => k.kind === kind).label, text, quote,
  source: "chat", status: "active", pinned: false, mention_count: 1, first_seen: dayOnly(ago(60)), last_seen: dayOnly(ago(3)),
  conversation_id: CONV.thesis, ...extra,
});
const LIFE = [
  fact(1, "about", "Final-year architecture student in Bengaluru", "final year of arch and it's eating me alive", { pinned: true, mention_count: 9 }),
  fact(2, "about", "Lives with a flatmate, Kabir", null, { mention_count: 4 }),
  fact(3, "situation", "Thesis submission is due on 12 December", "thesis is due dec 12 and i'm not ready", { pinned: true, mention_count: 6 }),
  fact(4, "situation", "Interviewing for design internships", "two internship interviews next week", { mention_count: 3 }),
  fact(5, "goal", "Wants a studio job in Mumbai after graduating", "i really want to end up at a studio in bombay", { mention_count: 2 }),
  fact(6, "routine", "Runs before morning classes", "ran before studio and honestly my head is so much clearer", { mention_count: 5 }),
  fact(7, "preference", "Works best late at night with music on", null, { mention_count: 3, source: "you" }),
  fact(8, "place", "Grew up in Mysuru", null, { mention_count: 2, source: "you" }),
];

// ---------------------------------------------------------------- chat
const THESIS_MESSAGES = [
  ["user", "ok i have 3 weeks till thesis submission and i've done basically nothing on the model", 3, 50],
  ["assistant", "Three weeks is tight but real. What's actually stopping you: not knowing where to start, or knowing and dreading it?", 3, 49],
  ["user", "dreading it ngl. every time i open the file i feel behind", 3, 47],
  ["assistant", "That 'behind' feeling is the same one you described before your site analysis, and you finished that in four days once you started. What's the smallest piece you could do tonight?", 3, 46],
  ["user", "probably just the massing. like 2 hours", 3, 44],
  ["assistant", "Two hours of massing, then stop, even if it's going well. Want me to check in tomorrow on how it went?", 3, 43],
];
const conversationMessages = (id) =>
  THESIS_MESSAGES.map(([role, content, days, minutes], i) => ({
    id: `50000000-0000-4000-8000-0000000000${String(i).padStart(2, "0")}`,
    conversation_id: id,
    role,
    content,
    created_at: new Date(ago(days).getTime() + (60 - minutes) * 60_000).toISOString(),
    feedback: i === 3 ? "up" : null,
    feedback_reasons: [],
  }));

const CONVERSATIONS = [
  { id: CONV.thesis, title: "Thesis panic, round two", created_at: iso(ago(3)) },
  { id: CONV.ananya, title: "Call with Ananya", created_at: iso(ago(5)) },
  { id: CONV.sunday, title: "Sunday reset", created_at: iso(ago(9)) },
  { id: CONV.run, title: "Morning run", created_at: iso(ago(12)) },
];

export const DEMO_MESSAGE = "had a weird day. ananya cancelled our call and now i'm just staring at the thesis file";
export const DEMO_REPLY =
  "That's a lot to sit with at once. Ananya is usually where you go to think things through out loud, so losing that call probably left the thesis feeling heavier. Last week you said two hours of massing felt doable. Want to start with just that tonight?";

function chatStream() {
  const words = DEMO_REPLY.split(" ");
  const partials = [];
  for (let i = 6; i < words.length; i += 6) partials.push(words.slice(0, i).join(" "));
  const done = {
    type: "done",
    conversation_id: CONV.newChat,
    title: "Ananya cancelled",
    reply: DEMO_REPLY,
    mirror_active: false,
    confidence_level: "medium",
    mode: "reflection",
    message_id: "50000000-0000-4000-8000-000000000999",
    people_used: [{ id: PEOPLE[0].id, name: "Ananya" }],
    remembered: [{ said: "probably just the massing. like 2 hours", when: "3 days ago", conversation_id: CONV.thesis }],
  };
  return [...partials.map((text) => ({ type: "partial", text })), done].map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
}

// ---------------------------------------------------------------- how it works
function systemFacts() {
  const contributions = { traits: 0.26, conversations: 0.2, voice: 0.15, reflections: 0.1 };
  return {
    // The real rule values, as the backend reports them.
    rules: {"traits": {"count": 4, "max_step_per_message": 0.2, "inertia": 0.8, "confidence_gain": 0.25, "confidence_loss": 0.3, "agree_within": 0.2, "conflict_beyond": 0.35, "confidence_floor": 0.05, "confidence_ceiling": 0.98, "snapshot_hours": 6}, "memory": {"messages_searched": 1200, "related_recalled": 4, "recent_recalled": 4, "turns_in_context": 16, "by_meaning": true, "meaning_min_similarity": 0.62, "meaning_min_standout": 2.5}, "mirror": {"voice_samples": 12, "max_attempts": 2}, "confidence": {"source_weights": {"traits": 0.4, "conversations": 0.25, "voice": 0.2, "reflections": 0.15}, "tiers": [{"tier": "very_low", "up_to": 20, "phrase_usage_frequency": 0.1, "tone_strength": 0.2, "reaction_accuracy_threshold": 0.85, "style_enforcement_intensity": 0.15, "include_uncertainty_note": true}, {"tier": "partial", "up_to": 50, "phrase_usage_frequency": 0.3, "tone_strength": 0.4, "reaction_accuracy_threshold": 0.7, "style_enforcement_intensity": 0.35, "include_uncertainty_note": false}, {"tier": "moderate", "up_to": 75, "phrase_usage_frequency": 0.55, "tone_strength": 0.65, "reaction_accuracy_threshold": 0.55, "style_enforcement_intensity": 0.6, "include_uncertainty_note": false}, {"tier": "high", "up_to": 100, "phrase_usage_frequency": 0.8, "tone_strength": 0.85, "reaction_accuracy_threshold": 0.4, "style_enforcement_intensity": 0.85, "include_uncertainty_note": false}]}, "reflections": {"messages_read": 160, "min_messages": 12, "min_quotes": 2}, "bootstrap": {"confidence_by_evidence": {"weak": 0.22, "moderate": 0.38, "strong": 0.52}, "counts_as_messages": {"weak": 3, "moderate": 7, "strong": 12}}, "ai": {"provider": "gemini", "reply_model": "gemini-3.6-flash", "fast_model": "gemini-3.1-flash-lite", "hedge_seconds": 4}},
    you: {
      messages: 412,
      conversations: 63,
      memory: { by_meaning: 398, recallable: 405 },
      feedback: { replies: { reflection: { up: 18, down: 3 }, mirror: { up: 7, down: 2 } }, reasons: [{ reason: "too_long", label: "Too long", count: 2 }], traits: { agree: 1, disagree: 0 }, reflections: { agree: 1, disagree: 0 } },
      traits: TRAITS.map(({ key, score, confidence, evidence_count }) => ({ key, score, confidence, evidence_count })),
      confidence: {
        center: 0.71,
        interval: { lower: 0.63, upper: 0.79 },
        tier: "moderate",
        source_scores: { traits: 0.65, conversations: 0.8, voice: 0.75, reflections: 0.67 },
        source_weights: { traits: 0.4, conversations: 0.25, voice: 0.2, reflections: 0.15 },
        source_contributions: contributions,
        facts: { messages: 412, active_days: 58, days_since_last: 0, freshness: 1, voice_messages: 160, voice_imported: 420, reflections: 3, half_width: 0.08 },
        controls: { phrase_usage_frequency: 0.65, tone_strength: 0.7, reaction_accuracy_threshold: 0.7, style_enforcement_intensity: 0.7, include_uncertainty_note: false },
      },
      voice_samples_available: 580,
      mirror: { replies_measured: 41, avg_seconds: 2.3, fallback_rate: 0.02 },
      reflections: 3,
    },
  };
}

// ---------------------------------------------------------------- router
const json = (body, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });

export function respond(url, method = "GET", postData = "") {
  const u = new URL(url);
  const path = u.pathname.replace(/^\/api/, "");
  const q = u.searchParams;

  // Supabase auth (the app checks the stored session with these)
  if (u.hostname.endsWith("supabase.co") || u.pathname.startsWith("/auth/v1")) {
    if (u.pathname.includes("/user")) return json({ id: USER.id, email: USER.email, aud: "authenticated", role: "authenticated", user_metadata: { display_name: USER.display_name } });
    return json({});
  }

  if (method === "POST" && path === "/chat/stream") return { status: 200, contentType: "text/event-stream", body: chatStream(), delayMs: 1300 };
  if (method !== "GET") {
    if (path.startsWith("/feedback/trait/")) {
      const body = safeJson(postData);
      const self = Number(body.self_score ?? 0.34);
      return json({ previous_score: 0.34, new_score: 0.34 + (self - 0.34) * 0.35, previous_confidence: 0.66, new_confidence: 0.58, counts_as_messages: 15 });
    }
    if (path.startsWith("/feedback/")) return json({ ok: true, verdict: safeJson(postData).verdict ?? null });
    return json({ ok: true });
  }

  if (path === "/health") return json({ status: "healthy", service: "reflectra", llm_configured: true });
  if (path === "/auth/me") return json(USER);
  if (path === "/user/system-state")
    return json({ last_inference: iso(ago(0, 2)), memory_count: 405, confidence: 71, confidence_range: [63, 79], confidence_tier: "moderate", learning_active: true, cycle_days: 7, messages: 412, learning_enabled: true });
  if (path === "/user/profile")
    return json({
      display_name: USER.display_name, email: USER.email, birth_date: "2003-04-12", age: 23,
      notifications: { enabled: true, follow_ups: true, weekly_digest: true, daily_check_in: false, check_in_time: "21:00", birthdays: true, quiet_start: "23:00", quiet_end: "08:00" },
      theme: null, member_since: dayOnly(ago(199)),
    });
  if (path === "/user/settings")
    return json({ user_id: USER.id, settings: { persona_mirroring: true, pattern_tracking: true, daily_reflections: true, digital_twin_enabled: true, twin_autonomy_mode: "draft_only", twin_mirror_intensity: 0.8, twin_require_approval: true }, updated_at: iso(ago(10)) });
  if (path.startsWith("/persona/portrait/")) return json(portrait());
  if (path === "/persona/voice-import")
    return json({ imported: { samples: 420, format: "whatsapp", description: "writes in lowercase, in short bursts, with a lot of 'ngl' and 'lol'", imported_at: iso(ago(46)) } });
  if (path.startsWith("/analytics/timeline/")) return json(timeline(q.get("range")));
  if (path.startsWith("/analytics/reflections/"))
    return json({ reflections: REFLECTIONS, earlier: [], status: { generated_at: iso(ago(2)), messages_available: 412, messages_read: 160, new_messages_since: 14, can_generate: true, reason: null, pattern_tracking: true } });
  if (path.startsWith("/analytics/system/")) return json(systemFacts());
  if (path.startsWith("/analytics/followups/"))
    return json({
      open: [
        { id: "60000000-0000-4000-8000-000000000001", what: "Email Prof. Iyer about the thesis extension", quote: "i'll email iyer tomorrow about the extension", status: "open", said_on: dayOnly(ago(2)), due: dayOnly(ago(-1)), overdue_by_days: 0, closed_on: null, closed_by: null, conversation_id: CONV.thesis },
        { id: "60000000-0000-4000-8000-000000000002", what: "Go for a run before Thursday's crit", quote: "running before the crit on thursday, promise", status: "open", said_on: dayOnly(ago(1)), due: dayOnly(ago(-2)), overdue_by_days: 0, closed_on: null, closed_by: null, conversation_id: CONV.run },
      ],
      closed: [
        { id: "60000000-0000-4000-8000-000000000003", what: "Finish the massing model", quote: "probably just the massing. like 2 hours", status: "done", said_on: dayOnly(ago(3)), due: dayOnly(ago(2)), overdue_by_days: 0, closed_on: dayOnly(ago(2)), closed_by: "chat", conversation_id: CONV.thesis },
      ],
      stats: { done: 7, dropped: 2, follow_through: 0.778 },
    });
  if (path === "/people") return json({ people: PEOPLE, suggestions: SUGGESTIONS });
  if (path === "/life")
    return json({
      facts: LIFE,
      kinds: LIFE_KINDS,
      in_replies: ["About you: Final-year architecture student in Bengaluru", "Going on now: Thesis submission is due on 12 December", "Routines: Runs before morning classes", "Working toward: Wants a studio job in Mumbai after graduating"],
      reading_history: false,
    });
  if (path === "/feedback/summary") return json(systemFacts().you.feedback);
  if (path === "/notifications/vapid-key") return json({ public_key: "" });
  if (path === "/notifications/status") return json({ subscribed: true, devices: 1 });
  if (path === "/conversations") return json({ conversations: CONVERSATIONS });
  if (/^\/conversations\/[^/]+\/messages$/.test(path)) return json(conversationMessages(path.split("/")[2]));
  if (path.startsWith("/schedule-context/"))
    return json({ user_id: USER.id, schedule_context: { classes_per_day: 4, study_hours: 5, has_deadlines: true, is_exam_period: false }, derived_context: { workload_level: "high", stress_level: 0.6 }, updated_at: iso(ago(8)) });
  if (path.startsWith("/chat/incognito-history/")) return json({ messages: [] });
  return json({});
}

function safeJson(text) {
  try {
    return JSON.parse(text || "{}");
  } catch {
    return {};
  }
}
