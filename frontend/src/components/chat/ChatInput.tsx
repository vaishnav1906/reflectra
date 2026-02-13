import { useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
}

export function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [message, setMessage] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isLoading) {
      onSend(message.trim());
      setMessage("");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="relative bg-card border border-border rounded-2xl overflow-hidden transition-all duration-200 focus-within:border-primary/50 focus-within:glow-subtle">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Share your thoughts..."
          rows={1}
          className="w-full bg-transparent px-5 py-4 pr-24 text-sm resize-none focus:outline-none placeholder:text-muted-foreground/50"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
        />
        
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-2">
          <button
            type="button"
            className="p-2 text-muted-foreground hover:text-primary transition-colors"
            title="Reflection mode"
          >
            <Sparkles className="w-4 h-4" />
          </button>
          <button
            type="submit"
            disabled={!message.trim() || isLoading}
            className={cn(
              "p-2.5 rounded-xl transition-all duration-200",
              message.trim() && !isLoading
                ? "bg-primary text-primary-foreground hover:opacity-90"
                : "bg-muted text-muted-foreground cursor-not-allowed"
            )}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>

      <p className="text-center text-xs text-muted-foreground/50 mt-3">
        Reflectra adapts to your communication style and remembers context
      </p>
    </form>
  );
}
