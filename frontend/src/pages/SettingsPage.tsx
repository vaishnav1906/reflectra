import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowRight, Check, Copy, EyeOff, Loader2, Lock, Trash2, Upload } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { PageShell, Panel } from "@/components/portrait/PageShell";
import { ExportPortraitButton } from "@/components/transitions/PortraitPrint";
import { VoiceImportRow } from "@/components/settings/VoiceImport";
import { AboutYou, useProfile } from "@/components/settings/AboutYou";
import { InstallCard } from "@/components/pwa/InstallApp";
import { ColourWheel } from "@/components/settings/ColourWheel";

/** The wheel starts from the colour saved on your account (falls back to this device). */
function ColourWheelFromProfile() {
  const { data } = useProfile();
  return <ColourWheel saved={data?.theme ?? null} />;
}
import { TRAIT_COLOR, TRAIT_LABEL, TraitKey } from "@/hooks/useReflectra";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";
import { playEraseFog } from "@/lib/motion";

/**
 * Settings. Every control here changes real behaviour on the server:
 *   Mirror my voice ....... Mirror mode on/off (persona_mirroring)
 *   Keep learning ......... trait updates, writing-style learning and reflections (pattern_tracking)
 *   Mirror strength ....... how strongly Mirror imitates you (twin_mirror_intensity)
 */

type ServerSettings = {
  persona_mirroring: boolean;
  pattern_tracking: boolean;
  daily_reflections: boolean;
  twin_mirror_intensity: number;
};

const DEFAULTS: ServerSettings = { persona_mirroring: true, pattern_tracking: true, daily_reflections: true, twin_mirror_intensity: 0.8 };

const STRENGTHS = [
  { value: 0.3, label: "Light", hint: "Mostly clear and neutral, a hint of you." },
  { value: 0.6, label: "Balanced", hint: "Your tone and rhythm, without the quirks." },
  { value: 0.9, label: "Strong", hint: "Your exact wording habits and cadence." },
];

const BOOTSTRAP_PROMPT =
  "Based on everything you know about me from our conversations, describe me as a person in about 250 words, in the third person. " +
  "Cover four things, each with a concrete example or something I actually said: (1) how I communicate: short and direct, or long and detailed; " +
  "(2) how openly I express emotions; (3) how I make decisions: hesitant or decisive; (4) how much I reflect on myself. " +
  "Then add a few facts about my life that matter: what I do, what I'm working on, what I care about, what I struggle with. " +
  "Be honest rather than flattering, and if you don't know something, say so instead of guessing.";

type TraitChange = {
  trait: TraitKey;
  applied: boolean;
  strength: string;
  evidence: string;
  previous_score: number;
  new_score: number;
  previous_confidence: number;
  new_confidence: number;
};

type BootstrapResult = { saved: boolean; traits: TraitChange[]; notes: string[]; recognised: number; total_traits: number };

async function readError(res: Response, fallback: string): Promise<string> {
  const body = await res.json().catch(() => ({}));
  return typeof body?.detail === "string" ? body.detail : fallback;
}

function Row({ title, body, control }: { title: string; body: string; control: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-6 border-b border-white/5 py-5 first:pt-0 last:border-0 last:pb-0">
      <div className="min-w-0">
        <p className="font-medium text-foreground">{title}</p>
        <p className="mt-1 max-w-xl text-sm leading-relaxed text-muted-foreground">{body}</p>
      </div>
      <div className="shrink-0 pt-0.5">{control}</div>
    </div>
  );
}

export function SettingsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user, signOut } = useAuth();
  const userId = user?.id ?? "";

  const [settings, setSettings] = useState<ServerSettings>(DEFAULTS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);


  const [bootstrapOpen, setBootstrapOpen] = useState(false);
  const [summary, setSummary] = useState("");
  const [analysing, setAnalysing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [preview, setPreview] = useState<BootstrapResult | null>(null);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [confirm, setConfirm] = useState<"clear" | "delete" | null>(null);
  const [confirmText, setConfirmText] = useState("");
  const [working, setWorking] = useState(false);
  const [dangerError, setDangerError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`/api/user/settings?user_id=${encodeURIComponent(userId)}`);
        if (!res.ok) throw new Error(await readError(res, "Couldn't load your settings."));
        const data = await res.json();
        if (!cancelled) setSettings({ ...DEFAULTS, ...(data?.settings ?? {}) });
      } catch (err) {
        if (!cancelled) setSettingsError(err instanceof Error ? err.message : "Couldn't load your settings.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const save = async (patch: Partial<ServerSettings>) => {
    if (loading || saving) return;
    const previous = settings;
    const next = { ...settings, ...patch };
    setSettings(next);
    setSettingsError(null);
    setSaving(true);
    try {
      const res = await apiFetch("/api/user/settings/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(next),
      });
      if (!res.ok) throw new Error(await readError(res, "Couldn't save that."));
      void queryClient.invalidateQueries({ queryKey: ["reflections"] });
    } catch (err) {
      setSettings(previous);
      setSettingsError(err instanceof Error ? err.message : "Couldn't save that.");
    } finally {
      setSaving(false);
    }
  };

  const runBootstrap = async (dryRun: boolean) => {
    setBootstrapError(null);
    if (dryRun) setAnalysing(true);
    else setApplying(true);
    try {
      const res = await apiFetch("/api/persona/bootstrap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ summary_text: summary, dry_run: dryRun }),
      });
      if (!res.ok) throw new Error(await readError(res, "Couldn't read that right now."));
      const result = (await res.json()) as BootstrapResult;
      if (dryRun) {
        setPreview(result);
      } else {
        toast.success(`Imported. ${result.recognised} of ${result.total_traits} traits updated.`);
        void queryClient.invalidateQueries();
        closeBootstrap();
        navigate("/app/personality");
      }
    } catch (err) {
      setBootstrapError(err instanceof Error ? err.message : "Couldn't read that right now.");
    } finally {
      setAnalysing(false);
      setApplying(false);
    }
  };

  const closeBootstrap = () => {
    setBootstrapOpen(false);
    setSummary("");
    setPreview(null);
    setBootstrapError(null);
  };

  const runDanger = async () => {
    if (!confirm || working) return;
    setWorking(true);
    setDangerError(null);
    try {
      const res =
        confirm === "clear"
          ? await apiFetch("/api/user/clear-data", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) })
          : await apiFetch("/api/user/delete-account", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
      if (!res.ok) throw new Error(await readError(res, "That didn't go through. Nothing was changed."));
      if (confirm === "clear") {
        queryClient.clear();
        setConfirm(null);
        await playEraseFog(); // the mirror fogs over and wipes clean before you leave
        toast.success("Your conversations and everything learned from them were erased.");
        navigate("/app/chat");
      } else {
        await signOut();
        localStorage.clear();
        navigate("/");
      }
    } catch (err) {
      setDangerError(err instanceof Error ? err.message : "That didn't go through. Nothing was changed.");
    } finally {
      setWorking(false);
    }
  };

  const confirmWord = confirm === "clear" ? "CLEAR" : "DELETE";
  const wordCount = summary.trim() ? summary.trim().split(/\s+/).length : 0;

  return (
    <PageShell eyebrow="Settings" title="Make it" accent="yours." subtitle="Each switch here changes what Reflectra actually does on the server, not just what this page shows.">
      <AboutYou />

      <ColourWheelFromProfile />

      <InstallCard />

      <Panel title="How Reflectra behaves" hint={saving ? "saving…" : loading ? "loading…" : undefined}>
        <Row
          title="Mirror my voice"
          body="Lets Mirror mode reply as you, in your own style. Turn it off and Mirror mode stops answering until you turn it back on."
          control={<Switch checked={settings.persona_mirroring} disabled={loading || saving} onCheckedChange={(checked) => void save({ persona_mirroring: checked })} aria-label="Mirror my voice" />}
        />
        <Row
          title="Keep learning about me"
          body="Updates your traits and writing style from each message and allows new reflections. Turn it off and Reflectra still talks, but freezes what it knows."
          control={<Switch checked={settings.pattern_tracking} disabled={loading || saving} onCheckedChange={(checked) => void save({ pattern_tracking: checked })} aria-label="Keep learning about me" />}
        />
        <div className="pt-5">
          <p className="font-medium text-foreground">Mirror strength</p>
          <p className="mt-1 text-sm text-muted-foreground">How closely Mirror mode imitates the way you write.</p>
          <div className="mt-4 grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Mirror strength">
            {STRENGTHS.map((option) => {
              const active = Math.abs(settings.twin_mirror_intensity - option.value) < 0.16;
              return (
                <button
                  key={option.label}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  disabled={loading || saving || !settings.persona_mirroring}
                  onClick={() => void save({ twin_mirror_intensity: option.value })}
                  className={cn(
                    "rounded-2xl border p-4 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50",
                    active ? "iris-border border-transparent bg-white/[0.06]" : "border-white/10 bg-white/[0.02] hover:bg-white/[0.05]",
                  )}
                >
                  <span className="text-sm font-medium text-foreground">{option.label}</span>
                  <span className="mt-1 block text-xs leading-snug text-muted-foreground">{option.hint}</span>
                </button>
              );
            })}
          </div>
        </div>
        {settingsError ? <p className="mt-4 text-sm text-destructive">{settingsError}</p> : null}
      </Panel>

      <Panel title="Privacy">
        <div className="grid gap-5 md:grid-cols-2">
          <div className="flex gap-3">
            <EyeOff className="mt-0.5 h-4 w-4 shrink-0 text-iris-cyan" />
            <p className="text-sm leading-relaxed text-muted-foreground">
              <span className="text-foreground">Incognito</span>{" "}is a switch at the top of the chat. While it&apos;s on, nothing you say is saved or learned from.
            </p>
          </div>
          <div className="flex gap-3">
            <Lock className="mt-0.5 h-4 w-4 shrink-0 text-iris-cyan" />
            <p className="text-sm leading-relaxed text-muted-foreground">
              Your conversations are tied to your login. The database refuses every request for them that isn&apos;t yours.
            </p>
          </div>
        </div>
      </Panel>

      <Panel title="Your data">
        <Row
          title="Give Reflectra a head start"
          body="Paste a description of yourself, for example one another AI assistant wrote about you. Reflectra shows you exactly what it took from it before anything is saved."
          control={
            <button type="button" className="btn-ghost-glass !px-4 !py-2" onClick={() => setBootstrapOpen(true)} aria-label="Import a description of you">
              <Upload className="h-4 w-4" /> Import
            </button>
          }
        />
        <VoiceImportRow Row={Row} />
        <Row
          title="Download your portrait"
          body="A PDF of everything on your Persona page: your traits, the patterns in your own words, how you've changed and how you write."
          control={
            <ExportPortraitButton />
          }
        />
        <Row
          title="Erase what Reflectra knows"
          body="Deletes your conversations, traits, writing style, reflections and imports. Your account stays, and Reflectra starts over with you."
          control={
            <button type="button" className="btn-ghost-glass !px-4 !py-2" onClick={() => { setConfirm("clear"); setConfirmText(""); setDangerError(null); }}>
              Erase
            </button>
          }
        />
        <Row
          title="Delete my account"
          body="Removes your account and everything in it, permanently."
          control={
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-full border border-destructive/40 px-4 py-2 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10"
              onClick={() => { setConfirm("delete"); setConfirmText(""); setDangerError(null); }}
            >
              <Trash2 className="h-4 w-4" /> Delete
            </button>
          }
        />
      </Panel>

      {/* Import a description */}
      <Dialog open={bootstrapOpen} onOpenChange={(open) => (!open && !analysing && !applying ? closeBootstrap() : undefined)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto border-white/10 bg-popover sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="font-display text-3xl font-normal">{preview ? "Here's what I took from it" : "Give Reflectra a head start"}</DialogTitle>
            <DialogDescription>
              {preview
                ? "Nothing is saved yet. Each reading is backed by a line from your text; anything without one was ignored."
                : "Paste a description of you. It counts like a dozen of your own messages at most, so the more you've talked here, the less it changes."}
            </DialogDescription>
          </DialogHeader>

          {!preview ? (
            <div className="space-y-4">
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-foreground">Don&apos;t have one? Ask an AI that knows you.</p>
                  <button
                    type="button"
                    className="inline-flex shrink-0 items-center gap-1.5 text-xs text-primary hover:underline"
                    onClick={async () => {
                      await navigator.clipboard.writeText(BOOTSTRAP_PROMPT);
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                    }}
                  >
                    {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />} {copied ? "Copied" : "Copy the question"}
                  </button>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{BOOTSTRAP_PROMPT}</p>
              </div>
              <Textarea
                value={summary}
                onChange={(event) => setSummary(event.target.value)}
                placeholder="Paste the description here…"
                className="min-h-[200px] border-white/10 bg-white/[0.03]"
                disabled={analysing}
                aria-label="Description of you"
              />
              <div className="flex items-center justify-between gap-4">
                <p className={cn("font-mono text-[11px] uppercase tracking-widest", wordCount < 40 ? "text-muted-foreground" : "text-iris-cyan")}>
                  {wordCount} words {wordCount < 40 ? "· needs at least 40" : ""}
                </p>
                <button type="button" className="btn-mirror disabled:cursor-not-allowed disabled:opacity-50" disabled={wordCount < 40 || analysing} onClick={() => void runBootstrap(true)}>
                  {analysing ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {analysing ? "Reading…" : "Read it"}
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {preview.traits.map((change) => {
                const label = TRAIT_LABEL[change.trait];
                const color = TRAIT_COLOR[change.trait];
                return (
                  <div key={change.trait} className={cn("rounded-2xl border border-white/10 p-4", !change.applied && "opacity-60")}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="flex items-center gap-2 text-sm font-medium text-foreground">
                        <span className="h-2 w-2 rounded-full" style={{ background: color }} />
                        {label?.name ?? change.trait}
                      </p>
                      {change.applied ? (
                        <p className="flex items-center gap-2 font-mono text-sm">
                          <span className="text-muted-foreground">{Math.round(change.previous_score * 100)}</span>
                          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                          <span style={{ color }}>{Math.round(change.new_score * 100)}</span>
                          <span className="text-xs text-muted-foreground">· {change.strength} evidence</span>
                        </p>
                      ) : (
                        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">not mentioned · left alone</p>
                      )}
                    </div>
                    {change.applied ? <p className="mt-2 border-l border-iris-peach/60 pl-3 text-sm italic text-muted-foreground">“{change.evidence}”</p> : null}
                  </div>
                );
              })}
              {preview.notes.length ? (
                <div className="rounded-2xl border border-white/10 p-4">
                  <p className="text-sm font-medium text-foreground">Things it will remember about you</p>
                  <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                    {preview.notes.map((note) => (
                      <li key={note}>· {note}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {preview.recognised === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nothing in that text describes how you communicate, feel, decide or reflect, so there is nothing to import. Try the question above.
                </p>
              ) : null}
              <div className="flex items-center justify-between gap-3">
                <button type="button" className="btn-ghost-glass" onClick={() => setPreview(null)} disabled={applying}>
                  Back
                </button>
                <button type="button" className="btn-mirror disabled:cursor-not-allowed disabled:opacity-50" disabled={preview.recognised === 0 || applying} onClick={() => void runBootstrap(false)}>
                  {applying ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {applying ? "Saving…" : `Save ${preview.recognised} ${preview.recognised === 1 ? "reading" : "readings"}`}
                </button>
              </div>
            </div>
          )}
          {bootstrapError ? <p className="text-sm text-destructive">{bootstrapError}</p> : null}
        </DialogContent>
      </Dialog>

      {/* Erase / delete confirmation */}
      <AlertDialog open={confirm !== null} onOpenChange={(open) => (!open && !working ? setConfirm(null) : undefined)}>
        <AlertDialogContent className="border-white/10 bg-popover sm:max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display text-3xl font-normal">{confirm === "clear" ? "Erase what Reflectra knows?" : "Delete your account?"}</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-4">
                <p>
                  {confirm === "clear"
                    ? "Your conversations, traits, writing style, reflections and imports will be deleted. Your account stays. This can't be undone."
                    : "Your account and everything in it will be deleted. This can't be undone."}
                </p>
                <p className="text-sm">
                  Type <span className="font-mono text-foreground">{confirmWord}</span> to confirm.
                </p>
                <Input value={confirmText} onChange={(event) => setConfirmText(event.target.value)} autoFocus disabled={working} aria-label={`Type ${confirmWord} to confirm`} />
                {dangerError ? <p className="text-sm text-destructive">{dangerError}</p> : null}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={working}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={confirmText !== confirmWord || working}
              onClick={(event) => {
                event.preventDefault();
                void runDanger();
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {working ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {confirm === "clear" ? "Erase" : "Delete account"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageShell>
  );
}
