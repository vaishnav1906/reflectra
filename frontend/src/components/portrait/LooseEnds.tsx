import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, ChevronDown, RotateCcw, X } from "lucide-react";
import { Panel } from "@/components/portrait/PageShell";
import { FollowUp, formatDay, useFollowUps, useSetFollowUp } from "@/hooks/useReflectra";
import { cn } from "@/lib/utils";

/**
 * Things you said you'd do. Reflectra notices these in conversation and asks about
 * each one once after it's due. Here you can see them, and settle them yourself.
 */

function dueLabel(item: FollowUp) {
  if (item.overdue_by_days > 0) return item.overdue_by_days === 1 ? "was due yesterday" : `was due ${item.overdue_by_days} days ago`;
  const due = new Date(`${item.due}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((due.getTime() - today.getTime()) / 86_400_000);
  if (days <= 0) return "due today";
  if (days === 1) return "due tomorrow";
  return `due ${formatDay(item.due, { weekday: "long" })}`;
}

function OpenItem({ item }: { item: FollowUp }) {
  const navigate = useNavigate();
  const settle = useSetFollowUp();
  return (
    <li className="flex items-start gap-4 border-b border-white/5 py-4 first:pt-0 last:border-0 last:pb-0">
      <span
        className={cn("mt-2 h-2 w-2 shrink-0 rounded-full", item.overdue_by_days > 0 ? "bg-iris-peach" : "bg-iris-cyan")}
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1">
        <p className="font-medium text-foreground">{item.what}</p>
        <button
          type="button"
          disabled={!item.conversation_id}
          onClick={() => item.conversation_id && navigate(`/app/chat?conversation_id=${item.conversation_id}`)}
          className="mt-1 block text-left text-sm italic text-muted-foreground enabled:hover:text-foreground"
          title={item.conversation_id ? "Open the conversation" : undefined}
        >
          “{item.quote}”
        </button>
        <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          said {formatDay(item.said_on)} · {dueLabel(item)}
        </p>
      </div>
      <div className="flex shrink-0 gap-1.5">
        <button
          type="button"
          onClick={() => settle.mutate({ id: item.id, status: "done" })}
          disabled={settle.isPending}
          className="flex h-9 items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3 text-xs text-foreground transition-colors hover:border-iris-cyan/60 hover:bg-white/[0.07]"
          aria-label={`Mark "${item.what}" as done`}
        >
          <Check className="h-3.5 w-3.5" /> Done
        </button>
        <button
          type="button"
          onClick={() => settle.mutate({ id: item.id, status: "dropped" })}
          disabled={settle.isPending}
          className="flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
          aria-label={`Let "${item.what}" go`}
          title="Let it go"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </li>
  );
}

export function LooseEnds() {
  const { data, isLoading, error } = useFollowUps();
  const settle = useSetFollowUp();
  const [showClosed, setShowClosed] = useState(false);
  if (isLoading || error || !data) return null;

  const { open, closed, stats } = data;
  const rate = stats.follow_through;

  return (
    <Panel
      title="Loose ends"
      hint={rate !== null ? `you followed through on ${Math.round(rate * 100)}% (${stats.done} of ${stats.done + stats.dropped})` : undefined}
    >
      {open.length ? (
        <ul>
          {open.map((item) => (
            <OpenItem key={item.id} item={item} />
          ))}
        </ul>
      ) : (
        <p className="text-sm leading-relaxed text-muted-foreground">
          Nothing open. When you mention something you&apos;re going to do (“i&apos;ll text my landlord tomorrow”), it shows up here, and Reflectra
          asks how it went once, after it was due.
        </p>
      )}

      {closed.length ? (
        <div className="mt-5 border-t border-white/5 pt-4">
          <button
            type="button"
            onClick={() => setShowClosed((v) => !v)}
            aria-expanded={showClosed}
            className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ChevronDown className={cn("h-4 w-4 transition-transform", showClosed && "rotate-180")} />
            Settled ({closed.length})
          </button>
          {showClosed ? (
            <ul className="mt-3 space-y-2">
              {closed.map((item) => (
                <li key={item.id} className="flex items-center gap-3 text-sm">
                  <span className={cn("font-mono text-[10px] uppercase tracking-widest", item.status === "done" ? "text-iris-cyan" : "text-muted-foreground")}>
                    {item.status === "done" ? "done" : item.closed_by === "expired" ? "lapsed" : "let go"}
                  </span>
                  <span className={cn("flex-1 truncate", item.status === "done" ? "text-foreground/85" : "text-muted-foreground line-through")}>{item.what}</span>
                  <button
                    type="button"
                    onClick={() => settle.mutate({ id: item.id, status: "open" })}
                    className="rounded-full p-1.5 text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                    aria-label={`Reopen "${item.what}"`}
                    title="Reopen"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </Panel>
  );
}
