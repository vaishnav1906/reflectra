import { apiFetch } from "@/lib/api";

/**
 * Ask the server to run this user's queued learning jobs now (traits, memory, People,
 * life facts). On serverless hosting nothing runs in the background, so the app
 * triggers it right after a reply; with a long-running server it simply finds nothing
 * left to do. Fire and forget: a scheduled tick picks up anything this misses.
 */
export function learnNow(): void {
  void apiFetch("/api/jobs/run-mine", { method: "POST", keepalive: true }).catch(() => undefined);
}
