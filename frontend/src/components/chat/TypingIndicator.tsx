import { MirrorMark } from "@/components/MirrorMark";

export function TypingIndicator() {
  return (
    <div className="flex gap-3 fade-in" role="status" aria-label="Reflectra is typing">
      <MirrorMark className="mt-1 h-7 w-7" breathing />
      <div className="chat-bubble-ai rounded-3xl rounded-tl-md px-5 py-4">
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-foreground/60 typing-dot" />
          <div className="w-1.5 h-1.5 rounded-full bg-foreground/60 typing-dot" />
          <div className="w-1.5 h-1.5 rounded-full bg-foreground/60 typing-dot" />
        </div>
      </div>
    </div>
  );
}
