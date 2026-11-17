import { cn } from "@/lib/utils";
import { History, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { MirrorMark } from "@/components/MirrorMark";
import { ReplyFeedback, type ReplyMode } from "@/components/chat/ReplyFeedback";
import type { RememberedMoment } from "@/contexts/ChatContext";

export interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  indicators?: {
    memoryUsed?: boolean;
    toneAdapted?: boolean;
    reflectionMode?: boolean;
    mirrorMode?: boolean;
  };
  className?: string;
  /** Still being written: shows a blinking caret. */
  streaming?: boolean;
  /** Skip the entrance animation (the reply was already on screen while streaming). */
  noFade?: boolean;
  /** People whose card informed this reply: shown as small chips. */
  peopleUsed?: { id: string; name: string }[];
  /** Past messages this reply drew on: a chip that glows in with a thread of light. */
  remembered?: RememberedMoment[];
  /** Set on a stored reply: shows the rating thumbs. */
  rating?: {
    messageId: string;
    mode: ReplyMode;
    initial?: "up" | "down" | null;
    initialReasons?: string[];
    onChange?: (verdict: "up" | "down" | null, reasons: string[]) => void;
  };
}

export function ChatMessage({ role, content, timestamp, indicators, className, streaming = false, noFade = false, rating, peopleUsed, remembered }: ChatMessageProps) {
  const isAI = role === "assistant";
  const isNotice = isAI && (content.startsWith("⏳") || content.startsWith("⚠️"));

  const parseMarkdown = (text: string) => {
    return text.split('\n').map((line, lineIndex, arr) => {
      // Find both **bold** and *bold* avoiding capturing empty strings
      const regex = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
      const parts = line.split(regex);
      return (
        <span key={lineIndex}>
          {parts.map((part, i) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return <strong key={i}>{part.slice(2, -2)}</strong>;
            } else if (part.startsWith('*') && part.endsWith('*')) {
              return <strong key={i}>{part.slice(1, -1)}</strong>;
            }
            return part;
          })}
          {lineIndex < arr.length - 1 && <br />}
        </span>
      );
    });
  };

  // System notices (rate limit, errors) read as a quiet centred line, not a reply.
  if (isNotice) {
    return (
      <div className={cn("fade-in flex justify-center", className)} role="status">
        <p className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-center text-xs text-muted-foreground">
          {content}
        </p>
      </div>
    );
  }

  return (
    <div className={cn("flex gap-3", isAI && "chat-ai-row", !noFade && !streaming && "fade-in", isAI ? "flex-row" : "flex-row-reverse", className)} aria-busy={streaming || undefined}>
      {isAI && <MirrorMark className="mt-1 h-7 w-7" />}

      <div className={cn("max-w-[78%] space-y-1.5 md:max-w-[70%]", !isAI && "text-right")}>
        <div
          className={cn(
            "inline-block rounded-3xl px-5 py-3.5 text-left",
            isAI ? "chat-bubble-ai rounded-tl-md" : "chat-bubble-user rounded-tr-md"
          )}
        >
          <p className="text-[15px] leading-relaxed">
            {parseMarkdown(content)}
            {streaming ? <span className="stream-caret" aria-hidden="true" /> : null}
          </p>
        </div>

        <div className={cn("flex flex-wrap items-center gap-x-3 gap-y-1.5 px-2", !isAI && "justify-end")}>
          <span className="font-mono text-[10px] tracking-wide text-muted-foreground/50">{timestamp}</span>
          {isAI && peopleUsed?.length && !streaming
            ? peopleUsed.map((p) => (
                <Link
                  key={p.id}
                  to={`/app/people?person=${p.id}`}
                  className="people-chip"
                  title={`This reply knew who ${p.name} is from your People. Tap to see or fix it.`}
                >
                  <Users className="h-3 w-3" /> knew {p.name}
                </Link>
              ))
            : null}
          {isAI && remembered?.length && !streaming
            ? remembered.map((moment, index) => (
                <Link
                  key={`${moment.conversation_id}-${index}`}
                  to={moment.conversation_id ? `/app/chat?conversation_id=${moment.conversation_id}` : "/app/memory"}
                  className="memory-chip"
                  style={{ animationDelay: `${0.25 + index * 0.18}s` }}
                  title={`Remembered what you said ${moment.when}: “${moment.said}” Tap to open that conversation.`}
                >
                  <History className="h-3 w-3" /> remembered {moment.when}
                </Link>
              ))
            : null}
          {isAI && rating && !streaming ? (
            <ReplyFeedback
              messageId={rating.messageId}
              mode={rating.mode}
              initial={rating.initial}
              initialReasons={rating.initialReasons}
              onChange={rating.onChange}
            />
          ) : null}

          {isAI && indicators && (
            <div className="flex items-center gap-2">
              {indicators.memoryUsed && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary/80">
                  memory
                </span>
              )}
              {indicators.toneAdapted && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-accent/10 text-accent/80">
                  adapted
                </span>
              )}
              {indicators.reflectionMode && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-trait-introspective/10 text-trait-introspective/80">
                  reflecting
                </span>
              )}
              {indicators.mirrorMode && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary/80 flex items-center gap-1">
                  <Users className="w-3 h-3" />
                  mirroring
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
