import { useState } from "react";
import { Calendar, Send } from "lucide-react";
import { cn } from "@/lib/utils";

interface DailyReflectionInputProps {
  onSubmit?: (reflection: string) => void;
}

export function DailyReflectionInput({ onSubmit }: DailyReflectionInputProps) {
  const [reflection, setReflection] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
  });

  const handleSubmit = () => {
    if (reflection.trim()) {
      onSubmit?.(reflection.trim());
      setSubmitted(true);
      setTimeout(() => {
        setReflection("");
        setSubmitted(false);
      }, 2000);
    }
  };

  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">Daily Reflection</span>
          <span className="text-xs text-muted-foreground">• Optional</span>
        </div>
        <span className="text-xs text-muted-foreground">{today}</span>
      </div>

      <div className="relative">
        <textarea
          value={reflection}
          onChange={(e) => setReflection(e.target.value)}
          placeholder="A brief thought about your day..."
          rows={2}
          maxLength={280}
          disabled={submitted}
          className={cn(
            "w-full bg-muted/30 border border-border rounded-lg px-4 py-3 pr-12 text-sm resize-none",
            "focus:outline-none focus:border-primary/50 placeholder:text-muted-foreground/50",
            "transition-all",
            submitted && "opacity-50"
          )}
        />
        <button
          onClick={handleSubmit}
          disabled={!reflection.trim() || submitted}
          className={cn(
            "absolute right-3 bottom-3 p-1.5 rounded-md transition-all",
            reflection.trim() && !submitted
              ? "bg-primary/10 text-primary hover:bg-primary/20"
              : "text-muted-foreground/30 cursor-not-allowed"
          )}
        >
          <Send className="w-4 h-4" />
        </button>
      </div>

      {submitted ? (
        <p className="text-xs text-primary mt-2">Reflection recorded</p>
      ) : (
        <p className="text-xs text-muted-foreground/60 mt-2">
          This helps Reflectra understand patterns over time.
        </p>
      )}
    </div>
  );
}
