import targets from "./targets.json";

/**
 * The tutorial, one idea per slide. Screens are real Reflectra pages with a made-up
 * person ("Maya"), captured on a PC and a phone by scripts/media/tutorial-shots.mjs,
 * which also records where each slide's button is (targets.json).
 */

export type Device = "desktop" | "mobile";
export type Target = { x: number; y: number; w: number; h: number }; // percent of the screen

/** One stop on a slide that explains several parts of a screen in turn. */
export type Callout = { id: string; label: string; gesture: "tap" | "look" };

export type Slide = {
  key: string;
  title: string;
  /** What to do or know, in one or two short sentences. */
  text: string | Record<Device, string>;
  /** A screen with a pointer, or a plain card (welcome / ending). */
  kind: "intro" | "screen" | "end";
  /** What the pointer does on this slide. */
  gesture?: "tap" | "look";
  /** Several parts of the screen, explained one after another. */
  callouts?: Callout[];
};

export const SLIDES: Slide[] = [
  {
    key: "welcome",
    kind: "intro",
    title: "Welcome to Reflectra",
    text: "A mirror for your mind. Here's how it works, in about a minute.",
  },
  {
    key: "navigate",
    kind: "screen",
    gesture: "tap",
    title: "Find your way",
    text: {
      desktop: "Every part of Reflectra is in the sidebar on the left.",
      mobile: "Tap the menu button to open every page of Reflectra.",
    },
  },
  {
    key: "message",
    kind: "screen",
    gesture: "tap",
    title: "Say what's on your mind",
    text: "Type the way you'd text a friend, then tap send. It listens, and tells you what it notices.",
  },
  {
    key: "remembered",
    kind: "screen",
    gesture: "look",
    title: "It remembers",
    text: "These chips show what a reply used: someone from your People, or something you said before. Tap one to see it.",
  },
  {
    key: "rate",
    kind: "screen",
    gesture: "tap",
    title: "Tell it what works",
    text: "Thumbs up or down on any reply. Say why, and the next replies adjust.",
  },
  {
    key: "mirror",
    kind: "screen",
    gesture: "tap",
    title: "Mirror mode",
    text: "Switch to Mirror and it talks back as you, in your own words and style.",
  },
  {
    key: "persona",
    kind: "screen",
    gesture: "look",
    title: "The shape of you",
    text: "Persona shows how you think, learned from how you write. The faint halo is doubt; it shrinks the more you talk.",
  },
  {
    key: "moved",
    kind: "screen",
    title: "How you've changed",
    text: "Persona also keeps a record of you over time.",
    callouts: [
      { id: "lines", gesture: "look", label: "Each line is one trait, with a point for every day you talked, so you can watch yourself change." },
      { id: "legend", gesture: "tap", label: "Tap or hover any day to read that day's numbers for each trait." },
    ],
  },
  {
    key: "rhythm",
    kind: "screen",
    title: "When you talk",
    text: "And it notices your rhythm.",
    callouts: [
      { id: "clock", gesture: "look", label: "The clock: the longer the spoke, the more you talk at that hour. The bright one is your busiest hour." },
      { id: "bars", gesture: "look", label: "Your week: the tallest, brightest bar is the day you talk the most." },
    ],
  },
  {
    key: "correct",
    kind: "screen",
    gesture: "tap",
    title: "Not quite you? Fix it",
    text: "Tap Not quite on any trait and drag to where you'd put yourself. You'll see the change before you save.",
  },
  {
    key: "orbit",
    kind: "screen",
    title: "Your people, in orbit",
    text: "Everyone you talk about circles around you, and every detail means something.",
    callouts: [
      { id: "you", gesture: "look", label: "That's you, in the middle." },
      { id: "inner", gesture: "look", label: "Inner ring: someone you talked about this week. A bigger circle means they come up often." },
      { id: "outer", gesture: "look", label: "Outer ring: it's been a while since they came up. They drift closer when you mention them again." },
      { id: "legend", gesture: "look", label: "Colours tell friends, family and work apart." },
      { id: "open", gesture: "tap", label: "Tap anyone to open their card: who they are to you, and what you've said about them." },
    ],
  },
  {
    key: "people",
    kind: "screen",
    gesture: "tap",
    title: "Add someone",
    text: "Add the people you talk about. When their name comes up, Reflectra already knows who they are to you.",
  },
  {
    key: "life",
    kind: "screen",
    gesture: "tap",
    title: "Your life, in your words",
    text: "The lasting things you've told it. Tap Read my past chats to build it from what you've already said.",
  },
  {
    key: "reflections",
    kind: "screen",
    gesture: "tap",
    title: "Patterns you can't see",
    text: "Each reflection is backed by your own quotes. Tell it Spot on, or Not really.",
  },
  {
    key: "week",
    kind: "screen",
    gesture: "tap",
    title: "Your week, as a story",
    text: "Every Sunday, tap Play your week for a short recap of how it went.",
  },
  {
    key: "colour",
    kind: "screen",
    gesture: "tap",
    title: "Make it yours",
    text: "In Settings, pick a colour and the whole app follows. Reminders and installing the app are there too.",
  },
  {
    key: "export",
    kind: "screen",
    gesture: "tap",
    title: "Take your portrait with you",
    text: "On Persona, tap Export PDF for a printable portrait: your traits, patterns, people and how you write.",
  },
  {
    key: "end",
    kind: "end",
    title: "You're all set",
    text: "Start with whatever's on your mind. You can replay this tour anytime from the homepage.",
  },
];

export function slideText(slide: Slide, device: Device): string {
  return typeof slide.text === "string" ? slide.text : slide.text[device];
}

type Targets = Record<Device, Record<string, Target | Record<string, Target>>>;

const isTarget = (value: unknown): value is Target =>
  Boolean(value) && typeof (value as Target).x === "number" && typeof (value as Target).w === "number";

/** Where a single-target slide points. */
export function targetFor(key: string, device: Device): Target | null {
  const found = (targets as Targets)[device]?.[key];
  return isTarget(found) ? found : null;
}

/** Where one part of a multi-part slide is. */
export function calloutTarget(key: string, id: string, device: Device): Target | null {
  const found = (targets as Targets)[device]?.[key];
  if (!found || isTarget(found)) return null;
  return found[id] ?? null;
}

export const screenSrc = (key: string, device: Device) => `/tutorial/${device}/${key}.webp`;
