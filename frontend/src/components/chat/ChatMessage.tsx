import { cn } from "@/lib/utils";
import { Brain, User, Users } from "lucide-react";

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
}

export function ChatMessage({ role, content, timestamp, indicators, className }: ChatMessageProps) {
  const isAI = role === "assistant";

  return (
    <div className={cn("flex gap-4 fade-in", isAI ? "flex-row" : "flex-row-reverse", className)}>
      {/* Avatar */}
      <div
        className={cn(
          "w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0",
          isAI ? "bg-primary/10 glow-subtle" : "bg-secondary"
        )}
      >
        {isAI ? (
          <Brain className="w-5 h-5 text-primary" />
        ) : (
          <User className="w-5 h-5 text-muted-foreground" />
        )}
      </div>

      {/* Message Content */}
      <div className={cn("max-w-[70%] space-y-2", !isAI && "text-right")}>
        <div
          className={cn(
            "rounded-2xl px-5 py-4",
            isAI ? "chat-bubble-ai rounded-tl-sm" : "chat-bubble-user rounded-tr-sm"
          )}
        >
          <p className="text-sm leading-relaxed">{content}</p>
        </div>

        {/* Metadata & Indicators */}
        <div className={cn("flex items-center gap-3 px-1", !isAI && "justify-end")}>
          <span className="text-xs text-muted-foreground/60">{timestamp}</span>
          
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
