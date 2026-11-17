import { apiFetch } from "@/lib/api";

/**
 * Browser notifications (Web Push). The service worker in /sw.js shows them; the
 * server decides when (see backend app/services/reminders.py).
 *
 * iPhone and iPad only allow this once Reflectra is added to the home screen.
 */

export type PushState = "unsupported" | "needs-install" | "blocked" | "off" | "on";

const tz = () => -new Date().getTimezoneOffset();

function isIos() {
  return /iphone|ipad|ipod/i.test(navigator.userAgent);
}

function isStandalone() {
  return window.matchMedia?.("(display-mode: standalone)").matches || (navigator as unknown as { standalone?: boolean }).standalone === true;
}

export function pushSupported() {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

function urlBase64ToUint8Array(base64: string) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

async function registration() {
  return navigator.serviceWorker.register("/sw.js", { scope: "/" });
}

export async function pushState(): Promise<PushState> {
  if (!pushSupported()) return isIos() && !isStandalone() ? "needs-install" : "unsupported";
  if (Notification.permission === "denied") return "blocked";
  const reg = await navigator.serviceWorker.getRegistration("/");
  const sub = await reg?.pushManager.getSubscription();
  return sub ? "on" : "off";
}

/** Ask for permission (if needed), subscribe this browser and tell the server. */
export async function enablePush(): Promise<PushState> {
  if (!pushSupported()) return pushState();
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return permission === "denied" ? "blocked" : "off";
  const reg = await registration();
  await navigator.serviceWorker.ready;
  const keyRes = await apiFetch("/api/notifications/vapid-key");
  if (!keyRes.ok) throw new Error("Couldn't reach the server.");
  const { public_key } = (await keyRes.json()) as { public_key: string };
  const subscription =
    (await reg.pushManager.getSubscription()) ??
    (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(public_key) }));
  const json = subscription.toJSON();
  const res = await apiFetch(`/api/notifications/subscribe?tz_offset_minutes=${tz()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint: json.endpoint, keys: json.keys ?? {}, platform: "web" }),
  });
  if (!res.ok) throw new Error("The server didn't accept this browser.");
  return "on";
}

/** Stop notifications on this browser (other devices are unaffected). */
export async function disablePush(): Promise<PushState> {
  if (!pushSupported()) return pushState();
  const reg = await navigator.serviceWorker.getRegistration("/");
  const subscription = await reg?.pushManager.getSubscription();
  if (subscription) {
    await apiFetch("/api/notifications/unsubscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint: subscription.endpoint }),
    }).catch(() => undefined);
    await subscription.unsubscribe();
  }
  return "off";
}

export async function sendTestPush(): Promise<void> {
  const res = await apiFetch("/api/notifications/test", { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body?.detail === "string" ? body.detail : "Couldn't send a test.");
  }
}
