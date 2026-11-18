import targets from "./targets.json";

/**
 * The tutorial, one idea per slide. Screens are real Reflectra pages with a made-up
 * person ("Maya"), captured on a PC and a phone by scripts/media/tutorial-shots.mjs,
 * which also records where each slide's button is (targets.json).
 */

export type Device = "desktop" | "mobile";
export type Target = { x: number; y: number; w: number; h: number }; // percent of the screen

export type Slide = {
  key: string;
  title: string;
  /** What to do or know, in one or two short sentences. */
  text: string | Record<Device, string>;
  /** A screen with a pointer, or a plain card (welcome / ending). */
  kind: "intro" | "screen" | "end";
  /** What the pointer does on this slide. */
  gesture?: "tap" | "look";
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
    key: "correct",
    kind: "screen",
    gesture: "tap",
    title: "Not quite you? Fix it",
    text: "Tap Not quite on any trait and drag to where you'd put yourself. You'll see the change before you save.",
  },
  {
    key: "people",
    kind: "screen",
    gesture: "tap",
    title: "Your people",
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

export function targetFor(key: string, device: Device): Target | null {
  const byDevice = (targets as Record<Device, Record<string, Target>>)[device];
  return byDevice?.[key] ?? null;
}

export const screenSrc = (key: string, device: Device) => `/tutorial/${device}/${key}.webp`;
