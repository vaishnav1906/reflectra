import { TrendingUp, TrendingDown, Minus, Calendar } from "lucide-react";
import { cn } from "@/lib/utils";

type TrendDirection = "up" | "down" | "stable";

interface PatternHighlightProps {
  period: string;
  observation: string;
  trend?: TrendDirection;
  context?: string;
}

const trendConfig = {
  up: { icon: TrendingUp, color: "text-primary", bg: "bg-primary/10" },
  down: { icon: TrendingDown, color: "text-muted-foreground", bg: "bg-muted" },
  stable: { icon: Minus, color: "text-muted-foreground", bg: "bg-muted/50" },
};

export function PatternHighlight({ period, observation, trend = "stable", context }: PatternHighlightProps) {
  const trendStyle = trendConfig[trend];
  const TrendIcon = trendStyle.icon;

  return (
    <div className="bg-card border border-border rounded-xl p-4 transition-all hover:border-primary/30">
      <div className="flex items-start gap-3">
        <div className={cn("p-2 rounded-lg", trendStyle.bg)}>
          <TrendIcon className={cn("w-4 h-4", trendStyle.color)} />
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Calendar className="w-3 h-3 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">{period}</span>
          </div>
          
          <p className="text-sm text-foreground leading-relaxed">{observation}</p>
          
          {context && (
            <p className="text-xs text-muted-foreground/70 mt-2 italic">{context}</p>
          )}
        </div>
      </div>
    </div>
  );
}
