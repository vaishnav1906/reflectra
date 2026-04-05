import { useState, useEffect } from "react";
import { Zap, Clock, Target, Activity, RefreshCw } from "lucide-react";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { cn } from "@/lib/utils";

const API_BASE = "/api/db";

interface TelemetryData {
  total_generations: number;
  avg_latency_ms: number;
  success_rate: number;
  avg_realism_score: number;
  total_fallbacks: number;
}

export function MirrorTelemetryDashboard() {
  const [data, setData] = useState<TelemetryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchTelemetry = async () => {
    try {
      setRefreshing(true);
      const userId = localStorage.getItem("user_id");
      if (!userId) {
        setLoading(false);
        setRefreshing(false);
        return;
      }
      const res = await fetch(`${API_BASE}/mirror-telemetry/${userId}`);
      if (!res.ok) throw new Error("Failed to fetch telemetry");
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
    // Refresh every 10 seconds
    const interval = setInterval(fetchTelemetry, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-card border border-border rounded-xl p-6 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-1 h-full bg-primary" />
      
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-foreground flex items-center gap-2">
              <Zap className="w-4 h-4 text-primary" />
              Mirror Engine Telemetry
            </h3>
            <InfoTooltip content="Real-time performance metrics and generative bounds observed from the Mirror Mode LLM pipeline" />
          </div>
          <p className="text-sm text-muted-foreground">Real-time inference observability</p>
        </div>
        <button 
          onClick={fetchTelemetry}
          disabled={refreshing}
          className="p-2 hover:bg-muted rounded-full transition-colors"
        >
          <RefreshCw className={cn("w-4 h-4 text-muted-foreground", refreshing && "animate-spin")} />
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Activity className="w-6 h-6 animate-pulse text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="py-8 text-center text-sm text-red-500 bg-red-500/10 rounded-lg">
          {error}
        </div>
      ) : data ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-background border border-border rounded-lg p-4">
            <p className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-medium">Generations</p>
            <div className="flex items-end gap-2">
              <span className="text-2xl font-bold text-foreground">{data.total_generations}</span>
              <span className="text-xs text-muted-foreground mb-1">total</span>
            </div>
          </div>
          
          <div className="bg-background border border-border rounded-lg p-4">
            <p className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-medium flex items-center gap-1">
              <Clock className="w-3 h-3" /> Latency
            </p>
            <div className="flex items-end gap-2">
              <span className="text-2xl font-bold text-trait-consistent">
                {Math.round(data.avg_latency_ms)}
              </span>
              <span className="text-xs text-muted-foreground mb-1">ms avg</span>
            </div>
          </div>

          <div className="bg-background border border-border rounded-lg p-4">
            <p className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-medium flex items-center gap-1">
              <Target className="w-3 h-3" /> Realism
            </p>
            <div className="flex items-end gap-2">
              <span className="text-2xl font-bold text-trait-curious">
                {data.avg_realism_score.toFixed(2)}
              </span>
              <span className="text-xs text-muted-foreground mb-1">/ 1.0 avg</span>
            </div>
          </div>

          <div className="bg-background border border-border rounded-lg p-4">
            <p className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-medium flex items-center gap-1">
              <Activity className="w-3 h-3" /> Success
            </p>
            <div className="flex items-end gap-2">
              <span className={cn(
                "text-2xl font-bold",
                data.success_rate >= 90 ? "text-green-500" : 
                data.success_rate >= 70 ? "text-yellow-500" : "text-red-500"
              )}>
                {Math.round(data.success_rate)}%
              </span>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
