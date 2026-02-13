import { useState } from "react";
import { ThumbsUp, ThumbsDown, HelpCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface PersonaTraitCardProps {
  name: string;
  leftLabel: string;
  rightLabel: string;
  value: number; // 0-100, where 50 is neutral
  confidence: "low" | "medium" | "high";
  onFeedback?: (accurate: boolean) => void;
}

const confidenceConfig = {
  low: { label: "Low", color: "text-muted-foreground", bg: "bg-muted" },
  medium: { label: "Medium", color: "text-primary", bg: "bg-primary/20" },
  high: { label: "High", color: "text-accent", bg: "bg-accent/20" },
};

export function PersonaTraitCard({
  name,
  leftLabel,
  rightLabel,
  value,
  confidence,
  onFeedback,
}: PersonaTraitCardProps) {
  const [feedback, setFeedback] = useState<"accurate" | "inaccurate" | null>(null);
  const conf = confidenceConfig[confidence];

  const handleFeedback = (accurate: boolean) => {
    const newFeedback = accurate ? "accurate" : "inaccurate";
    setFeedback(feedback === newFeedback ? null : newFeedback);
    onFeedback?.(accurate);
  };

  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">{name}</span>
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="p-0.5 rounded hover:bg-muted/50 transition-colors">
                  <HelpCircle className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-xs bg-card border border-border">
                <p className="text-xs text-muted-foreground">
                  Based on patterns across multiple interactions.
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        
        <div className="flex items-center gap-2">
          <span className={cn("text-xs px-2 py-0.5 rounded-full", conf.bg, conf.color)}>
            {conf.label} confidence
          </span>
        </div>
      </div>

      {/* Spectrum bar */}
      <div className="mb-3">
        <div className="flex justify-between mb-2">
          <span className="text-xs text-muted-foreground">{leftLabel}</span>
          <span className="text-xs text-muted-foreground">{rightLabel}</span>
        </div>
        <div className="relative h-2 bg-muted rounded-full overflow-hidden">
          {/* Center marker */}
          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-border z-10" />
          
          {/* Value indicator */}
          <div
            className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-primary border-2 border-background shadow-sm z-20 transition-all"
            style={{ left: `calc(${value}% - 6px)` }}
          />
          
          {/* Fill from center */}
          <div
            className={cn(
              "absolute top-0 bottom-0 bg-primary/30",
              value >= 50
                ? "left-1/2"
                : "right-1/2"
            )}
            style={{
              width: `${Math.abs(value - 50)}%`,
            }}
          />
        </div>
      </div>

      {/* Feedback buttons */}
      <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
        <span className="text-xs text-muted-foreground mr-2">Does this feel accurate?</span>
        <button
          onClick={() => handleFeedback(true)}
          className={cn(
            "flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-all",
            feedback === "accurate"
              ? "bg-green-500/10 text-green-500 border border-green-500/30"
              : "text-muted-foreground hover:bg-muted/50"
          )}
        >
          <ThumbsUp className="w-3 h-3" />
          Yes
        </button>
        <button
          onClick={() => handleFeedback(false)}
          className={cn(
            "flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-all",
            feedback === "inaccurate"
              ? "bg-red-400/10 text-red-400 border border-red-400/30"
              : "text-muted-foreground hover:bg-muted/50"
          )}
        >
          <ThumbsDown className="w-3 h-3" />
          No
        </button>
      </div>
    </div>
  );
}
