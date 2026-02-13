import { Brain } from "lucide-react";

export function TypingIndicator() {
  return (
    <div className="flex gap-4 fade-in">
      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0 glow-subtle">
        <Brain className="w-5 h-5 text-primary" />
      </div>
      <div className="chat-bubble-ai rounded-2xl rounded-tl-sm px-5 py-4">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-primary/60 typing-dot" />
          <div className="w-2 h-2 rounded-full bg-primary/60 typing-dot" />
          <div className="w-2 h-2 rounded-full bg-primary/60 typing-dot" />
        </div>
      </div>
    </div>
  );
}
