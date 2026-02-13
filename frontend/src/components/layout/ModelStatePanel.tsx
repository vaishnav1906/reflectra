import { 
  Activity, 
  Brain, 
  Database, 
  RefreshCw, 
  Gauge, 
  CircleDot 
} from "lucide-react";
import { cn } from "@/lib/utils";
import { InfoTooltip } from "@/components/ui/InfoTooltip";

interface StateMetric {
  label: string;
  value: string;
  icon: typeof Activity;
  tooltip: string;
}

const stateMetrics: StateMetric[] = [
  { 
    label: "Model Version", 
    value: "v2.4.1", 
    icon: Brain,
    tooltip: "Current version of the personality inference model"
  },
  { 
    label: "Last Inference", 
    value: "2m ago", 
    icon: RefreshCw,
    tooltip: "Time since the last personality trait inference update"
  },
  { 
    label: "Memory Count", 
    value: "156", 
    icon: Database,
    tooltip: "Total number of stored memory entries across all cognitive types"
  },
  { 
    label: "Confidence", 
    value: "94.2%", 
    icon: Gauge,
    tooltip: "Overall model confidence based on interaction volume and consistency"
  },
];

export function ModelStatePanel() {
  return (
    <div className="bg-card/30 border border-border rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CircleDot className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-medium text-foreground">System State</h3>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-muted-foreground">Active</span>
        </div>
      </div>

      <div className="space-y-3">
        {stateMetrics.map((metric) => (
          <div
            key={metric.label}
            className="flex items-center justify-between py-2 border-b border-border/50 last:border-0"
          >
            <div className="flex items-center gap-2">
              <metric.icon className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">{metric.label}</span>
              <InfoTooltip content={metric.tooltip} side="right" />
            </div>
            <span className="text-xs font-medium text-foreground">{metric.value}</span>
          </div>
        ))}
      </div>

      <div className="pt-2 border-t border-border">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center justify-between p-2 bg-muted/30 rounded-lg">
            <span className="text-muted-foreground">Learning</span>
            <span className="text-primary font-medium">Active</span>
          </div>
          <div className="flex items-center justify-between p-2 bg-muted/30 rounded-lg">
            <span className="text-muted-foreground">Cycle</span>
            <span className="text-foreground font-medium">7d</span>
          </div>
        </div>
      </div>
    </div>
  );
}
