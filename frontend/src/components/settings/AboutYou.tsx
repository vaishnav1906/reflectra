import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2 } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Panel } from "@/components/portrait/PageShell";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";
import { PushState, disablePush, enablePush, pushState, sendTestPush } from "@/lib/push";

/**
 * About you: your name, date of birth, and which reminders you want.
 *
 * Replies know your age (and say happy birthday on the day). The notification
 * switches are shared by the web app and the future Android and iOS apps; nothing is
 * ever sent while the main switch is off.
 */

export type NotificationPrefs = {
  enabled: boolean;
  follow_ups: boolean;
  weekly_digest: boolean;
  daily_check_in: boolean;
  check_in_time: string;
  birthdays: boolean;
  quiet_start: string;
  quiet_end: string;
};

export type Profile = {
  display_name: string;
  email: string;
  birth_date: string | null;
  age: number | null;
  notifications: NotificationPrefs;
  member_since: string | null;
  theme: { hue: number; saturation: number } | null;
};

const tz = () => -new Date().getTimezoneOffset();

async function patchProfile(body: object): Promise<Profile> {
  const res = await apiFetch(`/api/user/profile?tz_offset_minutes=${tz()}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Couldn't save that.");
  return data as Profile;
}

export function useProfile() {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["profile", user?.id],
    enabled: Boolean(user?.id),
    queryFn: async () => {
      const res = await apiFetch(`/api/user/profile?tz_offset_minutes=${tz()}`);
      if (!res.ok) throw new Error("Couldn't load your profile.");
      return (await res.json()) as Profile;
    },
  });
}

const REMINDERS: { key: keyof NotificationPrefs; title: string; body: string }[] = [
  { key: "follow_ups", title: "Follow-ups", body: "When something you said you'd do is due: \"how did the gym go?\"" },
  { key: "weekly_digest", title: "Your week", body: "Sunday evening: how the week went, a new reflection, loose ends." },
  { key: "birthdays", title: "Birthdays", body: "A heads-up the day before someone in your People has a birthday." },
  { key: "daily_check_in", title: "Daily check-in", body: "One question a day, at a time you pick." },
];

export function AboutYou() {
  const { refreshUser } = useAuth();
  const queryClient = useQueryClient();
  const { data: profile, isLoading } = useProfile();
  const [name, setName] = useState("");
  const [birth, setBirth] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [device, setDevice] = useState<PushState | null>(null);
  const [testing, setTesting] = useState<"idle" | "sending" | "sent">("idle");

  useEffect(() => {
    void pushState().then(setDevice).catch(() => setDevice("unsupported"));
  }, []);

  /** The main switch: saves the preference everywhere, and subscribes or unsubscribes this browser. */
  const toggleNotifications = async (on: boolean) => {
    setError(null);
    if (on) {
      try {
        setDevice(await enablePush());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Couldn't turn on notifications in this browser.");
      }
    } else {
      setDevice(await disablePush().catch(() => device));
    }
    await save({ notifications: { enabled: on } });
  };

  useEffect(() => {
    if (!profile) return;
    setName(profile.display_name ?? "");
    setBirth(profile.birth_date ?? "");
  }, [profile]);

  const save = async (body: object) => {
    setSaving(true);
    setError(null);
    try {
      const next = await patchProfile(body);
      queryClient.setQueriesData({ queryKey: ["profile"] }, next);
      setSavedAt(Date.now());
      if ("display_name" in body) await refreshUser();
      return next;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save that.");
      return null;
    } finally {
      setSaving(false);
    }
  };

  const dirty = profile ? name.trim() !== (profile.display_name ?? "") || birth !== (profile.birth_date ?? "") : false;
  const prefs = profile?.notifications;
  const setPref = (change: Partial<NotificationPrefs>) => void save({ notifications: change });

  return (
    <Panel title="About you" hint={isLoading ? "loading…" : profile?.email}>
      <div className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <label className="people-field">
          <span>What Reflectra calls you</span>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={60} disabled={!profile} />
        </label>
        <label className="people-field">
          <span>
            Date of birth (optional){profile?.age != null ? <span className="ml-1 text-foreground">· you&apos;re {profile.age}</span> : null}
          </span>
          <input type="date" value={birth} onChange={(e) => setBirth(e.target.value)} max={new Date().toISOString().slice(0, 10)} disabled={!profile} />
        </label>
        <button
          type="button"
          className="btn-mirror !py-2.5 disabled:opacity-40"
          disabled={!dirty || saving || !name.trim()}
          onClick={() => void save({ display_name: name, birth_date: birth })}
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Save
        </button>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        Replies use your first name now and then, know your age, and say happy birthday on the day.
        {savedAt && !dirty ? (
          <span className="ml-2 inline-flex items-center gap-1 text-iris-cyan">
            <Check className="h-3 w-3" /> Saved
          </span>
        ) : null}
      </p>

      <div className="mt-6 border-t border-white/5 pt-5">
        <div className="flex items-start justify-between gap-6">
          <div>
            <p className="font-medium text-foreground">Notifications</p>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-muted-foreground">
              For this browser and the Reflectra apps for Android and iOS. Nothing is sent while this is off, and notifications never show
              what you talked about.
            </p>
          </div>
          <Switch
            checked={Boolean(prefs?.enabled)}
            disabled={!prefs || saving}
            onCheckedChange={(checked) => void toggleNotifications(checked)}
            aria-label="Notifications"
          />
        </div>

        {prefs?.enabled ? (
          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
            <span className="text-muted-foreground">
              {device === "on"
                ? "This browser will get them."
                : device === "blocked"
                  ? "This browser has notifications blocked: allow them in the site settings (the lock icon by the address)."
                  : device === "needs-install"
                    ? "On iPhone and iPad: Share → Add to Home Screen, open Reflectra from there, then turn this on."
                    : device === "unsupported"
                      ? "This browser can't show notifications; the phone apps will."
                      : "Not on for this browser yet."}
            </span>
            {device === "off" ? (
              <button type="button" className="trait-check-btn" onClick={() => void toggleNotifications(true)}>
                Turn on here
              </button>
            ) : null}
            {device === "on" ? (
              <button
                type="button"
                className="trait-check-btn"
                disabled={testing === "sending"}
                onClick={async () => {
                  setTesting("sending");
                  setError(null);
                  try {
                    await sendTestPush();
                    setTesting("sent");
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Couldn't send a test.");
                    setTesting("idle");
                  }
                }}
              >
                {testing === "sending" ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                {testing === "sent" ? "Sent: check your notifications" : "Send a test"}
              </button>
            ) : null}
          </div>
        ) : null}

        <div className={cn("mt-4 grid gap-3 sm:grid-cols-2", !prefs?.enabled && "pointer-events-none opacity-45")} aria-disabled={!prefs?.enabled}>
          {REMINDERS.map((item) => (
            <div key={item.key} className="flex items-start justify-between gap-4 rounded-2xl border border-white/8 bg-white/[0.02] p-4">
              <div>
                <p className="text-sm text-foreground">{item.title}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{item.body}</p>
                {item.key === "daily_check_in" && prefs?.daily_check_in ? (
                  <label className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                    at
                    <input
                      type="time"
                      value={prefs.check_in_time}
                      onChange={(e) => e.target.value && setPref({ check_in_time: e.target.value })}
                      className="rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1 text-foreground [color-scheme:dark]"
                    />
                  </label>
                ) : null}
              </div>
              <Switch
                checked={Boolean(prefs?.[item.key])}
                disabled={!prefs?.enabled || saving}
                onCheckedChange={(checked) => setPref({ [item.key]: checked })}
                aria-label={item.title}
              />
            </div>
          ))}
        </div>

        <div className={cn("mt-4 flex flex-wrap items-center gap-2 text-xs text-muted-foreground", !prefs?.enabled && "opacity-45")}>
          Quiet hours: nothing between
          <input
            type="time"
            value={prefs?.quiet_start ?? "22:30"}
            disabled={!prefs?.enabled}
            onChange={(e) => e.target.value && setPref({ quiet_start: e.target.value })}
            className="rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1 text-foreground [color-scheme:dark]"
            aria-label="Quiet hours start"
          />
          and
          <input
            type="time"
            value={prefs?.quiet_end ?? "08:00"}
            disabled={!prefs?.enabled}
            onChange={(e) => e.target.value && setPref({ quiet_end: e.target.value })}
            className="rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1 text-foreground [color-scheme:dark]"
            aria-label="Quiet hours end"
          />
          , and never more than one a day.
        </div>
      </div>
      {error ? <p className="mt-3 text-sm text-destructive">{error}</p> : null}
    </Panel>
  );
}
