import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Cake, Check, Loader2, MessageCircle, Plus, Trash2, X } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Person, PersonFields, formatDay, usePeopleActions } from "@/hooks/useReflectra";
import { GROUP_COLOR, GROUP_LABEL } from "./PeopleOrbit";
import { cn } from "@/lib/utils";

export const RELATIONSHIP_IDEAS = [
  "mom", "dad", "sister", "brother", "best friend", "friend", "roommate", "partner", "girlfriend", "boyfriend",
  "boss", "coworker", "classmate", "professor", "cousin", "grandma", "grandpa", "mentor",
];

/** The editable fields of a person, shared by "Add someone" and the card. */
export function PersonFieldsForm({
  value,
  onChange,
  autoFocusName = false,
}: {
  value: PersonFields;
  onChange: (next: PersonFields) => void;
  autoFocusName?: boolean;
}) {
  const [aliasText, setAliasText] = useState((value.aliases ?? []).join(", "));
  useEffect(() => setAliasText((value.aliases ?? []).join(", ")), [value.aliases]);

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <label className="people-field">
        <span>Name</span>
        <input
          value={value.name ?? ""}
          onChange={(e) => onChange({ ...value, name: e.target.value })}
          maxLength={60}
          autoFocus={autoFocusName}
          placeholder="Jay"
          required
        />
      </label>
      <label className="people-field">
        <span>Who they are to you</span>
        <input
          value={value.relationship ?? ""}
          onChange={(e) => onChange({ ...value, relationship: e.target.value })}
          maxLength={80}
          placeholder="best friend"
          list="relationship-ideas"
        />
        <datalist id="relationship-ideas">
          {RELATIONSHIP_IDEAS.map((idea) => (
            <option key={idea} value={idea} />
          ))}
        </datalist>
      </label>
      <label className="people-field sm:col-span-2">
        <span>What they&apos;re like, in your words</span>
        <Textarea
          value={value.description ?? ""}
          onChange={(e) => onChange({ ...value, description: e.target.value })}
          maxLength={1000}
          placeholder="Chill, always late, would drop everything for me. We met in first year."
          className="min-h-[88px] border-white/10 bg-white/[0.03]"
        />
      </label>
      <label className="people-field">
        <span>Other names you use</span>
        <input
          value={aliasText}
          onChange={(e) => setAliasText(e.target.value)}
          onBlur={() =>
            onChange({
              ...value,
              aliases: aliasText
                .split(",")
                .map((a) => a.trim())
                .filter(Boolean),
            })
          }
          placeholder="Jayesh, J"
        />
      </label>
      <label className="people-field">
        <span>Birthday (optional)</span>
        <input type="date" value={value.birthday ?? ""} onChange={(e) => onChange({ ...value, birthday: e.target.value || null })} />
      </label>
    </div>
  );
}

function sameFields(person: Person, fields: PersonFields) {
  return (
    (fields.name ?? "") === person.name &&
    (fields.relationship ?? "") === (person.relationship ?? "") &&
    (fields.description ?? "") === (person.description ?? "") &&
    (fields.birthday ?? "") === (person.birthday ?? "") &&
    JSON.stringify(fields.aliases ?? []) === JSON.stringify(person.aliases ?? [])
  );
}

export function PersonCard({ person, onDeleted }: { person: Person; onDeleted: () => void }) {
  const navigate = useNavigate();
  const actions = usePeopleActions();
  const [fields, setFields] = useState<PersonFields>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [note, setNote] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setFields({
      name: person.name,
      relationship: person.relationship ?? "",
      description: person.description ?? "",
      aliases: person.aliases,
      birthday: person.birthday && person.birthday.length === 10 ? person.birthday : "",
    });
    setConfirmDelete(false);
    setError(null);
  }, [person]);

  const dirty = !sameFields(person, fields);
  const color = GROUP_COLOR[person.group];

  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save that.");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em]" style={{ color }}>
            {GROUP_LABEL[person.group]}
          </p>
          <h2 className="mt-1 font-display text-4xl leading-none">{person.name}</h2>
          <p className="mt-2 text-xs text-muted-foreground">
            {person.mention_count
              ? `Came up ${person.mention_count} time${person.mention_count === 1 ? "" : "s"}${
                  person.last_mentioned_at ? `, last ${formatDay(person.last_mentioned_at)}` : ""
                }`
              : "Not mentioned in a chat yet"}
          </p>
          {person.birthday_note ? (
            <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-iris-peach/10 px-3 py-1 text-xs text-iris-peach">
              <Cake className="h-3.5 w-3.5" /> {person.birthday_note}
            </p>
          ) : null}
        </div>
      </div>

      <PersonFieldsForm value={fields} onChange={(next) => { setFields(next); setSaved(false); }} />

      <div className="flex items-center justify-end gap-3">
        {saved && !dirty ? (
          <span className="flex items-center gap-1 text-xs text-muted-foreground fade-in">
            <Check className="h-3.5 w-3.5 text-iris-cyan" /> Saved
          </span>
        ) : null}
        <button
          type="button"
          className="btn-mirror !py-2 disabled:opacity-40"
          disabled={!dirty || saving || !(fields.name ?? "").trim()}
          onClick={() =>
            void run(async () => {
              setSaving(true);
              try {
                await actions.edit(person.id, { ...fields, birthday: fields.birthday || null });
                setSaved(true);
              } finally {
                setSaving(false);
              }
            })
          }
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Save changes
        </button>
      </div>

      <section aria-label={`What you've said about ${person.name}`}>
        <p className="eyebrow mb-3">What you&apos;ve said about them</p>
        {person.notes.length ? (
          <ol className="relative space-y-4 border-l border-white/10 pl-5">
            {person.notes.map((n) => (
              <li key={n.id} className="group relative">
                <span className="absolute -left-[25px] top-1.5 h-2 w-2 rounded-full" style={{ background: color }} />
                <p className="pr-8 text-sm text-foreground/90">{n.text}</p>
                {n.quote ? <p className="mt-1 text-xs italic text-muted-foreground">“{n.quote}”</p> : null}
                <p className="mt-1 flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  {formatDay(n.date)} · {n.source === "you" ? "you added" : "from a chat"}
                  {n.conversation_id ? (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 normal-case tracking-normal text-primary hover:underline"
                      onClick={() => navigate(`/app/chat?conversation_id=${n.conversation_id}`)}
                    >
                      <MessageCircle className="h-3 w-3" /> open
                    </button>
                  ) : null}
                </p>
                <button
                  type="button"
                  onClick={() => void run(() => actions.removeNote(person.id, n.id))}
                  className="absolute right-0 top-0 rounded-full p-1 text-muted-foreground opacity-60 transition hover:bg-white/[0.06] hover:text-foreground group-hover:opacity-100"
                  aria-label={`Forget "${n.text}"`}
                  title="Forget this"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted-foreground">
            Nothing yet. When you talk about {person.name} in a chat, the things worth remembering show up here, with your exact words.
          </p>
        )}
        <form
          className="mt-4 flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!note.trim()) return;
            void run(async () => {
              await actions.addNote(person.id, note.trim());
              setNote("");
            });
          }}
        >
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={240}
            placeholder={`Add something about ${person.name}`}
            className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm outline-none focus:border-iris-violet/60"
            aria-label={`Add a note about ${person.name}`}
          />
          <button type="submit" className="trait-check-btn" disabled={!note.trim()}>
            <Plus className="h-3.5 w-3.5" /> Add
          </button>
        </form>
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/5 pt-4">
        <p className="max-w-sm text-xs leading-relaxed text-muted-foreground">
          Only you see this. Replies use it as your side of things, never as fact about {person.name}.
        </p>
        {confirmDelete ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Forget {person.name} and every note?</span>
            <button type="button" className="text-xs text-muted-foreground hover:text-foreground" onClick={() => setConfirmDelete(false)}>
              Keep
            </button>
            <button
              type="button"
              className="rounded-full border border-destructive/40 px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10"
              onClick={() => void run(async () => { await actions.remove(person.id); onDeleted(); })}
            >
              Forget them
            </button>
          </div>
        ) : (
          <button
            type="button"
            className={cn("inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-destructive")}
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2 className="h-3.5 w-3.5" /> Remove from People
          </button>
        )}
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}
