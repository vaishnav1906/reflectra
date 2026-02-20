import { useState, useEffect } from "react";
import { 
  Activity, 
  Database, 
  RefreshCw, 
  Gauge, 
  CircleDot 
} from "lucide-react";
import { cn } from "@/lib/utils";
import { InfoTooltip } from "@/components/ui/InfoTooltip";

const API_BASE = "/api";

interface SystemState {
  last_inference: string | null;
  memory_count: number;
  confidence: number;
  learning_active: boolean;
  cycle_days: number;
}

function formatTimeAgo(isoTimestamp: string | null): string {
  if (!isoTimestamp) return "--";
  
  const now = new Date();
  const past = new Date(isoTimestamp);
  const diffMs = now.getTime() - past.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

export function ModelStatePanel() {
  const [systemState, setSystemState] = useState<SystemState | null>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchSystemState = async () => {
      const userId = localStorage.getItem("user_id");
      if (!userId) {
        console.error("❌ No user_id found in localStorage");
        setLoading(false);
        return;
      }
      
      try {
        const response = await fetch(`${API_BASE}/system-state?user_id=${userId}`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data: SystemState = await response.json();
        setSystemState(data);
        console.log("✅ System state loaded:", data);
      } catch (error) {
        console.error("❌ Failed to fetch system state:", error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchSystemState();
  }, []);
  
  const lastInferenceDisplay = loading ? "..." : formatTimeAgo(systemState?.last_inference || null);
  const memoryCountDisplay = loading ? "..." : systemState?.memory_count?.toString() || "--";
  const confidenceDisplay = loading ? "..." : systemState ? `${systemState.confidence.toFixed(1)}%` : "--";
  const learningStatus = systemState?.learning_active ? "Active" : "Inactive";
  const learningStatusColor = systemState?.learning_active ? "text-primary" : "text-muted-foreground";

  return (
    <div className="bg-card/30 border border-border rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CircleDot className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-medium text-foreground">System State</h3>
        </div>
        <div className="flex items-center gap-2">
          <div className={cn(
            "w-2 h-2 rounded-full",
            systemState?.learning_active ? "bg-green-500 animate-pulse" : "bg-muted-foreground"
          )} />
          <span className="text-xs text-muted-foreground">
            {loading ? "..." : learningStatus}
          </span>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between py-2 border-b border-border/50">
          <div className="flex items-center gap-2">
            <RefreshCw className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Last Inference</span>
            <InfoTooltip 
              content="Time since the last personality trait inference update" 
              side="right" 
            />
          </div>
          <span className="text-xs font-medium text-foreground">{lastInferenceDisplay}</span>
        </div>
        
        <div className="flex items-center justify-between py-2 border-b border-border/50">
          <div className="flex items-center gap-2">
            <Database className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Memory Count</span>
            <InfoTooltip 
              content="Total number of stored memory entries across all cognitive types" 
              side="right" 
            />
          </div>
          <span className="text-xs font-medium text-foreground">{memoryCountDisplay}</span>
        </div>
        
        <div className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
          <div className="flex items-center gap-2">
            <Gauge className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Confidence</span>
            <InfoTooltip 
              content="Overall model confidence based on interaction volume and consistency" 
              side="right" 
            />
          </div>
          <span className="text-xs font-medium text-foreground">{confidenceDisplay}</span>
        </div>
      </div>

      <div className="pt-2 border-t border-border">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center justify-between p-2 bg-muted/30 rounded-lg">
            <span className="text-muted-foreground">Learning</span>
            <span className={cn("font-medium", learningStatusColor)}>
              {loading ? "..." : learningStatus}
            </span>
          </div>
          <div className="flex items-center justify-between p-2 bg-muted/30 rounded-lg">
            <span className="text-muted-foreground">Cycle</span>
            <span className="text-foreground font-medium">
              {loading ? "..." : `${systemState?.cycle_days || 7}d`}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
