import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Loader2, Sparkles, UserPlus } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ErrorState, LoadingState, PageShell, Panel } from "@/components/portrait/PageShell";
import { GROUP_COLOR, GROUP_LABEL, PeopleOrbit } from "@/components/people/PeopleOrbit";
import { PersonCard, PersonFieldsForm } from "@/components/people/PersonCard";
import { Person, PersonFields, PersonGroup, usePeople, usePeopleActions } from "@/hooks/useReflectra";
import { cn } from "@/lib/utils";

/**
 * People: friends and family, as you describe them. When one of them comes up in a
 * chat, Reflectra already knows who they are to you.
 */

function Suggestion({ person, index = 0 }: { person: Person; index?: number }) {
  const actions = usePeopleActions();
  const [busy, setBusy] = useState<"add" | "skip" | null>(null);
  const latest = person.notes[0];
  return (
    <li
      className="suggestion-knock flex flex-wrap items-center justify-between gap-3 border-b border-white/5 py-3 first:pt-0 last:border-0 last:pb-0"
      style={{ animationDelay: `${0.2 + index * 0.12}s` }}
    >
      <div className="min-w-0">
        <p className="text-sm text-foreground">
          <span className="font-medium">{person.name}</span>
          {person.relationship ? <span className="text-muted-foreground"> · {person.relationship}</span> : null}
          <span className="ml-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            came up {person.mention_count}×
          </span>
        </p>
        {latest ? <p className="mt-0.5 truncate text-xs italic text-muted-foreground">“{latest.quote ?? latest.text}”</p> : null}
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          className="trait-check-btn"
          disabled={busy !== null}
          onClick={async () => {
            setBusy("add");
            try {
              await actions.accept(person.id);
            } finally {
              setBusy(null);
            }
          }}
        >
          {busy === "add" ? <Loader2 className="h-3 w-3 animate-spin" /> : <UserPlus className="h-3 w-3" />} Add
        </button>
        <button
          type="button"
          className="text-xs text-muted-foreground hover:text-foreground"
          disabled={busy !== null}
          onClick={async () => {
            setBusy("skip");
            try {
              await actions.dismiss(person.id);
            } finally {
              setBusy(null);
            }
          }}
        >
          Not someone to track
        </button>
      </div>
    </li>
  );
}

function AddPerson({ open, onClose, onAdded }: { open: boolean; onClose: () => void; onAdded: (id: string) => void }) {
  const actions = usePeopleActions();
  const [fields, setFields] = useState<PersonFields>({ name: "", relationship: "", description: "", aliases: [], birthday: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setFields({ name: "", relationship: "", description: "", aliases: [], birthday: "" });
      setError(null);
    }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={(next) => (!next && !saving ? onClose() : undefined)}>
      <DialogContent className="max-h-[90vh] overflow-y-auto border-white/10 bg-popover sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="font-display text-3xl font-normal">Add someone</DialogTitle>
          <DialogDescription>
            Whenever their name comes up in a chat, Reflectra will know who they are to you. A sentence or two is plenty.
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            setSaving(true);
            setError(null);
            try {
              const person = await actions.add({ ...fields, birthday: fields.birthday || null });
              onAdded(person.id);
              onClose();
            } catch (err) {
              setError(err instanceof Error ? err.message : "Couldn't add them.");
            } finally {
              setSaving(false);
            }
          }}
          className="space-y-5"
        >
          <PersonFieldsForm value={fields} onChange={setFields} autoFocusName />
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <div className="flex justify-end gap-3">
            <button type="button" className="btn-ghost-glass" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn-mirror disabled:opacity-40" disabled={saving || !(fields.name ?? "").trim()}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />} Add
            </button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function PeoplePage() {
  const { data, isLoading, error, refetch } = usePeople();
  const [params, setParams] = useSearchParams();
  const [adding, setAdding] = useState(false);
  const selectedId = params.get("person");
  const select = (id: string | null) => setParams(id ? { person: id } : {}, { replace: true });

  const people = data?.people ?? [];
  const selected = people.find((p) => p.id === selectedId) ?? people[0] ?? null;
  const groups = Array.from(new Set(people.map((p) => p.group))) as PersonGroup[];

  if (isLoading) return <LoadingState label="Gathering your people…" />;
  if (error || !data) return <ErrorState message={error instanceof Error ? error.message : "Couldn't load your people."} onRetry={() => void refetch()} />;

  return (
    <PageShell
      eyebrow="People"
      title="The people in"
      accent="your story."
      subtitle="Friends and family, as you describe them. When one of them comes up in a chat, Reflectra already knows who they are to you."
      actions={
        <button type="button" className="btn-mirror !py-2.5" onClick={() => setAdding(true)}>
          <UserPlus className="h-4 w-4" /> Add someone
        </button>
      }
    >
      {data.suggestions.length ? (
        <Panel title="Reflectra noticed" hint="people you've mentioned. Add them, or say they're not someone to track">
          <ul>
            {data.suggestions.map((person, index) => (
              <Suggestion key={person.id} person={person} index={index} />
            ))}
          </ul>
        </Panel>
      ) : null}

      {people.length ? (
        <div className="grid gap-6 xl:grid-cols-[1fr_1.1fr]">
          <Panel className="iris-border overflow-hidden">
            <PeopleOrbit people={people} selectedId={selected?.id ?? null} onSelect={select} dimOthers={Boolean(selectedId)} />
            <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1">
              {groups.map((group) => (
                <span key={group} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="h-2 w-2 rounded-full" style={{ background: GROUP_COLOR[group] }} /> {GROUP_LABEL[group]}
                </span>
              ))}
            </div>
            <p className="mt-3 text-center text-xs text-muted-foreground">Closer means you talked about them more recently.</p>
            {/* The same people as a plain list, for keyboards and screen readers. */}
            <div className="mt-5 flex flex-wrap justify-center gap-2 border-t border-white/5 pt-4">
              {people.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => select(p.id)}
                  aria-pressed={p.id === selected?.id}
                  className={cn("reply-reason", p.id === selected?.id && "is-on")}
                >
                  {p.name}
                </button>
              ))}
            </div>
          </Panel>
          <Panel>
            {selected ? (
              // Keyed by person, so each card you open settles in fresh.
              <div key={selected.id} className="card-reveal">
                <PersonCard person={selected} onDeleted={() => select(null)} />
              </div>
            ) : null}
          </Panel>
        </div>
      ) : (
        <Panel className="iris-border">
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            <Sparkles className="h-6 w-6 text-iris-violet" />
            <p className="font-display text-3xl">Nobody here yet.</p>
            <p className="max-w-md text-sm leading-relaxed text-muted-foreground">
              Add the people you talk about most: your mom, your best friend, your boss. Or just chat; when someone keeps coming up,
              Reflectra will ask if you want to add them.
            </p>
            <button type="button" className="btn-mirror" onClick={() => setAdding(true)}>
              <UserPlus className="h-4 w-4" /> Add someone
            </button>
          </div>
        </Panel>
      )}

      <AddPerson open={adding} onClose={() => setAdding(false)} onAdded={(id) => select(id)} />
    </PageShell>
  );
}
