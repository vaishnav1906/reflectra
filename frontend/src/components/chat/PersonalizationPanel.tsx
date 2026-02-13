import { Activity, Brain, Heart, Zap, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { InfoTooltip } from "@/components/ui/InfoTooltip";

interface Metric {
  label: string;
  value: number;
  icon: typeof Activity;
  color: string;
  tooltip: string;
}

const metrics: Metric[] = [
  { 
    label: "Tone Synchronization", 
    value: 94, 
    icon: Zap, 
    color: "text-primary",
    tooltip: "Degree of linguistic style alignment between system output and user's communication preferences"
  },
  { 
    label: "Memory Retrieval", 
    value: 12, 
    icon: Brain, 
    color: "text-trait-analytical",
    tooltip: "Number of memory entries actively referenced in current session context"
  },
  { 
    label: "Affective Modeling", 
    value: 87, 
    icon: Heart, 
    color: "text-trait-empathetic",
    tooltip: "Accuracy of emotional state inference based on linguistic and semantic markers"
  },
  { 
    label: "Interaction Depth", 
    value: 73, 
    icon: Activity, 
    color: "text-trait-consistent",
    tooltip: "Measure of conversational complexity and introspective engagement in current session"
  },
];

export function PersonalizationPanel() {
  return (
    <div className="bg-card/50 border border-border rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-foreground">Session Telemetry</h3>
          <InfoTooltip 
            content="Real-time metrics reflecting the system's adaptation state during this interaction session" 
          />
        </div>
        <div className="flex items-center gap-1.5">
          <RefreshCw className="w-3 h-3 text-muted-foreground animate-spin" style={{ animationDuration: '3s' }} />
          <span className="text-xs text-muted-foreground">Live</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="bg-background/50 rounded-lg p-3 space-y-2"
          >
            <div className="flex items-center justify-between">
              <metric.icon className={cn("w-4 h-4", metric.color)} />
              <span className="text-lg font-semibold text-foreground">
                {metric.label === "Memory Retrieval" ? metric.value : `${metric.value}%`}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <p className="text-xs text-muted-foreground flex-1">{metric.label}</p>
              <InfoTooltip content={metric.tooltip} className="w-3 h-3" />
            </div>
          </div>
        ))}
      </div>

      <div className="pt-2 border-t border-border space-y-2">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-muted-foreground">
            Personality model adapting in real-time
          </span>
        </div>
        <div className="text-xs text-muted-foreground/60">
          Inference cycle: Continuous • Next reflection: 23:00
        </div>
      </div>
    </div>
  );
}
